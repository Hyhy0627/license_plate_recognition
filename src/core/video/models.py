"""Video plate detector and OCR adapters; lifetime is owned by services."""

from src.config import settings
from src.core.image.detector import LicensePlateDetector
from src.core.video.plate_reader import PlateReader


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

class VideoPlateOCR(PlateReader):
    """Expose the integrated plate reader through the vehicle tracker interface."""

    ninerouter_client = None

    def __init__(self, model_path, config_path):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, settings.INFERENCE_THREADS)
        options.inter_op_num_threads = 1
        super().__init__(
            ocr_model_path=model_path, ocr_config_path=config_path,
            preprocess_ocr=False, ocr_options={"sess_options": options},
        )

    def recognize_local_yolo(self, crop):
        # This method name is the existing tracker interface, not the OCR engine.
        empty = {"raw_text": "", "avg_conf": 0.0, "engine_used": "cct_vn_onnx"}
        if crop is None or crop.size == 0:
            return empty
        text, confidence, char_probs = self.run_ocr(crop)
        return {
            "raw_text": text if text and confidence >= settings.VIDEO_OCR_MIN_CONFIDENCE else "",
            "avg_conf": confidence,
            "min_char_conf": min(char_probs, default=0.0),
            "plate_type": "two_line" if crop.shape[0] / crop.shape[1] >= 0.4 else "one_line",
            "engine_used": "cct_vn_onnx",
        }
