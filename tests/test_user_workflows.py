"""HTTP user journeys: real auth/database/files, controlled model outputs."""
import time
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from src.services import authentication, image_recognition, video_jobs
from src.config import settings
from src.db.migrations import initialize_database
from src.db.models import VideoJob
from src.db.session import get_db


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'workspace.db').as_posix()}")
    initialize_database(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(authentication, "rate_limiter", authentication.LoginRateLimiter())
    def database():
        with sessions() as db:
            yield db
    old_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = database
    for field in ("CROPPED_PLATES_DIR", "FINAL_RESULTS_DIR"):
        directory = tmp_path / field
        directory.mkdir()
        monkeypatch.setattr(settings, field, str(directory))
    monkeypatch.setattr(video_jobs, "UPLOAD_DIR", tmp_path / "video")
    # A real video job still runs on the worker thread; only inference is controlled.
    monkeypatch.setattr(video_jobs, "get_video_engines", lambda: (None, None))
    monkeypatch.setattr(video_jobs, "process_video", lambda *a, **kw: {
        "frames": [], "tracks": [], "mode": kw["mode"], "ninerouter": {"attempts": 0},
    })
    detector = SimpleNamespace(detect=lambda *a, **kw: [{"bbox": [20, 20, 120, 60], "confidence": .95}],
                               crop_plate=lambda image, bbox, **kw: image[20:60, 20:120])
    ocr = SimpleNamespace(yolo_ocr=None, ninerouter_client=None,
                         recognize_local_yolo=lambda image: {"raw_text": "30A12345", "avg_conf": .95, "plate_type": "one_line"})
    monkeypatch.setattr(image_recognition, "get_detector", lambda: detector)
    monkeypatch.setattr(image_recognition, "get_ocr_engine", lambda: ocr)
    clients = [TestClient(app), TestClient(app)]
    monkeypatch.setattr(video_jobs, "SessionLocal", sessions)
    try:
        yield clients
    finally:
        for client in clients:
            client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        engine.dispose()


def register(client, name="one"):
    response = client.post("/api/auth/register", json={
        "name": "Benchmark User", "email": f"{name}@example.com", "password": "Benchmark phrase 2026",
    })
    assert response.status_code == 201, response.text


def image_bytes():
    return cv2.imencode(".png", np.full((100, 200, 3), 120, np.uint8))[1].tobytes()


def test_full_image_history_logout_journey(workspace):
    owner, other = workspace
    register(owner)
    register(other, "two")
    for _ in range(3):
        response = owner.post("/api/license-plates/detect", files={"file": ("car.png", image_bytes(), "image/png")})
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["plate_number"] == "30A-123.45"
    crop = response.json()["results"][0]["cropped_image_url"]
    history = owner.get("/api/license-plates/history?page=2&page_size=2").json()
    assert history["total"] == 3 and len(history["items"]) == 1
    record_id = history["items"][0]["id"]
    assert owner.get("/api/license-plates/search?plate=30a12345").json()["total"] == 3
    assert owner.get("/api/license-plates/search?plate=99Z99999").json()["total"] == 0
    assert owner.get(f"/api/license-plates/{record_id}").status_code == 200
    assert owner.get(crop).status_code == 200
    assert other.get(crop).status_code == 404
    assert other.get(f"/api/license-plates/{record_id}").status_code == 404
    assert other.get("/api/license-plates/history").json()["total"] == 0
    assert owner.post("/api/auth/logout").status_code == 200
    assert owner.get("/api/license-plates/history").status_code == 401


@pytest.mark.parametrize("payload,status", [(b"", 400), (b"broken-image", 400), (b"x" * (10 * 1024 * 1024 + 1), 413)])
def test_invalid_images_do_not_create_history(workspace, payload, status):
    client, _ = workspace
    register(client)
    assert client.post("/api/license-plates/detect", files={"file": ("bad.jpg", payload, "image/jpeg")}).status_code == status
    assert client.get("/api/license-plates/history").json()["total"] == 0


@pytest.mark.parametrize("url", ["history?page=0", "history?page_size=101", "search?plate=", "search?plate=x&page=-1"])
def test_invalid_history_pagination(workspace, url):
    client, _ = workspace
    register(client)
    assert client.get("/api/license-plates/" + url).status_code == 422


def test_video_upload_poll_media_owner_and_missing_job(workspace):
    client, other = workspace
    register(client)
    register(other, "two")
    payload = b"benchmark-video"
    response = client.post("/api/video-tracking/jobs", files={"file": ("clip.mp4", payload, "video/mp4")})
    assert response.status_code == 202
    job_id = response.json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/video-tracking/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            break
        time.sleep(.01)
    assert job["status"] == "completed", job
    assert job["result"]["mode"] == "fast"
    assert job["result"]["ninerouter"]["attempts"] == 0
    media_url = f"/api/video-tracking/jobs/{job_id}/media"
    assert client.get(media_url, headers={"Range": "bytes=0-3"}).content == payload[:4]
    assert other.get(media_url).status_code == 404
    assert other.get(f"/api/video-tracking/jobs/{job_id}").status_code == 404
    assert client.get("/api/video-tracking/jobs/missing").status_code == 404


@pytest.mark.parametrize("name,payload,status", [("clip.exe", b"x", 400), ("clip.mp4", b"", 400)])
def test_video_input_validation(workspace, name, payload, status):
    client, _ = workspace
    register(client)
    assert client.post("/api/video-tracking/jobs", files={"file": (name, payload)}).status_code == status


def test_failed_video_and_queue_capacity(workspace, monkeypatch):
    client, _ = workspace
    register(client)
    def fail(*args, **kwargs):
        raise ValueError("Video không hợp lệ")
    monkeypatch.setattr(video_jobs, "process_video", fail)
    # Synchronous execution isolates job error handling from scheduling timing.
    with patch.object(video_jobs._executor, "submit", side_effect=lambda fn, *args: fn(*args)):
        response = client.post("/api/video-tracking/jobs", files={"file": ("bad.mp4", b"bad")})
    job_id = response.json()["id"]
    job = client.get(f"/api/video-tracking/jobs/{job_id}").json()
    assert job["status"] == "failed" and "không hợp lệ" in job["error"]
    monkeypatch.setattr(video_jobs, "MAX_UPLOAD_BYTES", 4)
    assert client.post("/api/video-tracking/jobs", files={"file": ("big.mp4", b"12345")}).status_code == 413
    with video_jobs.SessionLocal() as db:
        assert db.query(VideoJob).filter_by(status="queued").count() == 0
    with patch.object(video_jobs._executor, "submit"):
        for _ in range(2):
            assert client.post("/api/video-tracking/jobs", files={"file": ("clip.mp4", b"123")}).status_code == 202
        assert client.post("/api/video-tracking/jobs", files={"file": ("clip.mp4", b"123")}).status_code == 429
