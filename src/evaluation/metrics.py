"""Single-class plate metrics computed exclusively from recorded predictions.

AP50 uses 101 recall points and a precision envelope. Detections are greedily
matched by confidence, once per ground-truth box, independently in each image.
This module has no third-party dependencies or model/network side effects.
"""

import math
import re
from statistics import mean


def normalize_text(text):
    return re.sub(r"[^A-Z0-9]", "", str(text).upper())


def levenshtein_distance(first, second):
    row = list(range(len(second) + 1))
    for i, char in enumerate(first, 1):
        next_row = [i]
        for j, other in enumerate(second, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (char != other)))
        row = next_row
    return row[-1]


def compute_iou(first, second):
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    area_b = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def match_boxes(truth, predictions, threshold=0.5):
    remaining = set(range(len(truth)))
    matches = []
    unmatched_predictions = []
    for index in sorted(range(len(predictions)), key=lambda i: -predictions[i]["score"]):
        overlaps = [(compute_iou(predictions[index]["bbox"], truth[j]["bbox"]), j)
                    for j in sorted(remaining)]
        overlap, target = max(overlaps, default=(0.0, -1), key=lambda pair: pair[0])
        if target >= 0 and overlap >= threshold:
            remaining.remove(target)
            matches.append((target, index, overlap))
        else:
            unmatched_predictions.append(index)
    return matches, sorted(remaining), unmatched_predictions


def detection_metrics(records, score_threshold=0.3, iou_threshold=0.5):
    total_gt = sum(len(record["truth"]) for record in records)
    tp = fp = fn = 0
    matched_ious = []
    ranked = []
    for image_index, record in enumerate(records):
        predictions = record["detections"]
        operating = [p for p in predictions if p["score"] >= score_threshold]
        matches, missed, extra = match_boxes(record["truth"], operating, iou_threshold)
        tp += len(matches)
        fp += len(extra)
        fn += len(missed)
        matched_ious.extend(overlap for _, _, overlap in matches)
        for prediction_index, prediction in enumerate(predictions):
            ranked.append((prediction["score"], image_index, prediction_index))

    used = [set() for _ in records]
    curve = []
    cumulative_tp = cumulative_fp = 0
    for score, image_index, prediction_index in sorted(ranked, key=lambda row: -row[0]):
        record = records[image_index]
        prediction = record["detections"][prediction_index]
        overlaps = [(compute_iou(prediction["bbox"], gt["bbox"]), j)
                    for j, gt in enumerate(record["truth"]) if j not in used[image_index]]
        overlap, target = max(overlaps, default=(0.0, -1), key=lambda pair: pair[0])
        if target >= 0 and overlap >= iou_threshold:
            used[image_index].add(target)
            cumulative_tp += 1
        else:
            cumulative_fp += 1
        curve.append({"score": score, "precision": cumulative_tp / (cumulative_tp + cumulative_fp),
                      "recall": cumulative_tp / total_gt if total_gt else None})

    ap = None
    if total_gt:
        ap = mean(max((point["precision"] for point in curve
                       if point["recall"] >= recall / 100), default=0.0)
                  for recall in range(101))
    precision = tp / (tp + fp) if tp + fp else (0.0 if total_gt else None)
    recall = tp / total_gt if total_gt else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else (
        0.0 if total_gt else None)
    return {"ground_truth_plates": total_gt, "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1, "ap50": ap,
            "mean_iou_matched": mean(matched_ious) if matched_ious else None,
            "mean_iou_including_misses": sum(matched_ious) / total_gt if total_gt else None,
            "score_threshold": score_threshold, "iou_threshold": iou_threshold,
            "ap_interpolation": "101 recall points, precision envelope", "pr_curve": curve}


def text_metrics(records, source="predictions", field="text", iou_threshold=0.5):
    exact = total_gt = errors = characters = exact_images = extra_plates = 0
    total_predictions = 0
    for record in records:
        truth, predictions = record["truth"], record[source]
        matches, _, extra = match_boxes(truth, predictions, iou_threshold)
        match_by_gt = {gt_index: pred_index for gt_index, pred_index, _ in matches}
        image_exact = 0
        for index, target in enumerate(truth):
            expected = normalize_text(target["text"])
            pred_index = match_by_gt.get(index)
            actual = normalize_text(predictions[pred_index].get(field, "")) if pred_index is not None else ""
            errors += levenshtein_distance(expected, actual)
            characters += len(expected)
            if pred_index is not None and expected == actual:
                exact += 1
                image_exact += 1
        # Spurious plates count as insertion errors, rather than disappearing from CER.
        errors += sum(len(normalize_text(predictions[index].get(field, ""))) for index in extra)
        extra_plates += len(extra)
        total_predictions += len(predictions)
        total_gt += len(truth)
        exact_images += image_exact == len(truth) and len(predictions) == len(truth)
    return {"ground_truth_plates": total_gt, "predicted_plates": total_predictions,
            "exact_plate_matches": exact, "extra_localizations": extra_plates,
            "exact_plate_recall": exact / total_gt if total_gt else None,
            "exact_plate_precision": exact / total_predictions if total_predictions else (
                0.0 if total_gt else None),
            "exact_image_accuracy": exact_images / len(records) if records else None,
            "edit_errors": errors, "ground_truth_characters": characters,
            "cer": errors / characters if characters else None}


def timing_stats(values):
    if not values:
        return {"count": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None}
    values = sorted(values)
    if not all(math.isfinite(value) and value >= 0 for value in values):
        raise ValueError("Timing samples must be finite and nonnegative")

    def percentile(fraction):
        position = fraction * (len(values) - 1)
        low, high = math.floor(position), math.ceil(position)
        return values[low] + (values[high] - values[low]) * (position - low)

    return {"count": len(values), "mean_ms": mean(values),
            "p50_ms": percentile(0.5), "p95_ms": percentile(0.95)}
