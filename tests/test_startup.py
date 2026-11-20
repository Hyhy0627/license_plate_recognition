"""The API must not report healthy when required recognition models are unavailable."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app


class StartupTests(unittest.TestCase):
    def test_missing_detector_stops_startup(self):
        with patch("main.initialize_database"), patch("src.services.model_runtime.get_detector", return_value=SimpleNamespace(model=None)):
            with self.assertRaisesRegex(RuntimeError, "model phát hiện biển số"):
                with TestClient(app):
                    pass

    def test_missing_ocr_stops_startup(self):
        detector = SimpleNamespace(model=object())
        with patch("main.initialize_database"), patch("src.services.model_runtime.get_detector", return_value=detector), \
                patch("src.services.model_runtime.get_ocr_engine", return_value=SimpleNamespace(yolo_ocr=None)):
            with self.assertRaisesRegex(RuntimeError, "model OCR"):
                with TestClient(app):
                    pass

    def test_loaded_models_allow_health_response(self):
        detector = SimpleNamespace(model=object())
        ocr = SimpleNamespace(yolo_ocr=object())
        with patch("main.initialize_database"), patch("src.services.model_runtime.get_detector", return_value=detector), \
                patch("src.services.model_runtime.get_ocr_engine", return_value=ocr):
            with TestClient(app) as client:
                self.assertEqual(client.get("/").json()["status"], "online")


if __name__ == "__main__":
    unittest.main()


def test_request_headers_include_errors():
    from uuid import UUID
    client = TestClient(app)
    response = client.get("/")
    assert UUID(response.headers["X-Request-ID"]).version == 4
    assert float(response.headers["X-Process-Time"]) >= 0
    response = client.get("/api/auth/me", headers={"X-Request-ID": "review-15"})
    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == "review-15"


def test_sequence_model_allows_startup_without_character_yolo():
    detector = SimpleNamespace(model=object())
    ocr = SimpleNamespace(yolo_ocr=None, sequence_ocr=SimpleNamespace(recognizer=object()))
    with patch("main.initialize_database"), patch("src.services.model_runtime.get_detector", return_value=detector), \
            patch("src.services.model_runtime.get_ocr_engine", return_value=ocr):
        with TestClient(app) as client:
            assert client.get("/").status_code == 200


def test_deep_health_checks_each_component(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError
    import main
    client = TestClient(app)
    engine = create_engine(f"sqlite:///{(tmp_path / 'health.db').as_posix()}")
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main.settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main.model_runtime, "_detector", SimpleNamespace(model=object()))
    monkeypatch.setattr(main.model_runtime, "_ocr_engine", SimpleNamespace(yolo_ocr=object()))
    try:
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert (body["status"], body["database"], body["models_loaded"], body["output_writable"]) == (
            "healthy", "connected", True, True)
        assert not list(tmp_path.glob(".health-*"))
        with patch.object(engine, "connect", side_effect=OperationalError("", (), Exception())):
            response = client.get("/api/health")
            assert response.status_code == 503 and response.json()["database"] == "unavailable"
        monkeypatch.setattr(main.model_runtime, "_ocr_engine", None)
        response = client.get("/api/health")
        assert response.status_code == 503 and not response.json()["models_loaded"]
        monkeypatch.setattr(main.model_runtime, "_ocr_engine", SimpleNamespace(yolo_ocr=object()))
        monkeypatch.setattr(main.settings, "OUTPUT_DIR", str(tmp_path / "missing"))
        response = client.get("/api/health")
        assert response.status_code == 503 and not response.json()["output_writable"]
    finally:
        client.close()
        engine.dispose()
