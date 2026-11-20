"""Authenticated, bounded video analysis jobs for the tracking demo."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4
from time import perf_counter

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from src.api.auth import get_current_user
from src.api.routes import _inference_lock, get_detector, get_ocr_engine
from src.config import BASE_DIR, settings
from src.core.video_tracker import process_video
from src.core.video_models import get_video_engines
from src.db.models import User
from src.utils.logger import logger


router = APIRouter(prefix="/video-tracking", tags=["Video Tracking"])
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_SUFFIXES = {".mp4", ".mov", ".avi", ".webm"}
VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo", ".webm": "video/webm"}
UPLOAD_DIR = BASE_DIR / "data" / "video_jobs"
_jobs = {}
_jobs_lock = Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-tracking")


def _set_job(job_id, **updates):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(updates)


def _run_job(job_id, path, mode):
    _set_job(job_id, status="running")
    started = perf_counter()
    try:
        detector, ocr = get_video_engines() if mode == "fast" else (get_detector(), get_ocr_engine())
        result = process_video(
            path,
            Path(settings.VEHICLE_MODEL_PATH),
            detector,
            ocr,
            _inference_lock,
            lambda value: _set_job(job_id, progress=value),
            mode=mode,
            use_remote_ocr=mode != "fast",
        )
        result["processing_seconds"] = round(perf_counter() - started, 3)
        _set_job(job_id, status="completed", progress=100, result=result)
    except ValueError as exc:
        _set_job(job_id, status="failed", error=str(exc))
    except Exception:
        logger.exception("Video tracking job failed")
        _set_job(job_id, status="failed", error="Không xử lý được video. Hãy thử một video khác hoặc kiểm tra model.")


@router.post("/jobs", status_code=202)
def create_video_job(file: UploadFile = File(...), mode: Literal["combined", "fast", "detailed"] = Query("fast"), user: User = Depends(get_current_user)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, "Hãy chọn video MP4, MOV, AVI hoặc WEBM.")
    if not Path(settings.VEHICLE_MODEL_PATH).is_file():
        raise HTTPException(503, "Thiếu model phát hiện xe. Đặt yolov8n.pt tại thư mục gốc dự án.")

    with _jobs_lock:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        for old_id in [key for key, value in _jobs.items() if value["created_at"] < cutoff and value["status"] in {"completed", "failed"}]:
            _jobs[old_id]["path"].unlink(missing_ok=True)
            del _jobs[old_id]
        if sum(value["status"] in {"queued", "running"} for value in _jobs.values()) >= 2:
            raise HTTPException(429, "Hệ thống đang xử lý video khác. Vui lòng thử lại sau.")
        job_id = uuid4().hex
        _jobs[job_id] = {"id": job_id, "owner_id": user.id, "status": "queued", "progress": 0, "error": None, "result": None, "created_at": datetime.now(timezone.utc), "path": UPLOAD_DIR / f"{job_id}{suffix}"}

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{job_id}{suffix}"
    size = 0
    try:
        with path.open("wb") as destination:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Video vượt quá 100 MB.")
                destination.write(chunk)
        if not size:
            raise HTTPException(400, "Video rỗng.")
        _executor.submit(_run_job, job_id, path, mode)
        return {"id": job_id, "status": "queued", "progress": 0}
    except Exception:
        path.unlink(missing_ok=True)
        with _jobs_lock:
            _jobs.pop(job_id, None)
        raise


@router.get("/jobs/{job_id}/media")
def get_video_media(job_id: str, user: User = Depends(get_current_user)):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None or job["owner_id"] != user.id:
            raise HTTPException(404, "Không tìm thấy video.")
        path = job["path"]
    if not path.is_file():
        raise HTTPException(404, "Video không còn trên máy chủ.")
    return FileResponse(path, media_type=VIDEO_TYPES[path.suffix], headers={"Cache-Control": "no-store"})


@router.get("/jobs/{job_id}")
def get_video_job(job_id: str, user: User = Depends(get_current_user)):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None or job["owner_id"] != user.id:
            raise HTTPException(404, "Không tìm thấy tác vụ video.")
        return {key: value for key, value in job.items() if key not in {"owner_id", "created_at", "path"}}
