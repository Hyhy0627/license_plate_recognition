"""Measure local video recognition with the old or new engines on one clip."""

import argparse
import json
from pathlib import Path
import sys
from threading import Lock
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.core.video.tracker import process_video


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--engine", choices=("onnx", "legacy"), default="onnx")
    parser.add_argument("--mode", choices=("fast", "detailed", "combined"), default="fast")
    parser.add_argument("--output", type=Path, default=Path("data/benchmarks/video_benchmark.json"))
    args = parser.parse_args()
    import torch
    torch.set_num_threads(max(1, settings.INFERENCE_THREADS))
    started = time.perf_counter()
    if args.engine == "onnx":
        from src.services.model_runtime import get_video_engines
        settings.VIDEO_ENGINE = "onnx"
        detector, ocr = get_video_engines()
    else:
        from src.core.image.detector import LicensePlateDetector
        from src.core.ocr.engine import PlateOCREngine
        detector = LicensePlateDetector(settings.YOLO_MODEL_PATH)
        ocr = PlateOCREngine("yolo")
    loaded = time.perf_counter()
    result = process_video(
        args.video, Path(settings.VEHICLE_MODEL_PATH), detector, ocr, Lock(), lambda _: None,
        mode=args.mode, use_remote_ocr=False,
    )
    ended = time.perf_counter()
    result.update(engine=args.engine, processing_seconds=round(ended - loaded, 3),
                  model_load_seconds=round(loaded - started, 3), total_seconds=round(ended - started, 3))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "duration", "mode", "engine", "processing_seconds", "model_load_seconds", "total_seconds",
    )}))
    print("tracks:", len(result["tracks"]), "recognized:", sum(bool(t["plate_number"]) for t in result["tracks"]))
    print("Saved:", args.output)


if __name__ == "__main__":
    main()
