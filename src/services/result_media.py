"""Private recognition image retrieval, authorized against the result owner."""

from pathlib import Path
from src.core.exceptions import EntityNotFoundException

from src.config import settings
from src.db.models import PlateHistory


def private_result_image(category, filename, user, db):
    if category not in {"cropped_plates", "final_results"} or Path(filename).name != filename or "\\" in filename:
        raise EntityNotFoundException("Không tìm thấy ảnh.")
    url = f"/static/{category}/{filename}"
    field = PlateHistory.cropped_plate_url if category == "cropped_plates" else PlateHistory.annotated_image_url
    record = db.query(PlateHistory).filter(PlateHistory.owner_id == user.id, field == url).first()
    if record is None:
        raise EntityNotFoundException("Không tìm thấy ảnh.")
    root = Path(settings.CROPPED_PLATES_DIR if category == "cropped_plates" else settings.FINAL_RESULTS_DIR).resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise EntityNotFoundException("Không tìm thấy ảnh.")
    return path
