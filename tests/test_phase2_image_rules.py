"""Regressions for plate candidates and conservative OCR formatting."""

from types import SimpleNamespace

import cv2
import numpy as np
import torch

from src.core.image.detector import LicensePlateDetector
from src.core.image.preprocessor import PlatePreprocessor
from src.core.ocr.postprocessor import PlatePostprocessor


def _filter(image, bbox, confidence=0.9):
    detector = LicensePlateDetector.__new__(LicensePlateDetector)
    box = SimpleNamespace(
        xyxy=torch.tensor([bbox], dtype=torch.float32),
        conf=torch.tensor([confidence]),
        cls=torch.tensor([0]),
    )
    h, w = image.shape[:2]
    return detector._filter_boxes(
        [SimpleNamespace(boxes=[box])], image, w, h, w / 2, h / 2
    )


def test_large_confident_plate_candidate_survives():
    image = np.full((100, 200, 3), 220, np.uint8)
    assert len(_filter(image, [15, 15, 185, 85])) == 1
    assert _filter(image, [15, 15, 185, 85], confidence=0.4) == []


def test_red_plate_with_white_characters_survives_but_flat_red_region_does_not():
    image = np.zeros((100, 220, 3), np.uint8)
    image[:] = (0, 0, 220)
    cv2.putText(image, "59A12345", (20, 60), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 255, 255), 2)
    assert len(_filter(image, [15, 15, 205, 85])) == 1
    flat = np.full_like(image, (0, 0, 220))
    assert _filter(flat, [15, 15, 205, 85]) == []


def test_two_line_split_uses_visible_gap():
    image = np.full((100, 180, 3), 245, np.uint8)
    cv2.putText(image, "59-A1", (22, 34), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (10, 10, 10), 2)
    cv2.putText(image, "123.45", (12, 84), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (10, 10, 10), 2)
    top, bottom = PlatePreprocessor.split_two_line_plate(image)
    assert 35 <= top.shape[0] <= 65
    assert top.shape[0] + bottom.shape[0] == image.shape[0]


def test_deskew_uses_character_pixels_instead_of_bright_background():
    image = np.full((80, 240), 255, np.uint8)
    cv2.putText(image, "30A12345", (15, 52), cv2.FONT_HERSHEY_SIMPLEX, 1, 0, 2)
    rotated = cv2.warpAffine(image, cv2.getRotationMatrix2D((120, 40), 12, 1),
                             (240, 80), borderValue=255)
    corrected = PlatePreprocessor.deskew_plate(rotated)
    assert np.mean(rotated != corrected) > 0.05
    assert PlatePreprocessor.deskew_plate(np.full_like(image, 255)).shape == image.shape


def test_yellow_plate_keeps_dark_text_polarity():
    image = np.full((60, 180, 3), (0, 200, 220), np.uint8)
    cv2.putText(image, "30A12345", (10, 40), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (0, 0, 0), 2)
    assert not PlatePreprocessor.is_dark_or_blue_plate(image)


def test_ocr_correction_requires_confidence_and_never_invents_missing_chars():
    process = PlatePostprocessor
    low = process.format_vietnamese_plate("3OA12345", confidence=0.6)
    high = process.format_vietnamese_plate("3OA12345", confidence=0.9)
    assert process.clean_text(low) == "3OA12345"
    assert not process.validate_plate(low)
    assert high == "30A-123.45"
    assert process.clean_text(process.format_vietnamese_plate("59G2", confidence=0.99)) == "59G2"
    assert process.is_known_registration_prefix("41A12345")
    assert process.is_known_registration_prefix("80A12345")
    assert not process.is_known_registration_prefix("13A12345")
