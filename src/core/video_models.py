"""Local video models from ddkhoa2605/LicensePlateDetection.

Keep these separate from the image recognition engines. Models are loaded once
per server process; the caller serializes inference with the existing lock.
"""

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from src.config import BASE_DIR, settings
from src.core.image.detector import LicensePlateDetector


def _model_path(value):
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


class VideoPlateDetector(LicensePlateDetector):
    """One YOLO11n pass at a fixed resolution, without threshold retries."""

    def detect(self, image, include_low_confidence=False):
        if image is None or image.size == 0:
            return []
        height, width = image.shape[:2]
        predictions = self.model.predict(
            image, conf=self.conf_threshold, imgsz=640, iou=0.45, verbose=False,
        )
        return self._filter_boxes(predictions, image, width, height, width / 2, height / 2)


class VideoPlateOCR:
    """Adapt Fast Plate OCR 1.1 predictions to the existing video pipeline."""

    ninerouter_client = None

    def __init__(self, model_path, config_path):
        import onnxruntime as ort
        from fast_plate_ocr import LicensePlateRecognizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, settings.INFERENCE_THREADS)
        options.inter_op_num_threads = 1
        self.recognizer = LicensePlateRecognizer(
            onnx_model_path=str(model_path), plate_config_path=str(config_path),
            device="auto", sess_options=options,
        )

    def recognize_local_yolo(self, crop):
        # This method name is the existing tracker interface, not the OCR engine.
        empty = {"raw_text": "", "avg_conf": 0.0, "engine_used": "cct_vn_onnx"}
        if crop is None or crop.size == 0:
            return empty
        # OpenCV is BGR; fast-plate-ocr expects RGB for in-memory colour images.
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        predictions = self.recognizer.run(rgb, return_confidence=True, remove_pad_char=False)
        if not predictions:
            return empty
        prediction = predictions[0]
        # Confidence for '_' padding must not inflate the text confidence.
        indices = [index for index, char in enumerate(prediction.plate) if char != "_"]
        text = prediction.plate.replace("_", "")
        probabilities = prediction.char_probs
        confidence = float(np.mean(np.asarray(probabilities)[indices])) if indices and probabilities is not None else 0.0
        return {
            "raw_text": text if confidence >= settings.VIDEO_OCR_MIN_CONFIDENCE else "",
            "avg_conf": confidence,
            "plate_type": "two_line" if crop.shape[0] / crop.shape[1] >= 0.4 else "one_line",
            "engine_used": "cct_vn_onnx",
        }


@lru_cache(maxsize=1)
def get_video_engines():
    if settings.VIDEO_ENGINE == "legacy":
        from src.api.routes import get_detector, get_ocr_engine
        return get_detector(), get_ocr_engine()
    if settings.VIDEO_ENGINE != "onnx":
        raise ValueError("VIDEO_ENGINE phải là onnx hoặc legacy.")
    paths = [_model_path(value) for value in (
        settings.VIDEO_PLATE_MODEL_PATH, settings.VIDEO_OCR_MODEL_PATH, settings.VIDEO_OCR_CONFIG_PATH,
    )]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ValueError("Thiếu model video. Chạy python tool/setup_video_models.py. Tệp thiếu: " + ", ".join(missing))
    detector = VideoPlateDetector(str(paths[0]), conf_threshold=0.25)
    if detector.model is None:
        raise ValueError("Không nạp được model phát hiện biển số video.")
    return detector, VideoPlateOCR(paths[1], paths[2])
