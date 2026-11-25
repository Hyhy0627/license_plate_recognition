"""Factory contract for plate detector and OCR adapters."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from src.config import settings
from src.core.models.registry import default_path, resolve_path

if TYPE_CHECKING:
    from src.core.image.detector import LicensePlateDetector
    from src.core.ocr.engine import PlateOCREngine
    from src.core.video.models import VideoPlateOCR


MODEL_SETUP_HINT = "Chạy scripts/download_models.py hoặc scripts/setup_video_models.py."


class ModelRuntime(Protocol):
    """Build adapters with the detector and OCR capabilities used by ALPR services."""

    def image_detector(self) -> LicensePlateDetector: ...

    def image_ocr(self) -> PlateOCREngine: ...

    def video_engines(self) -> tuple[LicensePlateDetector, VideoPlateOCR]: ...


def image_ocr_model_path() -> Path:
    configured = resolve_path(settings.OCR_MODEL_PATH)
    if configured == default_path("image-ocr") and not configured.is_file():
        legacy = resolve_path("script/copy/models/LP_ocr.pt")
        if legacy.is_file():
            return legacy
    return configured


def sequence_model_paths() -> tuple[Path, Path]:
    paths = resolve_path(settings.VIDEO_OCR_MODEL_PATH), resolve_path(settings.VIDEO_OCR_CONFIG_PATH)
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Thiếu model OCR CCT: {path}. {MODEL_SETUP_HINT}")
    return paths


class LocalModelRuntime:
    """Create local Ultralytics and ONNX adapters on demand."""

    def image_detector(self) -> LicensePlateDetector:
        from src.core.image.detector import LicensePlateDetector

        path = resolve_path(settings.YOLO_MODEL_PATH)
        if not path.is_file():
            raise RuntimeError(f"Không nạp được model phát hiện biển số: {path}. Chạy scripts/download_models.py.")
        return LicensePlateDetector(model_path=str(path))

    def image_ocr(self) -> PlateOCREngine:
        from src.core.ocr.engine import PlateOCREngine

        return PlateOCREngine(engine_type=settings.OCR_ENGINE)

    def video_engines(self) -> tuple[LicensePlateDetector, VideoPlateOCR]:
        from src.core.video.models import VideoPlateDetector, VideoPlateOCR

        detector_path = resolve_path(settings.VIDEO_PLATE_MODEL_PATH)
        if not detector_path.is_file():
            raise ValueError(f"Thiếu model video: {detector_path}. {MODEL_SETUP_HINT}")
        ocr_paths = sequence_model_paths()
        detector = VideoPlateDetector(str(detector_path), conf_threshold=0.25)
        if detector.model is None:
            raise ValueError("Không nạp được model phát hiện biển số video.")
        return detector, VideoPlateOCR(*ocr_paths)


def create_model_runtime(backend: str = "local") -> ModelRuntime:
    if backend == "local":
        return LocalModelRuntime()
    raise ValueError(f"Unsupported model runtime: {backend}")
