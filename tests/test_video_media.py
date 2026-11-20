"""Uploaded video remains seekable and private while its job is available."""

import io
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from src.db.migrations import initialize_database
from src.services import video_jobs
from src.api.auth import get_current_user
from src.db.models import User, VideoJob


def test_video_media_range_and_owner_isolation(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'jobs.db').as_posix()}")
    initialize_database(engine)
    monkeypatch.setattr(video_jobs, "SessionLocal", sessionmaker(bind=engine))
    payload = b"0123456789" * 100
    app.dependency_overrides[get_current_user] = lambda: User(id=41)
    client = TestClient(app)
    job_id = None
    try:
        with patch.object(video_jobs, "UPLOAD_DIR", tmp_path), \
             patch.object(video_jobs, "process_video", return_value={"frames": [], "tracks": []}) as process, \
             patch.object(video_jobs, "get_video_engines", return_value=(None, None)), \
             patch.object(video_jobs, "get_detector", return_value=None), \
             patch.object(video_jobs, "get_ocr_engine", return_value=None):
            response = client.post("/api/video-tracking/jobs", files={"file": ("clip.mp4", io.BytesIO(payload), "video/mp4")})
            assert response.status_code == 202
            job_id = response.json()["id"]
            for _ in range(100):
                if client.get(f"/api/video-tracking/jobs/{job_id}").json()["status"] == "completed":
                    break
                time.sleep(0.01)
            assert process.call_args.kwargs["mode"] == "fast"
            assert process.call_args.kwargs["use_remote_ocr"] is False
            media = client.get(f"/api/video-tracking/jobs/{job_id}/media", headers={"Range": "bytes=10-19"})
            assert media.headers["accept-ranges"] == "bytes"
            assert media.status_code == 206
            assert media.content == payload[10:20]
            assert media.headers["content-range"] == f"bytes 10-19/{len(payload)}"
            assert media.headers["cache-control"] == "no-store"
            assert (tmp_path / f"{job_id}.mp4").is_file()

            # Read from disk using a newly opened database connection.
            engine.dispose()
            assert client.get(f"/api/video-tracking/jobs/{job_id}").json()["result"]["tracks"] == []
            url = f"/api/video-tracking/jobs/{job_id}/media"
            assert client.get(url).content == payload
            assert client.get(url, headers={"Range": "bytes=-4"}).content == payload[-4:]
            assert client.get(url, headers={"Range": "bytes=1000-"}).status_code == 416

            app.dependency_overrides[get_current_user] = lambda: User(id=42)
            assert client.get(f"/api/video-tracking/jobs/{job_id}/media").status_code == 404
            app.dependency_overrides.clear()
            assert client.get(f"/api/video-tracking/jobs/{job_id}/media").status_code == 401
    finally:
        app.dependency_overrides.clear()
        client.close()
        engine.dispose()


def test_interrupted_worker_releases_queue_slot(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'restart.db').as_posix()}")
    initialize_database(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(video_jobs, "SessionLocal", sessions)
    monkeypatch.setattr(video_jobs, "UPLOAD_DIR", tmp_path)
    with sessions.begin() as db:
        for job_id in ("stopped", "live"):
            db.add(VideoJob(id=job_id, filename="video.mp4", owner_id=41, status="running", progress=45))
    owner = User(id=41)
    try:
        with video_jobs._job_lock("live"):
            video_jobs._reserve_job("next", owner.id, "next.mp4", "fast")
            assert video_jobs.get_video_job("live", owner)["status"] == "running"
            interrupted = video_jobs.get_video_job("stopped", owner)
            assert interrupted["status"] == "failed" and interrupted["progress"] == 45
    finally:
        engine.dispose()
