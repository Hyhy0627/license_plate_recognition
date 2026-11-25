"""HTTP adapters for authenticated video analysis jobs."""

from typing import Literal
from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile

from src.api.auth import get_current_user
from src.api.storage_responses import media_response
from src.db.models import User
from src.services import video_jobs
from src.services.inference_rate_limit import inference_rate_limiter


router = APIRouter(prefix="/video-tracking", tags=["Video Tracking"])


@router.post('/jobs', status_code=202)
def create_video_job(
    file: UploadFile = File(...),
    mode: Literal["combined", "fast", "detailed"] = Query("fast"),
    user: User = Depends(get_current_user),
    request: Request = None,
):
    if request is not None:
        inference_rate_limiter.check("video", user.id)
    return video_jobs.create_video_job(file.file, file.filename or "", mode, user)


@router.get('/jobs')
def list_video_jobs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                    user: User = Depends(get_current_user)):
    return video_jobs.list_video_jobs(page, page_size, user)


@router.get('/jobs/{job_id}/media')
def get_video_media(job_id: str, request: Request, user: User = Depends(get_current_user)):
    media, media_type = video_jobs.get_video_media(job_id, user)
    return media_response(request, media, media_type)


@router.get('/jobs/{job_id}')
def get_video_job(job_id: str, user: User = Depends(get_current_user)):
    return video_jobs.get_video_job(job_id, user)


@router.delete('/jobs/{job_id}')
def delete_video_job(job_id: str, user: User = Depends(get_current_user)):
    video_jobs.delete_video_job(job_id, user)
    return Response(status_code=204)
