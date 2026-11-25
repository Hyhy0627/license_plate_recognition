"""Measure real HTTP metadata throughput while local image inference runs."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, asynccontextmanager, contextmanager
from datetime import datetime, timezone
from importlib.metadata import version
import json
from multiprocessing import get_context
import os
from pathlib import Path
import platform
import socket
from statistics import median
from tempfile import TemporaryDirectory
from threading import Barrier
from time import perf_counter, sleep

from src.core.models.registry import file_sha256, resolve_path
from src.evaluation.metrics import timing_stats


HISTORY = "/api/license-plates/history"
DETECT = "/api/license-plates/detect"


def _serve(listener, trial_root, threads, with_models):
    os.environ.update(
        APP_ENV="development", AUTH_COOKIE_SECURE="false", REDIS_URL="",
        DATABASE_URL=f"sqlite:///{(trial_root / 'bench.db').as_posix()}",
        STORAGE_BACKEND="local", OUTPUT_DIR=str(trial_root),
        CROPPED_PLATES_DIR=str(trial_root / "crops"),
        FINAL_RESULTS_DIR=str(trial_root / "results"),
        MODEL_RUNTIME="local", OCR_ENGINE="yolo", NINEROUTER_API_KEY="",
        INFERENCE_THREADS=str(threads), CUDA_VISIBLE_DEVICES="-1",
    )
    import uvicorn
    from main import app
    from src.api.lifespan import initialize_services
    from src.utils.logger import logger

    logger.remove()
    logger.add(str(trial_root / f"server-{os.getpid()}.log"), level="WARNING")
    if not with_models:
        @asynccontextmanager
        async def metadata_lifespan(_app):
            initialize_services()
            yield

        app.router.lifespan_context = metadata_lifespan

    uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning")).run(sockets=[listener])


@contextmanager
def _server(trial_root, threads, with_models):
    import httpx

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        process = get_context("spawn").Process(target=_serve, args=(listener, trial_root, threads, with_models))
        started = perf_counter()
        process.start()
        try:
            with httpx.Client(base_url=url, timeout=0.5, trust_env=False) as client:
                while process.is_alive() and perf_counter() - started < 60:
                    try:
                        health = client.get("/api/health")
                    except httpx.TransportError:
                        sleep(0.1)
                        continue
                    expected = 200 if with_models else 503
                    state = health.json()
                    if (health.status_code == expected and state["models_loaded"] is with_models
                            and state["database"] == "connected" and state["output_writable"]):
                        break
                    raise RuntimeError(f"Benchmark API not ready: HTTP {health.status_code} {health.text}")
                else:
                    raise RuntimeError(f"Benchmark API failed to start (process exit: {process.exitcode})")
            yield url, perf_counter() - started
        finally:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()


def _check_response(response, *, inference):
    response.raise_for_status()
    payload = response.json()
    if inference:
        if not isinstance(payload.get("results"), list) or payload.get("cloud_attempts") != 0:
            raise RuntimeError("Unexpected local inference response")
    elif not isinstance(payload.get("items"), list):
        raise RuntimeError("Unexpected history response")


def _measure(metadata_url, inference_url, cookies, image, args):
    import httpx

    metadata_clients, inference_clients = args.metadata_clients, args.inference_clients
    deadline = 0.0

    def start():
        nonlocal deadline
        deadline = perf_counter() + args.duration

    barrier = Barrier(metadata_clients + inference_clients, action=start, timeout=30)

    def client_load(url, inference):
        latencies = []
        drained = 0
        with httpx.Client(base_url=url, cookies=cookies, timeout=30, trust_env=False) as client:
            barrier.wait()
            while (started := perf_counter()) < deadline:
                response = client.post(DETECT, files=image) if inference else client.get(HISTORY)
                _check_response(response, inference=inference)
                completed = perf_counter()
                if completed <= deadline:
                    latencies.append((completed - started) * 1000)
                else:
                    drained += 1
        return latencies, drained

    with ThreadPoolExecutor(max_workers=barrier.parties) as pool:
        metadata = [pool.submit(client_load, metadata_url, False) for _ in range(metadata_clients)]
        inference = [pool.submit(client_load, inference_url, True) for _ in range(inference_clients)]
        measurements = {}
        for name, futures in (("metadata", metadata), ("inference", inference)):
            samples = []
            drained = 0
            for future in futures:
                times, count = future.result()
                samples.extend(times)
                drained += count
            if not samples:
                raise RuntimeError(f"No {name} requests finished within the window")
            measurements[name] = {
                **timing_stats(samples),
                "requests_per_second": len(samples) / args.duration,
                "completed_after_window": drained,
            }
    return measurements


def _trial(trial_root, image, args, *, colocated):
    import httpx

    with ExitStack() as servers:
        metadata_url, startup = servers.enter_context(_server(trial_root, args.threads, with_models=colocated))
        inference_url = metadata_url
        if not colocated:
            inference_url, _ = servers.enter_context(_server(trial_root, args.threads, with_models=True))
        with httpx.Client(base_url=metadata_url, timeout=30, trust_env=False) as client:
            registered = client.post("/api/auth/register", json={
                "name": "Benchmark User", "email": "benchmark@example.com", "password": "Benchmark phrase 2026",
            })
            registered.raise_for_status()
            _check_response(client.get(HISTORY), inference=False)
            # Warm up the real detector/OCR and initialize history in both arms.
            _check_response(client.post(inference_url + DETECT, files=image), inference=True)
            cookies = dict(client.cookies)
        metrics = _measure(metadata_url, inference_url, cookies, image, args)
    return {"metadata_api_startup_seconds": startup, **metrics}


def compare_api_throughput(args):
    from src.config import settings
    from src.core.models.runtime import image_ocr_model_path

    started = perf_counter()
    path = args.api_image.resolve()
    image = {"file": (path.name, path.read_bytes(), "application/octet-stream")}
    trials = {"colocated": [], "isolated": []}
    for index in range(args.repeats):
        # Alternate execution order to reduce warm-cache and thermal bias.
        order = tuple(trials) if index % 2 == 0 else tuple(reversed(trials))
        for layout in order:
            with TemporaryDirectory(prefix=f"alpr-{layout}-") as directory:
                result = _trial(Path(directory), image, args, colocated=(layout == "colocated"))
            trials[layout].append(result)
    summary = {}
    for layout, results in trials.items():
        summary[layout] = {
            name: {
                "median_requests_per_second": median(run[name]["requests_per_second"] for run in results),
                "median_p95_ms": median(run[name]["p95_ms"] for run in results),
            }
            for name in ("metadata", "inference")
        }
    report = {
        "scope": "Authenticated HTTP history with concurrent real image inference on loopback",
        "layouts": {"colocated": "one FastAPI process", "isolated": "metadata-only FastAPI + separate FastAPI for inference"},
        "duration_seconds_per_trial": args.duration,
        "elapsed_seconds": perf_counter() - started,
        "repeats": args.repeats,
        "metadata_clients": args.metadata_clients,
        "inference_clients": args.inference_clients,
        "inference_threads": args.threads,
        "device": "cpu",
        "ocr_engine": "yolo",
        "storage": "fresh SQLite and local files per trial, shared by both servers within each trial",
        "request_logging": "warning and above",
        "image": {"path": str(path), "sha256": file_sha256(path)},
        "model_sha256": {
            "detector": file_sha256(resolve_path(settings.YOLO_MODEL_PATH)),
            "ocr": file_sha256(image_ocr_model_path()),
        },
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(), "logical_cpus": os.cpu_count(),
            "cpu": os.environ.get("PROCESSOR_IDENTIFIER") or platform.processor(),
            "packages": {name: version(name) for name in ("fastapi", "uvicorn", "torch", "ultralytics")},
        },
        "trials": trials,
        "summary": summary,
    }
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = args.output_root.resolve() / f"api_throughput_{timestamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Results saved: {output}")
    return 0
