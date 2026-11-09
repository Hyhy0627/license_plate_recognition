"""Read-only evidence loading for the notebooks; never starts the API or cloud OCR."""
from collections import Counter
import json
import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from tool.check_regression import signature
from tool.benchmark import load_annotations, sha256, summarize


ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_image(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Missing input image: {path}")
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot decode image: {path}")
    return image


def checked_crop(image, bbox):
    h, w = image.shape[:2]
    if len(bbox) != 4 or not all(math.isfinite(v) for v in bbox):
        raise ValueError(f"Invalid bbox: {bbox}")
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h):
        raise ValueError(f"BBox outside image: {bbox}, image={w}x{h}")
    crop = image[math.floor(y1):math.ceil(y2), math.floor(x1):math.ceil(x2)]
    if not crop.size:
        raise ValueError(f"Empty crop: {bbox}")
    return crop


def load_synthetic_samples():
    dataset = ROOT / "data/test_cases"
    samples, _ = load_annotations(dataset, dataset / "ground_truth.json")
    for sample in samples:
        sample["kind"] = "synthetic"
        image = read_image(sample["path"])
        for target in sample["truth"]:
            checked_crop(image, target["bbox"])
    return samples


def load_development_cases(path):
    cases = read_json(path)["cases"]
    ids = [c["id"] for c in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("Cases must be nonempty and have unique IDs")
    for case in cases:
        if sha256(Path(case["path"])) != case["sha256"]:
            raise ValueError(f"Image changed since labeling: {case['id']}")
        read_image(case["path"])
    return cases


def image_inventory(samples, cohort):
    rows = []
    for sample in samples:
        image = read_image(sample["path"])
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        rows.append({
            "id": sample.get("id", sample.get("file")), "cohort": cohort,
            "kind": sample["kind"], "category": sample.get("category", sample.get("condition", "unspecified")),
            "path": str(sample["path"]), "sha256": sha256(Path(sample["path"])),
            "width": image.shape[1], "height": image.shape[0],
            "plates": len(sample.get("truth", sample.get("expected", []))),
            "mean_gray": float(gray.mean()),
            "laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        })
    return pd.DataFrame(rows)


def assert_equivalent(actual, expected, location="metrics"):
    """Reject edited KPI summaries instead of silently plotting them as measured."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or actual.keys() != expected.keys():
            raise ValueError(f"Metric keys differ: {location}")
        for key in expected:
            assert_equivalent(actual[key], expected[key], f"{location}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"Metric length differs: {location}")
        for i, (a, b) in enumerate(zip(actual, expected)):
            assert_equivalent(a, b, f"{location}[{i}]")
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(f"Metric value differs: {location}")
    elif actual != expected:
        raise ValueError(f"Metric value differs: {location}")


def hash_status(hashes, base=ROOT):
    rows = []
    for name, expected in hashes.items():
        path = Path(base) / name
        status = "missing" if not path.is_file() else ("same" if sha256(path) == expected else "changed")
        rows.append({"file": name, "status": status})
    return pd.DataFrame(rows, columns=["file", "status"])


def load_benchmark(run):
    run = Path(run)
    report = read_json(run / "metrics.json")
    records = read_json(run / "predictions.json")
    manifest = report["manifest"]
    if report["schema_version"] != 1 or not records or len(records) != manifest["evaluated_images"]:
        raise ValueError("Incomplete or unsupported benchmark evidence")
    if manifest["scope"] != "offline_local_detector_yolo_ocr_postprocessor" or manifest["iou_threshold"] != 0.5:
        raise ValueError("Unsupported benchmark protocol")
    files = [r["file"] for r in records]
    if len(files) != len(set(files)) or set(files) != set(manifest["image_sha256"]):
        raise ValueError("Benchmark image list differs from manifest")
    current = summarize(records, manifest["operating_confidence"])
    assert_equivalent(current, report["overall"])
    categories = {c: summarize([r for r in records if r["category"] == c], manifest["operating_confidence"])
                  for c in sorted({r["category"] for r in records})}
    assert_equivalent(categories, report["by_category"])
    return report, records


def regression_frame(result_path, cases_path):
    """Rescore frozen expected labels, preserving prefix/serial grouping and duplicates."""
    report = read_json(result_path)
    cases = load_development_cases(cases_path)
    truth = {c["id"]: c for c in cases}
    outputs = report["cases"]
    if len(outputs) != len(truth) or {c["id"] for c in outputs} != set(truth):
        raise ValueError("Incomplete regression run or duplicate IDs")
    rows = []
    for case in outputs:
        frozen = truth[case["id"]]
        for field in ("sha256", "expected", "kind"):
            if case[field] != frozen[field]:
                raise ValueError(f"Frozen {field} changed: {case['id']}")
        if case.get("input_sha256", case["sha256"]) != frozen["sha256"]:
            raise ValueError(f"Uploaded input differs: {case['id']}")
        response = case.get("response", {})
        actual = [r["plate_number"] for r in response.get("results", [])]
        exact = (case.get("http_status") == 200 and response.get("success") is True
                 and Counter(map(signature, actual)) == Counter(map(signature, frozen["expected"])))
        logged = case.get("exact_grouping", case.get("exact"))
        if logged is not None and logged != exact:
            raise ValueError(f"Logged verdict differs from recomputed verdict: {case['id']}")
        rows.append({"id": case["id"], "kind": case["kind"], "sha256": case["sha256"],
                     "expected": case["expected"], "actual": actual, "exact": exact,
                     "wall_ms": case["wall_ms"], "cloud_attempts": response.get("cloud_attempts"),
                     "engines": [r.get("engine_used") for r in response.get("results", [])]})
    return report, pd.DataFrame(rows)


def compare_regressions(before_report, before, after_report, after):
    for field in ("mode", "transport"):
        if before_report.get(field) != after_report.get(field):
            raise ValueError(f"Cannot pool different protocols: {field}")
    paired = before.merge(after, on="id", suffixes=("_before", "_after"), validate="one_to_one")
    if paired.empty:
        raise ValueError("No common frozen cases to compare")
    for field in ("sha256", "expected", "kind"):
        if not all(a == b for a, b in zip(paired[f"{field}_before"], paired[f"{field}_after"])):
            raise ValueError(f"Cannot compare changed {field}")
    return paired
