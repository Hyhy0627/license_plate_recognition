"""Regression checks for metrics and separation of oracle OCR from local E2E."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from src.evaluation.metrics import (
    compute_iou, detection_metrics, levenshtein_distance, match_boxes,
    normalize_text, text_metrics, timing_stats,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("benchmark_runner", ROOT / "tool/run_phase4_benchmark.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def plate(text="29A12345", bbox=None, score=0.9):
    return {"text": text, "raw_text": text, "bbox": bbox or [0, 0, 10, 10], "score": score}


def record(truth, detections=None, predictions=None, oracle=None):
    return {"truth": truth, "detections": detections or [],
            "predictions": predictions or [], "oracle": oracle or []}


class MetricTests(unittest.TestCase):
    def test_text_normalization_and_insertions(self):
        self.assertEqual(normalize_text("29-A 123.45"), "29A12345")
        self.assertEqual(levenshtein_distance("ABC", "ABCD"), 1)
        self.assertEqual(levenshtein_distance("ABC", ""), 3)

    def test_iou_disjoint_and_degenerate(self):
        self.assertEqual(compute_iou([0, 0, 10, 10], [0, 0, 10, 10]), 1)
        self.assertEqual(compute_iou([0, 0, 0, 0], [0, 0, 0, 0]), 0)
        self.assertEqual(compute_iou([0, 0, 2, 2], [3, 3, 5, 5]), 0)

    def test_duplicate_predictions_are_false_positives(self):
        truth = [plate()]
        matches, missed, extra = match_boxes(truth, [plate(score=0.7), plate(score=0.9)])
        self.assertEqual(matches, [(0, 1, 1.0)])
        self.assertEqual(missed, [])
        self.assertEqual(extra, [0])
        metrics = detection_metrics([record(truth, [plate(score=0.7), plate(score=0.9)])])
        self.assertEqual((metrics["tp"], metrics["fp"], metrics["fn"]), (1, 1, 0))
        self.assertEqual(metrics["precision"], 0.5)

    def test_higher_scored_false_positive_reduces_ap(self):
        false_box = plate(bbox=[20, 20, 30, 30], score=0.99)
        metrics = detection_metrics([record([plate()], [false_box, plate(score=0.8)])])
        self.assertAlmostEqual(metrics["ap50"], 0.5)

    def test_missed_plate_reduces_ap_and_recall(self):
        second = plate(bbox=[20, 20, 30, 30])
        metrics = detection_metrics([record([plate(), second], [plate()])])
        self.assertEqual(metrics["recall"], 0.5)
        self.assertAlmostEqual(metrics["ap50"], 51 / 101)
        self.assertEqual(metrics["mean_iou_including_misses"], 0.5)

    def test_no_predictions_is_zero_not_a_default_high_score(self):
        metrics = detection_metrics([record([plate()])])
        self.assertEqual(metrics["ap50"], 0)
        self.assertEqual(metrics["fn"], 1)
        self.assertIsNone(metrics["mean_iou_matched"])

    def test_negative_images_count_false_positives(self):
        records = [record([], [plate()], [plate()]), record([])]
        metrics = detection_metrics(records)
        self.assertEqual(metrics["fp"], 1)
        self.assertIsNone(metrics["ap50"])
        self.assertEqual(text_metrics(records)["exact_image_accuracy"], 0.5)

    def test_ap_pool_and_operating_threshold_are_separate(self):
        metrics = detection_metrics([record([plate()], [plate(score=0.2)])], score_threshold=0.3)
        self.assertEqual(metrics["recall"], 0)
        self.assertEqual(metrics["ap50"], 1)

    def test_wrong_text_does_not_become_exact_detection_success(self):
        metrics = text_metrics([record([plate()], predictions=[plate("29A12346")])])
        self.assertEqual(metrics["exact_plate_matches"], 0)
        self.assertEqual(metrics["edit_errors"], 1)
        self.assertEqual(metrics["cer"], 1 / 8)

    def test_cer_counts_missing_and_extra_text(self):
        second = plate("123", [20, 20, 30, 30])
        extra = plate("XYZ", [40, 40, 50, 50])
        metrics = text_metrics([record([plate("ABC"), second], predictions=[plate("ABC"), extra])])
        self.assertEqual(metrics["edit_errors"], 6)
        self.assertEqual(metrics["cer"], 1)
        self.assertEqual(metrics["exact_plate_recall"], 0.5)
        self.assertEqual(metrics["exact_image_accuracy"], 0)

    def test_timing_quantiles(self):
        metrics = timing_stats([10, 20, 30, 40])
        self.assertEqual(metrics["mean_ms"], 25)
        self.assertEqual(metrics["p50_ms"], 25)
        self.assertAlmostEqual(metrics["p95_ms"], 38.5)
        self.assertIsNone(timing_stats([])["mean_ms"])
        with self.assertRaises(ValueError):
            timing_stats([float("nan")])


class RunnerTests(unittest.TestCase):
    def test_existing_output_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sentinel = root / "metrics.json"
            sentinel.write_text("existing evidence", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                RUNNER.save_outputs(root, {}, [], {}, {}, False)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing evidence")

    def test_multi_plate_and_negative_annotation_format(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "image.jpg").touch()
            (root / "negative.jpg").touch()
            manifest = root / "gt.json"
            manifest.write_text(json.dumps({"metadata": {"kind": "synthetic"}, "images": {
                "image.jpg": {"plates": [plate(), plate(bbox=[20, 20, 30, 30])]},
                "negative.jpg": {"plates": []}}}), encoding="utf-8")
            samples, metadata = RUNNER.load_annotations(root, manifest)
            self.assertEqual([len(sample["truth"]) for sample in samples], [2, 0])
            self.assertEqual(metadata["kind"], "synthetic")

    def test_annotations_reject_path_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = root / "gt.json"
            manifest.write_text(json.dumps({"../escape.jpg": plate()}), encoding="utf-8")
            with self.assertRaises(ValueError):
                RUNNER.load_annotations(root, manifest)

    def test_oracle_cannot_rescue_a_missed_detection(self):
        import cv2
        import numpy as np

        class MissedDetector:
            def detect(self, image):
                return []

            def crop_plate(self, image, bbox):
                return image[:10, :10]

        class PerfectOracleOCR:
            def recognize_local_yolo(self, crop):
                return {"raw_text": "29A12345", "plate_type": "one_line", "avg_conf": 0.99}

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.png"
            cv2.imwrite(str(path), np.zeros((20, 20, 3), dtype=np.uint8))
            samples = [{"file": path.name, "path": path, "category": "fixture", "truth": [plate()]}]
            records, _ = RUNNER.collect_records(samples, MissedDetector(), PerfectOracleOCR(), 0.3, 0)
            self.assertEqual(text_metrics(records)["exact_plate_recall"], 0)
            self.assertEqual(text_metrics(records, "oracle")["exact_plate_recall"], 1)
            self.assertEqual(records[0]["predictions"], [])


if __name__ == "__main__":
    unittest.main()
