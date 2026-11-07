import io
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import cv2
import numpy as np
from fastapi import UploadFile

from src.core.postprocessor import PlatePostprocessor as P
from src.core.ocr_engine import PlateOCREngine
from src.core.ninerouter_vision import NineRouterVisionClient
from src.api import routes
from src.config import settings


class FormatTests(unittest.TestCase):
    def test_four_digit_motorcycle_keeps_ocr_row_boundary(self):
        for raw, lines, expected in [("54H45555", ["54H4", "5555"], "54-H4 5555"),
                                     ("54L43939", ["54L4", "3939"], "54-L4 3939"),
                                     ("54H45555", ["54H", "45555"], "54H 455.55")]:
            self.assertEqual(P.format_vietnamese_plate(raw, "two_line", lines), expected)
            self.assertTrue(P.validate_plate(expected))

    def test_no_character_is_deleted_to_force_validity(self):
        for text in ["29LD123456", "88GC133343"]:
            result = P.format_vietnamese_plate(text)
            self.assertEqual(P.clean_text(result), text)
            self.assertFalse(P.validate_plate(result))

    def test_two_letter_series_and_known_formats(self):
        for text, expected in [("29LD12345", "29LD-123.45"), ("29LD1234", "29LD-1234"), ("30A12345", "30A-123.45"), ("59G277777", "59-G2 777.77")]:
            self.assertEqual(P.format_vietnamese_plate(text), expected)
            self.assertTrue(P.validate_plate(expected))

    def test_inconsistent_or_extra_rows_are_not_accepted(self):
        for lines in [["54H", "4555"], ["54", "H4", "5555"], ["54H45", "555"]]:
            self.assertEqual(P.format_vietnamese_plate("54H45555", "two_line", lines), "")
        self.assertFalse(P.validate_plate("54-H4 55.55"))

    def test_valid_variant_beats_longer_junk(self):
        good = {"raw_text": "88G133343", "text_lines": ["88G1", "33343"], "chars_count": 9, "avg_conf": .8}
        junk = {"raw_text": "88GC133343", "text_lines": ["88GC1", "33343"], "chars_count": 10, "avg_conf": .9}
        self.assertGreater(PlateOCREngine._result_quality(good), PlateOCREngine._result_quality(junk))

    def test_missing_cloud_confidence_is_not_fabricated(self):
        client = NineRouterVisionClient()
        result = client._parse_model_output('{"raw_text":"54H45555","text_lines":["54H4","5555"]}')
        self.assertEqual(result["confidence"], 0)
        self.assertEqual(result["text_lines"], ["54H4", "5555"])


class CloudBudgetTests(unittest.TestCase):
    def run_detection(self, detected_boxes, remote_result):
        image = np.full((100, 200, 3), 127, dtype=np.uint8)
        upload = UploadFile(filename="test.png", file=io.BytesIO(cv2.imencode(".png", image)[1].tobytes()))
        remote = MagicMock()
        remote.is_available.return_value = True
        remote.recognize_plate.return_value = remote_result
        remote.detect_and_recognize_plate.return_value = remote_result
        detector = MagicMock()
        detector.detect.return_value = [{"bbox": [5, 5, 50, 50], "confidence": .9}] * detected_boxes
        detector.crop_plate.return_value = image
        ocr = MagicMock()
        ocr.ninerouter_client = remote
        ocr.yolo_ocr = None
        ocr.recognize_local_yolo.return_value = {"raw_text": "", "avg_conf": 0}
        original = settings.FINAL_RESULTS_DIR
        try:
            with tempfile.TemporaryDirectory() as directory, patch.object(routes, "get_detector", return_value=detector), patch.object(routes, "get_ocr_engine", return_value=ocr):
                settings.FINAL_RESULTS_DIR = directory
                response = routes.detect_license_plate(upload, MagicMock(), SimpleNamespace(id=1))
        finally:
            settings.FINAL_RESULTS_DIR = original
        return response, remote

    def test_crop_timeout_does_not_trigger_second_full_image_call(self):
        response, remote = self.run_detection(2, {"raw_text": "", "error": "timeout"})
        self.assertEqual(remote.recognize_plate.call_count, 1)
        self.assertEqual(remote.detect_and_recognize_plate.call_count, 0)
        self.assertEqual(response.cloud_attempts, 1)
        self.assertTrue(response.warnings)

    def test_full_image_timeout_is_visible(self):
        response, remote = self.run_detection(0, {"raw_text": "", "error": "timeout"})
        self.assertEqual(remote.detect_and_recognize_plate.call_count, 1)
        self.assertTrue(response.warnings)

    def test_missing_cloud_bbox_is_not_invented(self):
        response, _ = self.run_detection(0, {"raw_text": "30A12345", "confidence": .95})
        self.assertEqual(response.total_detected, 0)


if __name__ == "__main__":
    unittest.main()
