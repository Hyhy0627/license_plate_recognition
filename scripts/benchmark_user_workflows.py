"""Repeat real-model HTTP journeys in an isolated database and output directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
from importlib.metadata import version
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image", type=Path, default=ROOT / "tests/fixtures/test_cases/blurred/blur_01.jpg")
    parser.add_argument("--video", type=Path)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--video-timeout", type=float, default=180)
    args = parser.parse_args()
    if args.iterations < 1 or args.video_timeout <= 0:
        parser.error("iterations and video-timeout must be positive")
    assets = [args.image] + ([args.video] if args.video else [])
    for path in assets:
        if not path.is_file():
            parser.error(f"Missing fixture: {path}")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Environment overrides .env before importing the application.
    os.environ.update(DATABASE_URL=f"sqlite:///{(out / 'isolated.db').as_posix()}",
                      OCR_ENGINE="yolo", VIDEO_ENGINE="onnx",
                      OUTPUT_DIR=str(out), CROPPED_PLATES_DIR=str(out / "cropped"),
                      FINAL_RESULTS_DIR=str(out / "annotated"))
    from fastapi.testclient import TestClient
    from main import app
    from src.services import video_jobs
    from src.config import settings
    from src.core.models.registry import resolve_path
    from src.core.models.runtime import image_ocr_model_path
    import torch
    video_jobs.UPLOAD_DIR = out / "video_jobs"
    observations = []
    report = {"scope": "real models + HTTP TestClient; local OCR only; no browser/network latency",
              "accuracy": None, "accuracy_note": "No ground truth asserted; use scripts/benchmark.py for labeled accuracy.",
              "environment": {"python": sys.version, "platform": platform.platform()},
              "fixtures": [{"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in assets]}
    report["environment"].update(cpu=platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
                                  cuda_available=torch.cuda.is_available(), inference_threads=settings.INFERENCE_THREADS,
                                  packages={name: version(name) for name in ("torch", "ultralytics", "onnxruntime", "fast-plate-ocr")})
    report["model_sha256"] = {}
    for value in (settings.YOLO_MODEL_PATH, image_ocr_model_path(), settings.VIDEO_PLATE_MODEL_PATH, settings.VIDEO_OCR_MODEL_PATH):
        model = resolve_path(value)
        if model.is_file():
            report["model_sha256"][model.name] = hashlib.sha256(model.read_bytes()).hexdigest()
    def request(client, name, method, path, expected=200, **kwargs):
        started = time.perf_counter()
        response = client.request(method, path, **kwargs)
        observations.append({"name": name, "ms": (time.perf_counter() - started) * 1000,
                             "status": response.status_code, "passed": response.status_code == expected})
        if response.status_code != expected:
            raise RuntimeError(f"{name}: expected HTTP {expected}, received {response.status_code}")
        return response
    code = 0
    try:
        started = time.perf_counter()
        with TestClient(app) as client:
            report["startup_ms"] = (time.perf_counter() - started) * 1000
            credentials = {"email": f"benchmark-{time.time_ns()}@example.com", "password": "Benchmark phrase 2026"}
            request(client, "register", "POST", "/api/auth/register", 201, json={**credentials, "name": "Benchmark User"})
            for iteration in range(args.iterations):
                request(client, "session", "GET", "/api/auth/me")
                with args.image.open("rb") as image:
                    result = request(client, "image_detect_cold" if iteration == 0 else "image_detect_warm", "POST",
                                     "/api/license-plates/detect", files={"file": (args.image.name, image, "image/jpeg")}).json()
                assert isinstance(result["results"], list) and result["cloud_attempts"] == 0
                history = request(client, "history", "GET", "/api/license-plates/history").json()
                request(client, "search", "GET", "/api/license-plates/search?plate=30")
                if history["items"]:
                    item = history["items"][0]
                    request(client, "detail", "GET", f"/api/license-plates/{item['id']}")
                    if item["cropped_plate_url"]:
                        request(client, "crop_media", "GET", item["cropped_plate_url"])
                request(client, "logout", "POST", "/api/auth/logout")
                request(client, "login", "POST", "/api/auth/login", json=credentials)
            if args.video:
                started = time.perf_counter()
                with args.video.open("rb") as video:
                    created = request(client, "video_upload", "POST", "/api/video-tracking/jobs", 202,
                                      files={"file": (args.video.name, video, "video/mp4")}).json()
                job_id = created["id"]
                deadline = time.monotonic() + args.video_timeout
                while time.monotonic() < deadline:
                    job = request(client, "video_poll", "GET", f"/api/video-tracking/jobs/{job_id}").json()
                    if job["status"] in {"completed", "failed"}:
                        break
                    time.sleep(.25)
                if job["status"] != "completed":
                    raise RuntimeError(f"Video not completed: {job['status']}; {job.get('error', '')}")
                result = job["result"]
                assert result["ninerouter"]["attempts"] == 0
                report["video"] = {"total_seconds": time.perf_counter() - started,
                                   "processing_seconds": result["processing_seconds"], "duration": result["duration"],
                                   "processing_to_duration_ratio": result["processing_seconds"] / result["duration"],
                                   "tracks": len(result["tracks"]), "accuracy": None}
                request(client, "video_range", "GET", f"/api/video-tracking/jobs/{job_id}/media", 206,
                        headers={"Range": "bytes=0-31"})
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        code = 1
    finally:
        report["passed"] = code == 0
        report["observations"] = observations
        stats = {}
        for name in sorted({item["name"] for item in observations}):
            times = sorted(item["ms"] for item in observations if item["name"] == name)
            stats[name] = {"n": len(times), "mean_ms": statistics.mean(times), "p50_ms": statistics.median(times),
                           "p95_ms": times[max(0, __import__('math').ceil(.95 * len(times)) - 1)], "max_ms": max(times)}
        report["timings"] = stats
        (out / "real_models.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "requests": len(observations), "report": str(out / 'real_models.json')}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
