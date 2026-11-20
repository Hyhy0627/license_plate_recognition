"""HTTP adapters for authenticated video analysis jobs."""

from typing import Literal
from fastapi import APIRouter, Depends, File, Query, UploadFile

from fastapi.responses import FileResponse

from src.api.auth import get_current_user
from src.db.models import User
from src.services import video_jobs


router = APIRouter(prefix="/video-tracking", tags=["Video Tracking"])


@router.post('/jobs', status_code=202)
def create_video_job(
    file: UploadFile = File(...),
    mode: Literal["combined", "fast", "detailed"] = Query("fast"),
    user: User = Depends(get_current_user),
):
    return video_jobs.create_video_job(file.file, file.filename or "", mode, user)


@router.get('/jobs/{job_id}/media')
def get_video_media(job_id: str, user: User = Depends(get_current_user)):
    path = video_jobs.get_video_media(job_id, user)
    return FileResponse(path, media_type=video_jobs.VIDEO_TYPES[path.suffix], headers={"Cache-Control": "no-store"})


@router.get('/jobs/{job_id}')
def get_video_job(job_id: str, user: User = Depends(get_current_user)):
    return video_jobs.get_video_job(job_id, user)
