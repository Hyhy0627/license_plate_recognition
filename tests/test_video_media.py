"""Uploaded video remains seekable and private while its job is available."""

import io
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from src.api import video_routes
from src.api.auth import get_current_user
from src.db.models import User


def test_video_media_range_and_owner_isolation(tmp_path):
    payload = b"0123456789" * 100
    app.dependency_overrides[get_current_user] = lambda: User(id=41)
    client = TestClient(app)
    job_id = None
    try:
        with patch.object(video_routes, "UPLOAD_DIR", tmp_path), \
             patch.object(video_routes, "process_video", return_value={"frames": [], "tracks": []}) as process, \
             patch.object(video_routes, "get_video_engines", return_value=(None, None)), \
             patch.object(video_routes, "get_detector", return_value=None), \
             patch.object(video_routes, "get_ocr_engine", return_value=None):
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
            assert media.status_code == 206
            assert media.content == payload[10:20]
            assert media.headers["content-range"] == f"bytes 10-19/{len(payload)}"
            assert media.headers["cache-control"] == "no-store"
            assert (tmp_path / f"{job_id}.mp4").is_file()

            app.dependency_overrides[get_current_user] = lambda: User(id=42)
            assert client.get(f"/api/video-tracking/jobs/{job_id}/media").status_code == 404
            app.dependency_overrides.clear()
            assert client.get(f"/api/video-tracking/jobs/{job_id}/media").status_code == 401
    finally:
        app.dependency_overrides.clear()
        client.close()
        if job_id:
            video_routes._jobs.pop(job_id, None)
