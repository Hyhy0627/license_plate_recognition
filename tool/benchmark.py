"""Read-only evaluation of existing labeled images. See tool/BENCHMARK.md.

Default scope: offline local detector + local YOLO OCR + postprocessor.
No cloud calls, no API/database writes, no regenerated datasets or notebooks.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluation.metrics import (
    detection_metrics, normalize_text, text_metrics, timing_stats,
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_annotations(dataset, ground_truth):
    """Accept legacy {file: {bbox, clean_text}} or {metadata, images: {file: {plates}}}."""
    dataset = Path(dataset).resolve()
    ground_truth = Path(ground_truth)
    raw = json.loads(ground_truth.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Ground truth must be a JSON object")
    metadata = raw.get("metadata", {}) if "images" in raw else {}
    entries = raw.get("images", raw)
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Ground truth must contain a nonempty image mapping")
    samples = []
    for name, item in sorted(entries.items()):
        if not isinstance(name, str) or not isinstance(item, dict):
            raise ValueError("Each image needs a relative path and an annotation object")
        path = (dataset / name).resolve()
        if not path.is_relative_to(dataset) or not path.is_file():
            raise ValueError(f"Missing image or unsafe relative path: {name}")
        plates = item.get("plates")
        if plates is None:
            plates = [{"bbox": item.get("bbox"), "text": item.get("clean_text", item.get("plate_number", ""))}]
        if not isinstance(plates, list):
            raise ValueError(f"plates must be a list: {name}")
        truth = []
        for plate in plates:
            if not isinstance(plate, dict):
                raise ValueError(f"Each plate must be an object: {name}")
            bbox = plate.get("bbox")
            text = normalize_text(plate.get("text", plate.get("clean_text", plate.get("plate_number", ""))))
            if not text or not isinstance(bbox, list) or len(bbox) != 4:
                raise ValueError(f"Invalid plate annotation: {name}")
            bbox = [float(value) for value in bbox]
            if not all(math.isfinite(value) for value in bbox) or not (0 <= bbox[0] < bbox[2] and 0 <= bbox[1] < bbox[3]):
                raise ValueError(f"Invalid bounding box: {name}")
            truth.append({"bbox": bbox, "text": text})
        samples.append({"file": name, "path": path, "category": str(item.get("category", "unspecified")), "truth": truth})
    return samples, metadata


def collect_records(samples, detector, ocr, operating_threshold, warmup):
    import cv2
    from src.core.postprocessor import PlatePostprocessor

    def read_image(sample):
        import numpy as np
        # imdecode + fromfile also supports Unicode Windows paths.
        image = cv2.imdecode(np.fromfile(sample["path"], dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot decode image: {sample['file']}")
        h, w = image.shape[:2]
        for plate in sample["truth"]:
            if plate["bbox"][2] > w or plate["bbox"][3] > h:
                raise ValueError(f"Ground truth box is outside the image: {sample['file']}")
        return image

    def recognize(image, bbox, score):
        crop = detector.crop_plate(image, bbox)
        if crop is None or not crop.size:
            raise ValueError("Detector returned an empty crop")
        result = ocr.recognize_local_yolo(crop)
        raw = str(result.get("raw_text", ""))
        text = PlatePostprocessor.format_vietnamese_plate(
            normalize_text(raw), plate_type=result.get("plate_type"), text_lines=result.get("text_lines"))
        return {"bbox": list(bbox), "score": score, "raw_text": raw, "text": text,
                "valid_format": PlatePostprocessor.validate_plate(text),
                "ocr_confidence": float(result.get("avg_conf", 0.0)),
                "engine": result.get("engine_used", "local_yolo")}

    warmup_start = perf_counter()
    if warmup:
        image = read_image(samples[0])
        for _ in range(warmup):
            detector.detect(image)
            # Whole-image warmup does not read a ground-truth box.
            ocr.recognize_local_yolo(image)
    warmup_ms = (perf_counter() - warmup_start) * 1000
    records = []
    for index, sample in enumerate(samples, 1):
        image = read_image(sample)
        # Timed local end-to-end scope starts after image decoding, before detection.
        started = perf_counter()
        detections = detector.detect(image)
        detection_ms = (perf_counter() - started) * 1000
        for item in detections:
            if not math.isfinite(float(item["confidence"])) or not 0 <= item["confidence"] <= 1:
                raise ValueError("Detector confidence must be finite and between 0 and 1")
        candidates = [recognize(image, item["bbox"], float(item["confidence"]))
                      for item in detections if item["confidence"] >= operating_threshold]
        pipeline_ms = (perf_counter() - started) * 1000
        predictions = [item for item in candidates if item["valid_format"]]
        # Oracle OCR is a separate experiment. These crops NEVER enter predictions.
        oracle_start = perf_counter()
        oracle = [recognize(image, target["bbox"], 1.0) for target in sample["truth"]]
        oracle_ms = (perf_counter() - oracle_start) * 1000
        records.append({"file": sample["file"], "category": sample["category"],
                        "truth": sample["truth"],
                        "detections": [{"bbox": item["bbox"], "score": float(item["confidence"]),
                                        "class_id": item.get("class_id")} for item in detections],
                        "candidates": candidates, "predictions": predictions, "oracle": oracle,
                        "timing_ms": {"detection": detection_ms,
                                      "predicted_crop_ocr_and_postprocessing": pipeline_ms - detection_ms,
                                      "pipeline": pipeline_ms, "gt_crop_ocr": oracle_ms}})
        print(f"[{index}/{len(samples)}] {sample['file']}: {len(predictions)}/{len(sample['truth'])} output/GT plates, {pipeline_ms:.1f} ms", flush=True)
    return records, warmup_ms


def summarize(records, threshold):
    return {"images": len(records),
            "detection": detection_metrics(records, score_threshold=threshold),
            "local_end_to_end": text_metrics(records),
            "ground_truth_crop_ocr_raw": text_metrics(records, "oracle", "raw_text"),
            "ground_truth_crop_ocr_formatted": text_metrics(records, "oracle", "text"),
            "timing": {name: timing_stats([record["timing_ms"][name] for record in records])
                       for name in ("detection", "predicted_crop_ocr_and_postprocessing", "pipeline", "gt_crop_ocr")}}


def export_figures(summary, categories, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    detection = summary["detection"]
    curve = detection["pr_curve"]
    fig, ax = plt.subplots(figsize=(7, 5))
    if curve and detection["ap50"] is not None:
        ax.step([point["recall"] for point in curve], [point["precision"] for point in curve], where="post")
        ax.set_title(f"Measured PR at IoU 0.50 | AP50 = {detection['ap50']:.4f}")
    else:
        ax.text(0.5, 0.5, "No predictions / no ground-truth positives", ha="center")
        ax.set_title("Measured detection PR")
    ax.set(xlabel="Recall", ylabel="Precision", xlim=(0, 1), ylim=(0, 1.02))
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output / "pr_curve.png", dpi=160)
    plt.close(fig)

    names = list(categories)
    fig, ax = plt.subplots(figsize=(9, 5))
    detection_values = [categories[name]["detection"]["recall"] for name in names]
    exact_values = [categories[name]["local_end_to_end"]["exact_plate_recall"] for name in names]
    positions = list(range(len(names)))
    bars_detection = ax.bar([x - 0.18 for x in positions], [v if v is not None else 0 for v in detection_values], width=0.36, label="Detection recall")
    bars_exact = ax.bar([x + 0.18 for x in positions], [v if v is not None else 0 for v in exact_values], width=0.36, label="Local E2E exact plate recall")
    ax.bar_label(bars_detection, labels=[f"{v:.1%}" if v is not None else "N/A" for v in detection_values], padding=3)
    ax.bar_label(bars_exact, labels=[f"{v:.1%}" if v is not None else "N/A" for v in exact_values], padding=3)
    for x, det, exact in zip(positions, detection_values, exact_values):
        if det is None or exact is None:
            ax.text(x, 0.02, "N/A: no GT plates", ha="center", fontsize=8, rotation=90)
    ax.set_xticks(positions, names)
    ax.set(ylim=(0, 1.1), ylabel="Ratio", title="Measured results by category")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "category_metrics.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    parts = ("detection", "predicted_crop_ocr_and_postprocessing")
    values = [summary["timing"][part]["mean_ms"] for part in parts]
    ax.barh(["Local pipeline"], [values[0]], label="Detection")
    ax.barh(["Local pipeline"], [values[1]], left=[values[0]], label="Crop + OCR + formatting")
    ax.set(xlabel="Measured mean milliseconds per image", title="Local pipeline latency (excludes GT-crop experiment)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "latency_breakdown.png", dpi=160)
    plt.close(fig)


def save_outputs(output, manifest, records, summary, categories, plots):
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "manifest": manifest, "overall": summary, "by_category": categories}
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    (output / "predictions.json").write_text(json.dumps(records, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    with (output / "per_image.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=["file", "category", "gt_plates", "detections", "output_plates", "exact_plate_matches", "pipeline_ms", "gt_crop_ocr_ms"])
        writer.writeheader()
        for record in records:
            metrics = text_metrics([record])
            writer.writerow({"file": record["file"], "category": record["category"],
                             "gt_plates": len(record["truth"]), "detections": len(record["detections"]),
                             "output_plates": len(record["predictions"]), "exact_plate_matches": metrics["exact_plate_matches"],
                             "pipeline_ms": record["timing_ms"]["pipeline"], "gt_crop_ocr_ms": record["timing_ms"]["gt_crop_ocr"]})
    if plots:
        export_figures(summary, categories, output)

    def ratio(value):
        return f"{value * 100:.2f}%" if value is not None else "N/A"

    d, e, t = summary["detection"], summary["local_end_to_end"], summary["timing"]["pipeline"]
    rows = ["# Measured local ALPR benchmark", "", f"Run: {manifest['run_id']}",
            f"Dataset kind: {manifest['dataset_kind']}. Images: {len(records)}.", "",
            "Scope: local detector + local YOLO OCR + formatting. This is NOT an HTTP/web or hybrid-cloud benchmark.",
            "Image decoding, model loading, warmup, disk/DB writes, HTTP, and GT-crop OCR are excluded from local pipeline latency.", "",
            "| Metric | Measured value |", "|---|---:|",
            f"| Detection AP50 (101-point) | {ratio(d['ap50'])} |",
            f"| Detection precision / recall | {ratio(d['precision'])} / {ratio(d['recall'])} |",
            f"| Detection TP / FP / FN | {d['tp']} / {d['fp']} / {d['fn']} |",
            f"| Local E2E exact plate recall | {ratio(e['exact_plate_recall'])} |",
            f"| Local E2E exact image accuracy | {ratio(e['exact_image_accuracy'])} |",
            f"| Local E2E CER (includes misses and extra plates) | {ratio(e['cer'])} |",
            f"| GT-crop raw OCR exact recall | {ratio(summary['ground_truth_crop_ocr_raw']['exact_plate_recall'])} |",
            f"| GT-crop formatted OCR exact recall | {ratio(summary['ground_truth_crop_ocr_formatted']['exact_plate_recall'])} |",
            f"| Local pipeline mean / p50 / p95 ms | {t['mean_ms']:.2f} / {t['p50_ms']:.2f} / {t['p95_ms']:.2f} |", "",
            "Ratios use 0..1 in JSON. CER may exceed 100% if insertion errors outnumber reference characters.",
            "No claimed targets are automatically marked as passed. No ablation claim is made without separate measured variants.",
            "Synthetic/unspecified data cannot establish accuracy on real traffic photos.", "",
            "Raw evidence: predictions.json, per_image.csv, metrics.json (model/data/source hashes and metric conventions)."]
    (output / "REPORT.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/test_cases")
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--dataset-kind", choices=["synthetic", "real", "unspecified"], default="unspecified")
    parser.add_argument("--model", type=Path, default=ROOT / "models/best.pt")
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/benchmarks")
    parser.add_argument("--confidence", type=float, default=0.30, help="Operating threshold for local pipeline and reported P/R")
    parser.add_argument("--ap-min-confidence", type=float, default=0.01, help="Collect low-score boxes for AP; AP is conditional on these proposals and detector filters")
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--limit", type=int, help="Smoke test only; report includes selected sample count")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    if not (0 < args.ap_min_confidence <= args.confidence <= 1) or args.warmup < 0 or args.threads < 1 or (args.limit is not None and args.limit < 1):
        parser.error("Require 0 < AP minimum <= operating confidence <= 1, warmup >= 0, threads >= 1, limit >= 1")
    dataset = args.dataset.resolve()
    ground_truth = (args.ground_truth or dataset / "ground_truth.json").resolve()
    model_path = args.model.resolve()
    if not model_path.is_file():
        parser.error(f"Missing local model: {model_path}")
    samples, dataset_metadata = load_annotations(dataset, ground_truth)
    full_count = len(samples)
    if args.limit:
        samples = samples[:args.limit]

    import cv2
    import torch
    import ultralytics
    from src.core.detector import LicensePlateDetector
    from src.core.ocr_engine import PlateOCREngine
    torch.set_num_threads(args.threads)
    started = perf_counter()
    detector = LicensePlateDetector(str(model_path), conf_threshold=args.ap_min_confidence)
    ocr = PlateOCREngine(engine_type="yolo")
    if detector.model is None or ocr.yolo_ocr is None:
        raise RuntimeError("Required local detector/OCR weights failed to load; refusing an empty success report")
    detector.model.to("cpu")
    ocr.yolo_ocr.to("cpu")
    load_ms = (perf_counter() - started) * 1000
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    run_started = perf_counter()
    records, warmup_ms = collect_records(samples, detector, ocr, args.confidence, args.warmup)
    elapsed_ms = (perf_counter() - run_started) * 1000
    summary = summarize(records, args.confidence)
    categories = {category: summarize([r for r in records if r["category"] == category], args.confidence)
                  for category in sorted({r["category"] for r in records})}
    ocr_path = Path(ocr.yolo_ocr.ckpt_path).resolve()
    manifest = {"run_id": run_id, "scope": "offline_local_detector_yolo_ocr_postprocessor",
                "dataset_kind": args.dataset_kind, "dataset_metadata": dataset_metadata,
                "dataset": str(dataset), "ground_truth_sha256": sha256(ground_truth),
                "dataset_images_total": full_count, "evaluated_images": len(samples),
                "image_sha256": {sample["file"]: sha256(sample["path"]) for sample in samples},
                "detector_weights": {"path": str(model_path), "sha256": sha256(model_path)},
                "ocr_weights": {"path": str(ocr_path), "sha256": sha256(ocr_path)},
                "detector_class_names": detector.model.names,
                "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in
                                  [Path(__file__).resolve(), ROOT / "src/evaluation/metrics.py", ROOT / "src/core/detector.py", ROOT / "src/core/ocr_engine.py", ROOT / "src/core/postprocessor.py", ROOT / "src/core/preprocessor.py"]},
                "versions": {"python": platform.python_version(), "torch": torch.__version__, "opencv": cv2.__version__, "ultralytics": ultralytics.__version__},
                "platform": platform.platform(), "cpu": platform.processor(), "torch_threads": args.threads,
                "device": "cpu", "cloud_enabled": False, "warmup_iterations": args.warmup,
                "model_load_ms": load_ms, "warmup_ms": warmup_ms,
                "evaluation_wall_ms_including_gt_crop_experiment": elapsed_ms,
                "operating_confidence": args.confidence, "ap_min_confidence": args.ap_min_confidence,
                "iou_threshold": 0.5, "read_only_inputs": True,
                "excluded_from_pipeline": ["API character-region fallback", "whole-image OCR fallback", "cloud fallback", "image decoding", "HTTP", "file writes", "database", "model load", "warmup", "GT-crop OCR"],
                "detection_note": "AP evaluates retained detector proposals at AP minimum confidence with existing geometric/color filters and NMS; P/R uses operating confidence. Not raw YOLO val().",
                "text_note": "One-to-one IoU>=0.5 matching. Missing detections predict empty text; unmatched predicted text adds insertion errors. GT-crop OCR is independent."}
    output = args.output_root.resolve() / run_id
    save_outputs(output, manifest, records, summary, categories, not args.no_plots)
    print((output / "REPORT.md").read_text(encoding="utf-8"))
    print(f"Results saved: {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Benchmark failed: {error}", file=sys.stderr)
        raise SystemExit(1)
