"""Video admission, distributed execution and owner-scoped retrieval."""

from contextlib import nullcontext
from functools import partial
import json
from pathlib import Path
from uuid import uuid4
from time import perf_counter

from filelock import FileLock, Timeout
from sqlalchemy import select, text, update

from typing import BinaryIO
from src.core.exceptions import (EntityNotFoundException, InvalidPayloadException,
                                 RateLimitExceededException, ServiceUnavailableException)

from src.config import BASE_DIR, settings
from src.core.models.registry import resolve_path
from src.core.video.tracker import process_video
from src.db.job_locks import PostgresJobLease, job_lock_key
from src.services.cloud_vision import get_cloud_vision_client
from src.services.model_runtime import _inference_lock, get_detector, get_ocr_engine, get_video_engines
from src.services.queue import get_task_queue
from src.services.queue.base import VideoTask
from src.db.models import User, VideoJob
from src.db.session import SessionLocal
from src.services.storage import get_storage
from src.services.storage.base import VIDEO_CATEGORY, VIDEO_TYPES
from src.utils.logger import logger


MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_SUFFIXES = set(VIDEO_TYPES)
UPLOAD_DIR = BASE_DIR / "data" / "video_jobs"
ACTIVE = ("queued", "running")
REDIS_UPLOAD = "redis-upload"
REDIS_READY = "redis"


def _job_lock(job_id):
    engine = SessionLocal.kw["bind"]
    if engine.dialect.name == "postgresql":
        return PostgresJobLease(engine.url, job_id)
    # SQLite deployments use the lock directory on the same host.
    return FileLock(UPLOAD_DIR / f"{job_id}.lock", timeout=0, thread_local=False)


def _recover_interrupted(db, job):
    if job.queue_backend == REDIS_READY:
        return
    if db.get_bind().dialect.name == "postgresql":
        if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": job_lock_key(job.id)}):
            return
        lease = nullcontext()
    else:
        lease = _job_lock(job.id)
    try:
        with lease:
            # The worker may have finished since the SELECT.
            db.execute(update(VideoJob).where(VideoJob.id == job.id, VideoJob.status.in_(ACTIVE))
                       .values(status="failed", error="Máy chủ đã dừng trước khi xử lý xong video."))
    except Timeout:
        pass


def _reserve_job(job_id, owner_id, filename, mode, *, queue_backend=None):
    with SessionLocal.begin() as db:
        # Serialize admission across processes, then release the DB before upload.
        if db.get_bind().dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        elif db.get_bind().dialect.name == "postgresql":
            db.execute(text("LOCK TABLE video_jobs IN SHARE ROW EXCLUSIVE MODE"))
        active = db.query(VideoJob).filter(VideoJob.status.in_(ACTIVE))
        for job in active.all():
            _recover_interrupted(db, job)
        if active.count() >= 2:
            raise RateLimitExceededException("Hệ thống đang xử lý video khác. Vui lòng thử lại sau.")
        db.add(VideoJob(id=job_id, owner_id=owner_id, filename=filename, mode=mode, queue_backend=queue_backend))


def _set_job(job_id, *, expected_worker_token=None, **updates):
    with SessionLocal.begin() as db:
        query = update(VideoJob).where(VideoJob.id == job_id, VideoJob.status.in_(ACTIVE))
        if expected_worker_token is not None:
            query = query.where(VideoJob.worker_token == expected_worker_token)
        db.execute(query.values(**updates))


def _run_job(job_id, filename, mode, lease, storage, *, worker_token=None):
    last_progress = 0
    write = (partial(_set_job, job_id, expected_worker_token=worker_token) if worker_token
             else partial(_set_job, job_id))

    def progress(value):
        nonlocal last_progress
        if value > last_progress:
            write(progress=value)
            last_progress = value

    started = perf_counter()
    try:
        write(status="running")
        detector, ocr = get_video_engines() if mode == "fast" else (get_detector(), get_ocr_engine())
        cloud_vision = get_cloud_vision_client(ocr.engine_type) if mode != "fast" else None
        with storage.video_file(filename) as path:
            result = process_video(
                path,
                resolve_path(settings.VEHICLE_MODEL_PATH),
                detector,
                ocr,
                _inference_lock,
                progress,
                mode=mode,
                use_remote_ocr=mode != "fast",
                cloud_vision=cloud_vision,
                remote_ocr_timeout=settings.VIDEO_NINEROUTER_TIMEOUT,
            )
        result["processing_seconds"] = round(perf_counter() - started, 3)
        write(status="completed", progress=100, result_json=json.dumps(result, ensure_ascii=False, allow_nan=False))
    except ValueError as exc:
        write(status="failed", error=str(exc)[:500])
    except Exception:
        logger.exception("Video tracking job failed")
        write(status="failed", error="Không xử lý được video. Hãy thử một video khác hoặc kiểm tra model.")
    finally:
        lease.release()


