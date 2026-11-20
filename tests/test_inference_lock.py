import io
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from src.services import image_recognition as service


@pytest.mark.parametrize("has_crop", [True, False])
def test_cloud_wait_allows_another_local_read(monkeypatch, has_crop):
    waiting, release = Event(), Event()
    lock = service._inference_lock
    first = np.zeros((30, 80, 3), dtype=np.uint8)
    second = np.full_like(first, 255)

    def detect(image, **kwargs):
        assert lock.locked()
        if not image.any() and not has_crop:
            return []
        return [{"bbox": [0, 0, 80, 30], "confidence": 0.9}]

    def read(image):
        assert lock.locked()
        return {"raw_text": "30A12345" if image.any() else "", "avg_conf": .95}

    def remote_read(image):
        waiting.set()
        assert release.wait(5)
        return {}

    def unlocked(*args, **kwargs):
        assert not lock.locked()
        return True

    remote = SimpleNamespace(is_available=unlocked, recognize_plate=remote_read,
                             detect_and_recognize_plate=remote_read)
    detector = SimpleNamespace(detect=detect, crop_plate=lambda image, bbox: image)
    ocr = SimpleNamespace(ninerouter_client=remote, yolo_ocr=None, recognize_local_yolo=read)
    monkeypatch.setattr(service, "get_detector", lambda: detector)
    monkeypatch.setattr(service, "get_ocr_engine", lambda: ocr)
    monkeypatch.setattr(cv2, "imwrite", unlocked)
    decode = cv2.imdecode

    def decode_image(*args):
        unlocked()
        return decode(*args)

    monkeypatch.setattr(cv2, "imdecode", decode_image)

    def recognize(image):
        stream = io.BytesIO(cv2.imencode(".png", image)[1].tobytes())
        db = Mock(add=unlocked, commit=unlocked)
        return service.detect_license_plate(stream, db, SimpleNamespace(id=1))

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(recognize, first)
        try:
            assert waiting.wait(5)
            local = pool.submit(recognize, second).result(timeout=3)
            assert local.results[0].plate_number == "30A-123.45"
            assert not pending.done()
        finally:
            release.set()
        assert pending.result(timeout=3).cloud_attempts == 1
