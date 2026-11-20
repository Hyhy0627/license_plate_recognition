"""Shared image/video model factories and one inference lock per process."""

from functools import lru_cache
from pathlib import Path
from threading import Lock

from src.config import BASE_DIR, settings
from src.core.image.detector import LicensePlateDetector
from src.core.ocr.engine import PlateOCREngine
from src.core.video.models import VideoPlateDetector, VideoPlateOCR


_detector = None
_ocr_engine = None
_inference_lock = Lock()


def image_models_loaded() -> bool:
    return (getattr(_detector, "model", None) is not None
            and ocr_model_loaded(_ocr_engine))


def ocr_model_loaded(ocr) -> bool:
    return (getattr(ocr, "yolo_ocr", None) is not None
            or getattr(getattr(ocr, "sequence_ocr", None), "recognizer", None) is not None)


def get_detector() -> LicensePlateDetector:
    global _detector
    if _detector is None:
        _detector = LicensePlateDetector(model_path=settings.YOLO_MODEL_PATH)
    return _detector

def get_ocr_engine() -> PlateOCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PlateOCREngine(engine_type=settings.OCR_ENGINE)
    return _ocr_engine

def _model_path(value):
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path

@lru_cache(maxsize=1)
def get_video_engines():
    if settings.VIDEO_ENGINE == "legacy":
        return get_detector(), get_ocr_engine()
    if settings.VIDEO_ENGINE != "onnx":
        raise ValueError("VIDEO_ENGINE phải là onnx hoặc legacy.")
    paths = [_model_path(value) for value in (
        settings.VIDEO_PLATE_MODEL_PATH, settings.VIDEO_OCR_MODEL_PATH, settings.VIDEO_OCR_CONFIG_PATH,
    )]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ValueError("Thiếu model video. Chạy python scripts/setup_video_models.py. Tệp thiếu: " + ", ".join(missing))
    detector = VideoPlateDetector(str(paths[0]), conf_threshold=0.25)
    if detector.model is None:
        raise ValueError("Không nạp được model phát hiện biển số video.")
    return detector, VideoPlateOCR(paths[1], paths[2])
