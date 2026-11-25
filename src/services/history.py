"""Owner-scoped recognition history queries."""

from src.core.exceptions import EntityNotFoundException, InvalidPayloadException

from src.core.ocr.postprocessor import PlatePostprocessor
from src.db.models import PlateHistory


def get_history(page, page_size, db, user, plate_type=None):
    """
    Lấy lịch sử từ cơ sở dữ liệu được cấu hình (SQLite hoặc PostgreSQL).
    """
    start_idx = (page - 1) * page_size
    owned = db.query(PlateHistory).filter(PlateHistory.owner_id == user.id)
    if plate_type:
        owned = owned.filter(PlateHistory.plate_type == plate_type)
    total = owned.count()
    records = owned.order_by(PlateHistory.id.desc()).offset(start_idx).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [r.to_dict() for r in records]
    }

def search_plates(plate, page, page_size, db, user, plate_type=None):
    """
    Tìm kiếm các xe đã nhận diện trong cơ sở dữ liệu được cấu hình.
    """
    plate_clean = PlatePostprocessor.clean_text(plate)
    if not plate_clean:
        raise InvalidPayloadException("Vui lòng nhập ít nhất một chữ hoặc số để tìm kiếm.")

    matched = db.query(PlateHistory).filter(
        PlateHistory.owner_id == user.id,
        PlateHistory.plate_number_clean.like(f"%{plate_clean}%"),
    )
    if plate_type:
        matched = matched.filter(PlateHistory.plate_type == plate_type)
    total = matched.count()
    records = matched.order_by(PlateHistory.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "query": plate, "page": page, "page_size": page_size,
            "results": [record.to_dict() for record in records]}

def get_detection_detail(detection_id, db, user):
    """
    Xem chi tiết một lượt nhận diện trong cơ sở dữ liệu được cấu hình.
    """
    item = db.query(PlateHistory).filter(PlateHistory.id == detection_id, PlateHistory.owner_id == user.id).first()
    if not item:
        raise EntityNotFoundException("Không tìm thấy lượt nhận diện")
    return item.to_dict()


def delete_detection(detection_id, db, user):
    item = db.query(PlateHistory).filter(
        PlateHistory.id == detection_id, PlateHistory.owner_id == user.id).first()
    if item is None:
        raise EntityNotFoundException("Không tìm thấy lượt nhận diện")
    db.delete(item)
    db.commit()


def delete_history(db, user):
    count = db.query(PlateHistory).filter(PlateHistory.owner_id == user.id).delete(
        synchronize_session=False)
    db.commit()
    return count


def export_history(db, user):
    """Return owned rows in stable order for CSV serialization."""
    return db.query(PlateHistory).filter(PlateHistory.owner_id == user.id).order_by(
        PlateHistory.id.desc()).all()
