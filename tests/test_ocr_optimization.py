"""Inference budget, input polarity, and image CCT compatibility regressions."""

import io
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from src.config import settings
from src.core.ocr.engine import PlateOCREngine
from src.core.image.preprocessor import PlatePreprocessor
from src.services import image_recognition, model_runtime


@pytest.mark.parametrize("grayscale", [False, True])
def test_dark_vehicle_padding_does_not_invert_a_white_plate(grayscale):
    crop = np.full((80, 240, 3), 20, np.uint8)
    crop[10:-10, 10:-10] = 220
    cv2.putText(crop, "30A12345", (25, 50), cv2.FONT_HERSHEY_SIMPLEX, .6, (20, 20, 20), 1)
    if grayscale:
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    assert not PlatePreprocessor.is_dark_or_blue_plate(crop)
    assert PlatePreprocessor.is_dark_or_blue_plate(np.full_like(crop, 30))


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("height", [30, 40, 80])
def test_clear_plate_uses_one_pass_and_only_upscales_small_crops(monkeypatch, dark, height):
    engine = PlateOCREngine.__new__(PlateOCREngine)
    engine.yolo_ocr = object()
    image = np.full((height, height * 4, 3), 180, np.uint8)
    monkeypatch.setattr("src.core.ocr.engine.PlatePreprocessor.is_dark_or_blue_plate", lambda _: dark)
    predict = Mock(return_value={"raw_text": "30A12345", "avg_conf": .9,
                                 "chars_count": 8, "skew_angle": 10})
    monkeypatch.setattr(engine, "_predict_yolo_boxes", predict)
    result = engine.recognize_local_yolo(image)
    assert result["raw_text"] == "30A12345"
    assert result["forward_passes"] == 1
    assert predict.call_count == 1
    observed = predict.call_args.args[0]
    assert observed.shape[0] == (60 if height == 30 else height)
    assert np.all(observed == (75 if dark else 180))


def test_invalid_first_read_uses_retry_but_valid_retry_stops(monkeypatch):
    engine = PlateOCREngine.__new__(PlateOCREngine)
    engine.yolo_ocr = object()
    predict = Mock(side_effect=[{"raw_text": "", "avg_conf": 0},
                               {"raw_text": "30A12345", "avg_conf": .8, "skew_angle": 10, "chars_count": 8}])
    monkeypatch.setattr(engine, "_predict_yolo_boxes", predict)
    assert engine.recognize_local_yolo(np.full((60, 240, 3), 180, np.uint8))["raw_text"] == "30A12345"
    assert [call.kwargs["conf"] for call in predict.call_args_list] == [.20, .12]


@pytest.mark.parametrize("kind", ["onnx", "cct"])
def test_image_sequence_engine_does_not_require_yolo(monkeypatch, tmp_path, kind):
    model, config = tmp_path / "ocr.onnx", tmp_path / "ocr.yaml"
    model.touch()
    config.touch()
    monkeypatch.setattr(settings, "VIDEO_OCR_MODEL_PATH", str(model))
    monkeypatch.setattr(settings, "VIDEO_OCR_CONFIG_PATH", str(config))
    adapter = SimpleNamespace(recognizer=object(), recognize_local_yolo=Mock(return_value={
        "raw_text": "30A12345", "avg_conf": .91, "engine_used": "cct_vn_onnx"}))
    factory = Mock(return_value=adapter)
    monkeypatch.setattr("src.core.video.models.VideoPlateOCR", factory)
    engine = PlateOCREngine(kind)
    assert engine.yolo_ocr is None
    assert engine.ninerouter_client is None
    assert model_runtime.ocr_model_loaded(engine)
    assert engine.recognize_plate(np.ones((40, 160, 3), np.uint8))["engine_used"] == "cct_vn_onnx"
    factory.assert_called_once_with(model, config)


def test_image_sequence_engine_missing_model_fails_explicitly(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "VIDEO_OCR_MODEL_PATH", str(tmp_path / "missing.onnx"))
    with pytest.raises(ValueError, match="setup_video_models.py"):
        PlateOCREngine("onnx")


