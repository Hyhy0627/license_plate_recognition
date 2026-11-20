"""The video adapter must preserve RGB and per-character OCR confidence."""

from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from src.core.video_models import VideoPlateOCR, get_video_engines


def make_ocr(prediction):
    ocr = VideoPlateOCR.__new__(VideoPlateOCR)
    class Recognizer:
        def run(self, image, **kwargs):
            assert image[0, 0].tolist() == [30, 20, 10]
            assert kwargs == {"return_confidence": True, "remove_pad_char": False}
            return [prediction]
    ocr.recognizer = Recognizer()
    return ocr


def test_rgb_conversion_and_padding_does_not_inflate_confidence():
    prediction = SimpleNamespace(plate="30A12345_", char_probs=np.array([0.8] * 8 + [1.0]))
    result = make_ocr(prediction).recognize_local_yolo(np.full((20, 80, 3), [10, 20, 30], dtype=np.uint8))
    assert result["raw_text"] == "30A12345"
    assert result["avg_conf"] == pytest.approx(0.8)
    assert result["plate_type"] == "one_line"


def test_uncertain_text_and_empty_crops_are_not_accepted():
    prediction = SimpleNamespace(plate="30A12345_", char_probs=np.array([0.4] * 8 + [1.0]))
    ocr = make_ocr(prediction)
    assert ocr.recognize_local_yolo(np.full((20, 80, 3), [10, 20, 30], dtype=np.uint8))["raw_text"] == ""
    assert ocr.recognize_local_yolo(None)["raw_text"] == ""
    assert ocr.recognize_local_yolo(np.empty((0, 0, 3), dtype=np.uint8))["raw_text"] == ""


def test_missing_models_explain_setup_without_silently_switching_engine(tmp_path):
    get_video_engines.cache_clear()
    try:
        with patch("src.core.video_models.settings.VIDEO_ENGINE", "onnx"), \
             patch("src.core.video_models.settings.VIDEO_PLATE_MODEL_PATH", str(tmp_path / "missing.pt")):
            with pytest.raises(ValueError, match="setup_video_models.py"):
                get_video_engines()
    finally:
        get_video_engines.cache_clear()
