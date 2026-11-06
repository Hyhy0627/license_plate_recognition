"""Regressions for truncated crops, tilt, electric plates and offline fallbacks."""
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import torch
from fastapi import UploadFile

from src.api import routes
from src.config import settings
from src.core.detector import LicensePlateDetector
from src.core.line_ocr import LocalLineOCR
from src.core.ocr_engine import PlateOCREngine
from src.core.plate_regions import quadrilateral_plate_regions
from src.core.postprocessor import PlatePostprocessor as P


class HardCaseTests(unittest.TestCase):
    def test_electric_prefix_and_leading_serial_zeros_survive(self):
        for raw, lines in [('43MD200123', ['43MD2', '00123']), ('43-MĐ2 001.23', ['43-MĐ2', '001.23'])]:
            formatted = P.format_vietnamese_plate(raw, 'two_line', lines)
            self.assertEqual(formatted, '43-MD2 001.23')
            self.assertTrue(P.validate_plate(formatted))
        self.assertFalse(P.validate_plate('43-ABC 001.23'))
        self.assertFalse(P.validate_plate('43-MD2 001234'))

    def test_deskew_must_not_drop_an_observed_digit_for_higher_mean_score(self):
        engine = PlateOCREngine.__new__(PlateOCREngine)
        engine.yolo_ocr = object()
        weak = {'raw_text': '43A123', 'chars_count': 6, 'avg_conf': .6, 'skew_angle': -4}
        complete = {'raw_text': '43A12344', 'text_lines': ['43A12344'], 'chars_count': 8, 'avg_conf': .65, 'skew_angle': -4}
        dropped = {'raw_text': '43A1234', 'text_lines': ['43A1234'], 'chars_count': 7, 'avg_conf': .95, 'skew_angle': 0}
        with patch.object(engine, '_predict_yolo_boxes', side_effect=[weak, weak, weak, complete, dropped]):
            result = engine.recognize_local_yolo(np.full((60, 240, 3), 180, np.uint8))
        self.assertEqual(result['raw_text'], '43A12344')

    def test_rotated_region_has_observed_geometry(self):
        image = np.full((240, 400, 3), 25, np.uint8)
        corners = cv2.boxPoints(((200, 120), (140, 90), 17)).astype(np.int32)
        cv2.fillConvexPoly(image, corners, (245, 245, 245))
        regions = quadrilateral_plate_regions(image)
        self.assertEqual(len(regions), 1)
        x1, y1, x2, y2 = regions[0]['bbox']
        self.assertLess(abs(x1 - int(corners[:, 0].min())), 5)
        self.assertLess(abs(y2 - int(corners[:, 1].max())), 5)
        h, w = regions[0]['crop'].shape[:2]
        self.assertAlmostEqual(w / h, 140 / 90, delta=.12)

    def test_blank_image_does_not_fabricate_a_region(self):
        self.assertEqual(quadrilateral_plate_regions(np.full((240, 400, 3), 200, np.uint8)), [])

    def test_optional_reader_missing_weights_does_not_download(self):
        with tempfile.TemporaryDirectory() as directory:
            reader = LocalLineOCR(directory)
            self.assertEqual(reader.recognize(np.full((40, 160, 3), 200, np.uint8))['raw_text'], '')
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_optional_reader_rejects_uncertain_or_nonplate_text(self):
        reader = LocalLineOCR('unused')
        reader.attempted = True
        reader.reader = MagicMock()
        for text, confidence in [('43A12345', .35), ('PARKING2026', .99)]:
            reader.reader.recognize.return_value = [(None, text, confidence)]
            self.assertEqual(reader.recognize(np.full((40, 160, 3), 200, np.uint8))['raw_text'], '')

    def test_small_neighbour_plate_is_considered_after_strong_detection(self):
        detector = LicensePlateDetector.__new__(LicensePlateDetector)
        detector.conf_threshold = .30
        def predict(**kwargs):
            boxes = [SimpleNamespace(xyxy=torch.tensor([[20., 20., 60., 45.]]), conf=torch.tensor([.8]), cls=torch.tensor([0.]))]
            if kwargs['conf'] <= .19:
                boxes.append(SimpleNamespace(xyxy=torch.tensor([[120., 20., 160., 45.]]), conf=torch.tensor([.19]), cls=torch.tensor([0.])))
            return [SimpleNamespace(boxes=boxes)]
        detector.model = SimpleNamespace(predict=predict)
        image = np.full((100, 200, 3), 180, np.uint8)
        self.assertEqual(len(detector.detect(image)), 1)
        self.assertEqual(len(detector.detect(image, include_low_confidence=True)), 2)

    def test_complete_character_crop_replaces_truncated_valid_read_without_cloud(self):
        image = np.full((100, 300, 3), 180, np.uint8)
        upload = UploadFile(filename='example.png', file=io.BytesIO(cv2.imencode('.png', image)[1].tobytes()))
        detector = MagicMock()
        detector.detect.return_value = [{'bbox': [80, 20, 190, 80], 'confidence': .8}]
        detector.crop_plate.return_value = image
        remote = MagicMock()
        remote.is_available.return_value = True
        ocr = MagicMock()
        ocr.ninerouter_client = remote
        ocr.recognize_local_yolo.side_effect = [
            {'raw_text': '43A1234', 'text_lines': ['43A1234'], 'avg_conf': .90, 'plate_type': 'one_line'},
            {'raw_text': '43A12345', 'text_lines': ['43A12345'], 'avg_conf': .89, 'plate_type': 'one_line'},
        ]
        old_crop, old_final = settings.CROPPED_PLATES_DIR, settings.FINAL_RESULTS_DIR
        try:
            with tempfile.TemporaryDirectory() as directory:
                settings.CROPPED_PLATES_DIR = settings.FINAL_RESULTS_DIR = directory
                with patch.object(routes, 'get_detector', return_value=detector), patch.object(routes, 'get_ocr_engine', return_value=ocr), patch.object(routes, '_ocr_character_regions', return_value=[{'bbox': [40, 30, 250, 75], 'confidence': .85}]):
                    response = routes.detect_license_plate(upload, MagicMock(), SimpleNamespace(id=1))
        finally:
            settings.CROPPED_PLATES_DIR, settings.FINAL_RESULTS_DIR = old_crop, old_final
        self.assertEqual([r.plate_number for r in response.results], ['43A-123.45'])
        self.assertEqual(response.cloud_attempts, 0)
        remote.recognize_plate.assert_not_called()
        remote.detect_and_recognize_plate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