@pytest.mark.parametrize("text,layout,weakest,full_scene,expected", [
    ("30A12345", "one_line", .94, False, "cct_vn_onnx"),
    ("59G277777", "two_line", .94, False, "cct_vn_onnx"),
    ("30A12345", "one_line", .52, False, "local_yolo"),
    ("54H45555", "two_line", .99, False, "local_yolo"),
    ("29MD10016", "two_line", .99, False, "local_yolo"),
    ("3OA12345", "one_line", .99, False, "local_yolo"),
    ("30A12345", "one_line", .99, True, "local_yolo"),
])
def test_fastplate_verifies_uncertain_crops_and_skips_scene_inference(
        monkeypatch, text, layout, weakest, full_scene, expected):
    monkeypatch.setattr(PlateOCREngine, "_init_ocr", lambda self: None)
    engine = PlateOCREngine("fastplate")
    predict = Mock(return_value={"raw_text": text, "plate_type": layout, "avg_conf": .98,
                                 "min_char_conf": weakest, "engine_used": "cct_vn_onnx"})
    engine.sequence_ocr = SimpleNamespace(recognize_local_yolo=predict)
    fallback = Mock(return_value={"raw_text": "54H45555", "text_lines": ["54H4", "5555"],
                                  "engine_used": "local_yolo"})
    monkeypatch.setattr(engine, "_recognize_with_yolo", fallback)
    crop = np.full((50, 180, 3), 200, np.uint8)
    read = engine.recognize_local_yolo(crop, full_scene=True) if full_scene else engine.recognize_plate(crop)
    assert read["engine_used"] == expected
    assert predict.call_count == (0 if full_scene else 1)
    assert fallback.call_count == (1 if expected == "local_yolo" else 0)


@pytest.mark.parametrize("engine_name", ["local_yolo", "cct_vn_onnx"])
def test_confident_detection_skips_expensive_service_fallbacks(monkeypatch, tmp_path, engine_name):
    image = np.full((60, 240, 3), 180, np.uint8)
    detector = SimpleNamespace(detect=lambda *a, **kw: [{"bbox": [0, 0, 240, 60], "confidence": .8}],
                               crop_plate=lambda *a, **kw: image)
    read = Mock(return_value={"raw_text": "30A12345", "avg_conf": .9, "engine_used": engine_name})
    ocr = SimpleNamespace(yolo_ocr=object(), ninerouter_client=None, recognize_local_yolo=read)
    monkeypatch.setattr(image_recognition, "get_detector", lambda: detector)
    monkeypatch.setattr(image_recognition, "get_ocr_engine", lambda: ocr)
    fallback = Mock(side_effect=AssertionError("clear detection should skip fallback"))
    monkeypatch.setattr(image_recognition, "_ocr_character_regions", fallback)
    monkeypatch.setattr(image_recognition, "quadrilateral_plate_regions", fallback)
    monkeypatch.setattr(settings, "CROPPED_PLATES_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "FINAL_RESULTS_DIR", str(tmp_path))
    db = Mock()
    response = image_recognition.detect_license_plate(
        io.BytesIO(cv2.imencode(".png", image)[1].tobytes()), db, SimpleNamespace(id=1))
    assert response.results[0].engine_used == engine_name
    assert response.results[0].confidence == .9
    assert db.add.call_args.args[0].plate_number_clean == "30A12345"
    read.assert_called_once()
    fallback.assert_not_called()


def test_one_clear_plate_does_not_skip_rescue_for_an_unreadable_neighbour(monkeypatch, tmp_path):
    image = np.full((60, 240, 3), 180, np.uint8)
    detector = SimpleNamespace(detect=lambda *a, **kw: [
        {"bbox": [0, 0, 100, 60], "confidence": .9}, {"bbox": [120, 0, 240, 60], "confidence": .3}],
        crop_plate=lambda *a, **kw: image)
    ocr = SimpleNamespace(yolo_ocr=object(), ninerouter_client=None, recognize_local_yolo=Mock(side_effect=[
        {"raw_text": "30A12345", "avg_conf": .9}, {"raw_text": "59G2", "avg_conf": .9},
        {"raw_text": "59G277777", "avg_conf": .9}]))
    proposal = Mock(return_value=[{"bbox": [120, 0, 240, 60], "confidence": .9}])
    monkeypatch.setattr(image_recognition, "get_detector", lambda: detector)
    monkeypatch.setattr(image_recognition, "get_ocr_engine", lambda: ocr)
    monkeypatch.setattr(image_recognition, "_ocr_character_regions", proposal)
    monkeypatch.setattr(settings, "CROPPED_PLATES_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "FINAL_RESULTS_DIR", str(tmp_path))
    response = image_recognition.detect_license_plate(
        io.BytesIO(cv2.imencode(".png", image)[1].tobytes()), Mock(), SimpleNamespace(id=1))
    assert {item.plate_number for item in response.results} == {"30A-123.45", "59-G2 777.77"}
    proposal.assert_called_once()
