"""HTTP adapters for recognition and owner-scoped image history."""

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from src.api.auth import get_current_user
from src.db.models import User
from src.db.session import get_db
from src.services import history, image_recognition
from src.services.schemas import PlateDetectionResponse


router = APIRouter(prefix="/license-plates", tags=["License Plates"])


@router.post('/detect', response_model=PlateDetectionResponse)
def detect_license_plate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return image_recognition.detect_license_plate(file.file, db, user)


@router.get('/history')
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Lấy danh sách lịch sử nhận diện từ cơ sở dữ liệu SQLite (data/alpr.db) có phân trang.
    """
    return history.get_history(page, page_size, db, user)


@router.get('/search')
async def search_plates(
    plate: str = Query(..., min_length=1, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Tìm kiếm các xe đã nhận diện trong SQLite theo biển số.
    """
    return history.search_plates(plate, page, page_size, db, user)


@router.get('/{detection_id}')
async def get_detection_detail(
    detection_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Xem chi tiết một lượt nhận diện theo ID từ SQLite.
    """
    return history.get_detection_detail(detection_id, db, user)