def create_video_job(file: BinaryIO, filename: str, mode: str, user: User):
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise InvalidPayloadException("Hãy chọn video MP4, MOV, AVI hoặc WEBM.")
    distributed = bool(settings.REDIS_URL)
    if not distributed and not resolve_path(settings.VEHICLE_MODEL_PATH).is_file():
        raise ServiceUnavailableException("Thiếu model phát hiện xe. Đặt model tại models/yolov8n.pt hoặc cấu hình VEHICLE_MODEL_PATH.")

    storage = get_storage(video_dir=UPLOAD_DIR)
    job_id = uuid4().hex
    stored_name = f"{job_id}{suffix}"
    lease = _job_lock(job_id)
    lease.acquire()
    reserved = False
    ready = False
    try:
        _reserve_job(job_id, user.id, Path(filename).name[-255:], mode,
                     queue_backend=REDIS_UPLOAD if distributed else None)
        reserved = True
        storage.save_video(stored_name, file, max_bytes=MAX_UPLOAD_BYTES)
        if distributed:
            _set_job(job_id, queue_backend=REDIS_READY)
            ready = True
        else:
            def cancel_local():
                try:
                    _set_job(job_id, status="failed", error="Tác vụ video đã bị hủy.")
                finally:
                    lease.release()

            get_task_queue().enqueue_video_job(VideoTask(
                job_id, partial(_run_job, job_id, stored_name, mode, lease, storage), cancel_local,
            ))
    except Exception:
        try:
            if reserved:
                try:
                    storage.delete_file(VIDEO_CATEGORY, stored_name)
                except Exception as exc:
                    logger.warning("Video upload cleanup failed: {}", type(exc).__name__)
                with SessionLocal.begin() as db:
                    db.query(VideoJob).filter_by(id=job_id).delete()
        finally:
            lease.release()
        raise
    finally:
        if ready:
            lease.release()
    if distributed:
        try:
            get_task_queue().enqueue_video_job(VideoTask(job_id))
        except ServiceUnavailableException:
            # The worker republishes durable ready rows after Redis recovers.
            logger.warning("Video job {} saved for queue reconciliation.", job_id)
    return {"id": job_id, "status": "queued", "progress": 0}


def redis_video_jobs():
    with SessionLocal() as db:
        return db.scalars(select(VideoJob.id).where(VideoJob.queue_backend == REDIS_READY,
                                                    VideoJob.status.in_(ACTIVE))).all()


def run_redis_video_job(job_id: str) -> bool:
    """Acknowledge only terminal or obsolete deliveries, after releasing ownership."""
    if not job_id:
        return True
    lease = _job_lock(job_id)
    try:
        lease.acquire()
    except Timeout:
        return False
    try:
        with SessionLocal.begin() as db:
            job = db.get(VideoJob, job_id)
            if job is None or job.queue_backend != REDIS_READY or job.status not in ACTIVE:
                return True
            worker_token = uuid4().hex
            job.worker_token = worker_token
            job.status = "running"
            job.progress = 0
            filename = f"{job_id}{Path(job.filename).suffix.lower()}"
            mode = job.mode
        _run_job(job_id, filename, mode, lease, get_storage(video_dir=UPLOAD_DIR), worker_token=worker_token)
        with SessionLocal() as db:
            status = db.scalar(select(VideoJob.status).where(VideoJob.id == job_id))
        return status not in ACTIVE
    finally:
        lease.release()


def get_video_media(job_id: str, user: User):
    with SessionLocal() as db:
        filename = db.scalar(select(VideoJob.filename).where(VideoJob.id == job_id, VideoJob.owner_id == user.id))
    if filename is None:
        raise EntityNotFoundException("Không tìm thấy video.")
    suffix = Path(filename).suffix.lower()
    try:
        media = get_storage(video_dir=UPLOAD_DIR).get_file(VIDEO_CATEGORY, f"{job_id}{suffix}")
    except FileNotFoundError as exc:
        raise EntityNotFoundException("Video không còn trên máy chủ.") from exc
    return media, VIDEO_TYPES[suffix]


def get_video_job(job_id: str, user: User):
    with SessionLocal.begin() as db:
        job = db.scalar(select(VideoJob).where(VideoJob.id == job_id, VideoJob.owner_id == user.id))
        if job is None:
            raise EntityNotFoundException("Không tìm thấy tác vụ video.")
        if job.status in ACTIVE:
            _recover_interrupted(db, job)
            db.refresh(job)
        return {"id": job.id, "status": job.status, "progress": job.progress, "error": job.error,
                "result": json.loads(job.result_json) if job.result_json is not None else None}


def list_video_jobs(page: int, page_size: int, user: User):
    with SessionLocal() as db:
        owned = db.query(VideoJob).filter(VideoJob.owner_id == user.id)
        total = owned.count()
        jobs = owned.order_by(VideoJob.created_at.desc(), VideoJob.id.desc()).offset(
            (page - 1) * page_size).limit(page_size).all()
        return {"total": total, "page": page, "page_size": page_size,
                "items": [{"id": job.id, "filename": job.filename, "mode": job.mode,
                           "status": job.status, "progress": job.progress,
                           "created_at": job.created_at.isoformat() if job.created_at else None}
                          for job in jobs]}


def delete_video_job(job_id: str, user: User):
    with SessionLocal.begin() as db:
        job = db.scalar(select(VideoJob).where(VideoJob.id == job_id, VideoJob.owner_id == user.id))
        if job is None:
            raise EntityNotFoundException("Không tìm thấy tác vụ video.")
        if job.status in ACTIVE:
            raise InvalidPayloadException("Chỉ có thể xóa tác vụ video đã kết thúc.")
        filename = f"{job.id}{Path(job.filename).suffix.lower()}"
        try:
            get_storage(video_dir=UPLOAD_DIR).delete_file(VIDEO_CATEGORY, filename)
        except FileNotFoundError:
            pass
        db.delete(job)
