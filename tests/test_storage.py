"""Media storage preserves private URLs, byte ranges, and cleanup guarantees."""

from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from main import create_app
from src.api.auth import get_current_user
from src.core.exceptions import InvalidPayloadException, PayloadTooLargeException
from src.db.migrations import initialize_database
from src.db.models import User, VideoJob
from src.db.session import build_engine
from src.services import image_recognition, video_jobs
from src.services.storage.base import RemoteFile
from src.services.storage.local_storage import LocalStorage


@pytest.mark.parametrize("data,error", [(b"", InvalidPayloadException), (b"abcdef", PayloadTooLargeException)])
def test_rejected_video_upload_keeps_no_partial_file(tmp_path, data, error):
    storage = LocalStorage(tmp_path, tmp_path / "crops", tmp_path / "results", tmp_path)
    with pytest.raises(error):
        storage.save_video("clip.mp4", BytesIO(data), max_bytes=5)
    assert not list(tmp_path.iterdir())


def test_image_save_failure_rolls_back_and_deletes_saved_crops(tmp_path, monkeypatch):
    local = LocalStorage(tmp_path, tmp_path / "crops", tmp_path / "results", tmp_path)
    storage = Mock(wraps=local)

    def save_image(category, filename, image):
        local.save_image(category, filename, image)
        if category == "final_results":
            raise OSError("simulated write failure")

    storage.save_image.side_effect = save_image
    monkeypatch.setattr(image_recognition, "get_storage", lambda: storage)
    detector = SimpleNamespace(
        detect=lambda *a, **kw: [{"bbox": [0, 0, 80, 40], "confidence": 0.9}],
        crop_plate=lambda image, bbox: image,
    )
    ocr = SimpleNamespace(
        engine_type="yolo", recognize_local_yolo=lambda image: {"raw_text": "30A12345", "avg_conf": 0.95},
    )
    monkeypatch.setattr(image_recognition, "get_detector", lambda: detector)
    monkeypatch.setattr(image_recognition, "get_ocr_engine", lambda: ocr)
    db = Mock()
    image = cv2.imencode(".png", np.full((40, 80, 3), 127, dtype=np.uint8))[1]
    with pytest.raises(OSError, match="simulated write failure"):
        image_recognition.detect_license_plate(BytesIO(image.tobytes()), db, User(id=1))
    db.rollback.assert_called_once()
    db.commit.assert_not_called()
    assert not [item for item in tmp_path.rglob("*") if item.is_file()]


def test_remote_video_ranges_and_owner_check(tmp_path, monkeypatch):
    engine = build_engine(f"sqlite:///{(tmp_path / 'media.db').as_posix()}")
    initialize_database(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(video_jobs, "SessionLocal", sessions)
    payload = b"0123456789" * 10

    def open_media(byte_range):
        if byte_range is None:
            return BytesIO(payload)
        start, end = map(int, byte_range.removeprefix("bytes=").split("-"))
        return BytesIO(payload[start:end + 1])

    source = Mock(side_effect=open_media)
    stored = RemoteFile(len(payload), '"etag"', datetime(2026, 1, 1, tzinfo=timezone.utc), source)
    storage = Mock()
    storage.get_file.return_value = stored
    monkeypatch.setattr(video_jobs, "get_storage", lambda **kwargs: storage)
    with sessions.begin() as db:
        db.add(VideoJob(id="video", filename="clip.mp4", owner_id=41, status="completed"))

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: User(id=41)
    client = TestClient(app)
    try:
        url = "/api/video-tracking/jobs/video/media"
        full = client.get(url)
        assert full.status_code == 200 and full.content == payload
        assert full.headers["cache-control"] == "no-store"
        assert full.headers["accept-ranges"] == "bytes"
        part = client.get(url, headers={"Range": "bytes=-4", "If-Range": '"etag"'})
        assert part.status_code == 206 and part.content == payload[-4:]
        assert part.headers["content-range"] == "bytes 96-99/100"
        source.assert_called_with("bytes=96-99")
        assert client.get(url, headers={"Range": "bytes=1-2", "If-Range": '"stale"'}).content == payload

        many = client.get(url, headers={"Range": "bytes=0-1,4-5"})
        assert many.status_code == 206 and many.headers["content-type"].startswith("multipart/byteranges;")
        assert int(many.headers["content-length"]) == len(many.content)
        assert b"Content-Range: bytes 0-1/100\r\n\r\n01\r\n" in many.content
        assert b"Content-Range: bytes 4-5/100\r\n\r\n45\r\n" in many.content
        assert client.get(url, headers={"Range": "bytes=999-"}).headers["content-range"] == "bytes */100"
        assert client.get(url, headers={"Range": "bytes=999-"}).status_code == 416
        assert client.get(url, headers={"Range": "items=0-2"}).status_code == 400

        storage.reset_mock()
        app.dependency_overrides[get_current_user] = lambda: User(id=42)
        assert client.get(url).status_code == 404
        storage.get_file.assert_not_called()
    finally:
        client.close()
        engine.dispose()
