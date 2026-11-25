"""Shared image/video model factories and one inference lock per process."""

from functools import lru_cache
from threading import Lock

from src.config import settings
from src.core.models.runtime import create_model_runtime


_detector = None
_ocr_engine = None
_inference_lock = Lock()
_load_lock = Lock()
_runtime = create_model_runtime(settings.MODEL_RUNTIME)


def image_models_loaded() -> bool:
    return (getattr(_detector, "model", None) is not None
            and ocr_model_loaded(_ocr_engine))


def ocr_model_loaded(ocr) -> bool:
    return (getattr(ocr, "yolo_ocr", None) is not None
            or getattr(getattr(ocr, "sequence_ocr", None), "recognizer", None) is not None)


def get_detector():
    global _detector
    if _detector is None:
        with _load_lock:
            if _detector is None:
                _detector = _runtime.image_detector()
    return _detector


def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        with _load_lock:
            if _ocr_engine is None:
                _ocr_engine = _runtime.image_ocr()
    return _ocr_engine


@lru_cache(maxsize=1)
def get_video_engines():
    if settings.VIDEO_ENGINE == "legacy":
        return get_detector(), get_ocr_engine()
    if settings.VIDEO_ENGINE != "onnx":
        raise ValueError("VIDEO_ENGINE phải là onnx hoặc legacy.")
    return _runtime.video_engines()
