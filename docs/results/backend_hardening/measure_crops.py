"""Compare the HEAD OCR algorithm and working tree on the same detector crops.

Run from the repository root with venv/Scripts/python.exe. No cloud, DB writes,
input changes or model downloads. This measures crop OCR, not API latency.
"""

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import torch

from src.config import settings
from src.core.image.detector import LicensePlateDetector
from src.core.image.preprocessor import PlatePreprocessor
from src.core.ocr.engine import PlateOCREngine
from src.core.ocr.postprocessor import PlatePostprocessor


def old_method(source, class_name, method_name, scope):
    tree = ast.parse(source)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    method.decorator_list = []
    exec(compile(ast.unparse(method), "<HEAD baseline>", "exec"), scope)
    return scope[method_name]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    torch.set_num_threads(2)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    def source(path):
        return subprocess.check_output(["git", "show", f"{head}:{path}"], cwd=ROOT, encoding="utf-8")
    legacy_source = source("src/core/ocr_engine.py")
    legacy_preprocessor = source("src/core/preprocessor.py")
    old_dark = old_method(legacy_preprocessor, "PlatePreprocessor", "is_dark_or_blue_plate", {"cv2": cv2, "np": np})
    legacy = old_method(legacy_source, "PlateOCREngine", "_recognize_with_yolo", {
        "cv2": cv2, "np": np, "Dict": dict, "Any": object,
        "PlatePreprocessor": SimpleNamespace(is_dark_or_blue_plate=old_dark, invert_plate=PlatePreprocessor.invert_plate),
    })
    engine = PlateOCREngine("yolo")
    detector = LicensePlateDetector(settings.YOLO_MODEL_PATH)
    cases = json.loads((ROOT / "docs/results/stage5/web_cases.json").read_text(encoding="utf-8"))["cases"]
    evidence = {"head_algorithm": head, "scope": "same detected crop, CPU 2 threads, 3 interleaved repeats after warmup",
                "baseline_source_sha256": hashlib.sha256(legacy_source.encode()).hexdigest(),
                "optimized_source_sha256": sha(ROOT / "src/core/ocr/engine.py"),
                "model_sha256": {"best.pt": sha(ROOT / "models/best.pt"), "LP_ocr.pt": sha(ROOT / "models/LP_ocr.pt")}, "cases": []}
    original_predict = engine._predict_yolo_boxes
    for case in cases:
        path = ROOT / case["path"]
        image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        boxes = detector.detect(image, include_low_confidence=True)
        if not boxes:
            raise RuntimeError("No detected crop for " + case["id"])
        bbox = max(boxes, key=lambda box: box["confidence"])["bbox"]
        crop = detector.crop_plate(image, bbox)
        original_predict(crop)  # Untimed warmup; shared model for both algorithms.
        entry = {"id": case["id"], "input_sha256": sha(path), "bbox": bbox, "crop_shape": list(crop.shape), "runs": []}
        for repeat in range(3):
            for name in (["baseline", "optimized"] if repeat % 2 == 0 else ["optimized", "baseline"]):
                calls = 0
                def predict(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    return original_predict(*args, **kwargs)
                engine._predict_yolo_boxes = predict
                started = perf_counter()
                read = legacy(engine, crop) if name == "baseline" else engine.recognize_local_yolo(crop)
                elapsed = (perf_counter() - started) * 1000
                formatted = PlatePostprocessor.format_vietnamese_plate(read.get("raw_text", ""), read.get("plate_type"), read.get("text_lines"))
                entry["runs"].append({"algorithm": name, "repeat": repeat, "forward_passes": calls,
                                      "ocr_ms": round(elapsed, 3), "text": formatted, "confidence": read.get("avg_conf", 0)})
        engine._predict_yolo_boxes = original_predict
        evidence["cases"].append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
    (Path(__file__).parent / "crop_comparison.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
