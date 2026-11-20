"""Bounded in-process video jobs, upload storage and owner-scoped retrieval."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from uuid import uuid4
from time import perf_counter

from filelock import FileLock, Timeout
from sqlalchemy import select, text, update

from typing import BinaryIO
from src.core.exceptions import (EntityNotFoundException, InvalidPayloadException, PayloadTooLargeException,
                                 RateLimitExceededException, ServiceUnavailableException)

from src.config import BASE_DIR, settings
from src.core.video.tracker import process_video
from src.services.model_runtime import _inference_lock, get_detector, get_ocr_engine, get_video_engines
from src.db.models import User, VideoJob
from src.db.session import SessionLocal
from src.utils.logger import logger


MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_SUFFIXES = {".mp4", ".mov", ".avi", ".webm"}
VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo", ".webm": "video/webm"}
UPLOAD_DIR = BASE_DIR / "data" / "video_jobs"
ACTIVE = ("queued", "running")
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-tracking")


def _job_lock(job_id):
    # Released by the OS on worker exit. The media directory is shared with SQLite.
    return FileLock(UPLOAD_DIR / f"{job_id}.lock", timeout=0, thread_local=False)


def _recover_interrupted(db, job):
    try:
        with _job_lock(job.id):
            # The worker may have finished since the SELECT.
            db.execute(update(VideoJob).where(VideoJob.id == job.id, VideoJob.status.in_(ACTIVE))
                       .values(status="failed", error="Máy chủ đã dừng trước khi xử lý xong video."))
    except Timeout:
        pass


def _reserve_job(job_id, owner_id, filename, mode):
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
        db.add(VideoJob(id=job_id, owner_id=owner_id, filename=filename, mode=mode))


def _set_job(job_id, **updates):
    with SessionLocal.begin() as db:
        db.execute(update(VideoJob).where(VideoJob.id == job_id).values(**updates))


def _run_job(job_id, path, mode, lease):
    last_progress = 0

    def progress(value):
        nonlocal last_progress
        if value > last_progress:
            _set_job(job_id, progress=value)
            last_progress = value

    started = perf_counter()
    try:
        _set_job(job_id, status="running")
        detector, ocr = get_video_engines() if mode == "fast" else (get_detector(), get_ocr_engine())
        result = process_video(
            path,
            Path(settings.VEHICLE_MODEL_PATH),
            detector,
            ocr,
            _inference_lock,
            progress,
            mode=mode,
            use_remote_ocr=mode != "fast",
        )
        result["processing_seconds"] = round(perf_counter() - started, 3)
        _set_job(job_id, status="completed", progress=100, result_json=json.dumps(result, ensure_ascii=False, allow_nan=False))
    except ValueError as exc:
        _set_job(job_id, status="failed", error=str(exc)[:500])
    except Exception:
        logger.exception("Video tracking job failed")
        _set_job(job_id, status="failed", error="Không xử lý được video. Hãy thử một video khác hoặc kiểm tra model.")
    finally:
        lease.release()


def create_video_job(file: BinaryIO, filename: str, mode: str, user: User):
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise InvalidPayloadException("Hãy chọn video MP4, MOV, AVI hoặc WEBM.")
    if not Path(settings.VEHICLE_MODEL_PATH).is_file():
        raise ServiceUnavailableException("Thiếu model phát hiện xe. Đặt model tại models/yolov8n.pt hoặc cấu hình VEHICLE_MODEL_PATH.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid4().hex
    path = UPLOAD_DIR / f"{job_id}{suffix}"
    lease = _job_lock(job_id)
    lease.acquire()
    size = 0
    reserved = False
    try:
        _reserve_job(job_id, user.id, Path(filename).name[-255:], mode)
        reserved = True
        with path.open("wb") as destination:
            while chunk := file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise PayloadTooLargeException("Video vượt quá 100 MB.")
                destination.write(chunk)
        if not size:
            raise InvalidPayloadException("Video rỗng.")
        _executor.submit(_run_job, job_id, path, mode, lease)
        return {"id": job_id, "status": "queued", "progress": 0}
    except Exception:
        try:
            path.unlink(missing_ok=True)
            if reserved:
                with SessionLocal.begin() as db:
                    db.query(VideoJob).filter_by(id=job_id).delete()
        finally:
            lease.release()
        raise


def get_video_media(job_id: str, user: User):
    with SessionLocal() as db:
        filename = db.scalar(select(VideoJob.filename).where(VideoJob.id == job_id, VideoJob.owner_id == user.id))
    if filename is None:
        raise EntityNotFoundException("Không tìm thấy video.")
    path = UPLOAD_DIR / f"{job_id}{Path(filename).suffix.lower()}"
    if not path.is_file():
        raise EntityNotFoundException("Video không còn trên máy chủ.")
    return path


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
