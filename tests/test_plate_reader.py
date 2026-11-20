"""Exercise the integrated reader without loading models or Streamlit."""

import numpy as np
import pytest

from src.core.video.plate_reader import PlateReader


def test_character_votes_use_multiple_reads_and_confidence():
    reader = PlateReader()
    reader.track_buffer[7] = [
        ("30A12345", [0.8] * 8, 0, 0.9),
        ("30A12845", [0.99] * 8, 1, 0.9),
        ("30A12345", [0.8] * 8, 2, 0.9),
    ]
    text, confidence = reader.vote_plate(7)
    assert text == "30A12345"
    assert 0 < confidence <= 1


def test_finalization_keeps_single_read_and_releases_track_state():
    reader = PlateReader()
    reader.track_buffer[7].append(("30A12345", [0.8] * 8, 12, 0.9))
    reader.track_best_image[7] = np.zeros((30, 90, 3), dtype=np.uint8)
    assert reader.vote_plate(7) == (None, 0.0)
    result = reader.finalize_all_tracks(image_budget_remaining=1)
    assert result[0]["plate"] == "30A12345"
    assert result[0]["ocr_confidence"] == pytest.approx(0.8)
    assert result[0]["read_count"] == 1
    assert result[0]["image"].shape == (30, 90, 3)
    assert not reader.track_buffer
    assert not reader.track_best_image


def test_crop_padding_stays_inside_frame_and_readers_have_separate_buffers():
    frame = np.ones((50, 100, 3), dtype=np.uint8)
    assert PlateReader.crop_with_padding(frame, (0, 0, 99, 49)).shape == frame.shape
    first, second = PlateReader(), PlateReader()
    first.track_buffer[1].append(("30A12345", [0.8] * 8, 0, 0.9))
    assert not second.track_buffer
