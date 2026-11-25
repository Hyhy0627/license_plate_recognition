"""Private recognition image retrieval, authorized against the result owner."""

from src.core.exceptions import EntityNotFoundException

from src.db.models import PlateHistory
from src.services.storage import get_storage


def private_result_image(category, filename, user, db):
    storage = get_storage()
    try:
        url = storage.get_image_url(category, filename)
    except ValueError as exc:
        raise EntityNotFoundException("Không tìm thấy ảnh.") from exc
    field = PlateHistory.cropped_plate_url if category == "cropped_plates" else PlateHistory.annotated_image_url
    record = db.query(PlateHistory).filter(PlateHistory.owner_id == user.id, field == url).first()
    if record is None:
        raise EntityNotFoundException("Không tìm thấy ảnh.")
    try:
        return storage.get_file(category, filename)
    except FileNotFoundError as exc:
        raise EntityNotFoundException("Không tìm thấy ảnh.") from exc
