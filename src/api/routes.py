"""HTTP adapters for recognition and owner-scoped image history."""

import csv
from io import StringIO
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from src.api.auth import COOKIE_NAME, get_current_user
from src.config import settings
from src.core.exceptions import ServiceUnavailableException
from src.db.models import User
from src.db.session import get_db
from src.infrastructure.inference_worker import recognize_image
from src.services import history, image_recognition
from src.services.inference_rate_limit import inference_rate_limiter
from src.services.schemas import PlateDetectionResponse


router = APIRouter(prefix="/license-plates", tags=["License Plates"])
image_router = APIRouter()


@image_router.post('/detect', response_model=PlateDetectionResponse)
def detect_license_plate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    request: Request = None,
):
    if request is not None and not settings.INFERENCE_WORKER_URL:
        inference_rate_limiter.check("image", user.id)
    if settings.INFERENCE_WORKER_URL:
        token = request.cookies.get(COOKIE_NAME)
        result = recognize_image(image_recognition.read_image_upload(file.file), token, COOKIE_NAME)
        if 300 <= result.status_code < 400:
            raise ServiceUnavailableException("Worker nhận diện ảnh tạm thời không khả dụng.")
        return Response(result.content, status_code=result.status_code, media_type=result.headers.get("Content-Type"))
    return image_recognition.detect_license_plate(file.file, db, user)


router.include_router(image_router)


@router.get('/history')
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    plate_type: Literal["one_line", "two_line"] | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Lấy lịch sử từ cơ sở dữ liệu được cấu hình, có phân trang.
    """
    return history.get_history(page, page_size, db, user, plate_type)


@router.delete('/history')
def delete_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"deleted": history.delete_history(db, user)}


@router.get('/export')
def export_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    output = StringIO(newline="")
    writer = csv.writer(output)
    columns = ("id", "plate_number", "confidence", "plate_type", "engine_used", "created_at")
    writer.writerow(columns)
    for record in history.export_history(db, user):
        row = record.to_dict()
        writer.writerow([row[column] for column in columns])
    return Response(
        "\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="plate-history.csv"'},
    )


@router.get('/search')
async def search_plates(
    plate: str = Query(..., min_length=1, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    plate_type: Literal["one_line", "two_line"] | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Tìm kiếm các xe đã nhận diện trong cơ sở dữ liệu được cấu hình.
    """
    return history.search_plates(plate, page, page_size, db, user, plate_type)


@router.get('/{detection_id}')
async def get_detection_detail(
    detection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Xem chi tiết một lượt nhận diện trong cơ sở dữ liệu được cấu hình.
    """
    return history.get_detection_detail(detection_id, db, user)


@router.delete('/{detection_id}')
def delete_detection(detection_id: int, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    history.delete_detection(detection_id, db, user)
    return Response(status_code=204)
