"""Exercise the actual video's metadata guard before loading inference models."""
from threading import Lock
from unittest.mock import patch

import cv2
import pytest

from src.core.video_tracker import process_video


@pytest.mark.parametrize("fps,count,width,height,error", [
    (0, 30, 640, 360, "thiếu thông tin"),
    (30, 0, 640, 360, "thiếu thông tin"),
    (30, 30 * 46, 640, 360, "dài quá"),
    (30, 30, 3840, 2160, "Full HD"),
])
def test_video_metadata_limits(tmp_path, fps, count, width, height, error):
    weight = tmp_path / "vehicle.pt"
    weight.touch()
    class Capture:
        released = False
        def isOpened(self):
            return True
        def get(self, prop):
            return {cv2.CAP_PROP_FPS: fps, cv2.CAP_PROP_FRAME_COUNT: count,
                    cv2.CAP_PROP_FRAME_WIDTH: width, cv2.CAP_PROP_FRAME_HEIGHT: height}[prop]
        def release(self):
            self.released = True
    capture = Capture()
    with patch("src.core.video_tracker.cv2.VideoCapture", return_value=capture):
        with pytest.raises(ValueError, match=error):
            process_video(tmp_path / "clip.mp4", weight, None, None, Lock(), lambda _: None)
    assert capture.released


def test_video_missing_vehicle_weights_and_invalid_mode(tmp_path):
    for mode, expected in [("fast", "Thiếu model"), ("unsupported", "không hợp lệ")]:
        with pytest.raises(ValueError, match=expected):
            process_video(tmp_path / "clip.mp4", tmp_path / "missing.pt", None, None, Lock(), lambda _: None, mode=mode)
