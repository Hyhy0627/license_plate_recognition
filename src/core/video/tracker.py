"""Offline vehicle tracking with plate recognition for short traffic clips."""

from collections import Counter, defaultdict
from pathlib import Path
from threading import Lock
from typing import Callable
import re

import cv2

from src.core.ocr.postprocessor import PlatePostprocessor
from src.core.video.unassigned_plates import UnassignedPlates
from src.config import settings


VEHICLE_CLASSES = {2: "Ô tô", 3: "Xe máy", 5: "Xe buýt", 7: "Xe tải"}
UNCERTAIN_HEAVY_VEHICLE = "Chưa rõ xe tải hay xe buýt"
HEAVY_VEHICLE_TYPES = {"Xe tải", "Xe buýt", UNCERTAIN_HEAVY_VEHICLE}
MAX_VIDEO_SECONDS = 45
MAX_WIDTH = 960
TRACKING_PROFILES = {"fast": (5, 640), "detailed": (5, 640)}
MAX_NINEROUTER_CALLS = 6


def _box_iou(first, second):
    x1, y1 = max(first[0], second[0]), max(first[1], second[1])
    x2, y2 = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def _track_boxes(result):
    boxes = defaultdict(list)
    for frame in result["frames"]:
        for vehicle in frame["vehicles"]:
            boxes[vehicle["track_id"]].append((frame["time"], vehicle["bbox"]))
    return boxes


def _stable_vehicle_type(votes):
    """Use the whole track, avoiding a permanent label from its first frame."""
    counts = Counter(votes)
    winner, count = counts.most_common(1)[0]
    if len(votes) == 1 and winner in {"Xe tải", "Xe buýt"}:
        return UNCERTAIN_HEAVY_VEHICLE
    heavy_count = counts["Xe tải"] + counts["Xe buýt"]
    if counts["Xe tải"] and counts["Xe buýt"] and count / heavy_count < 0.7:
        return UNCERTAIN_HEAVY_VEHICLE
    return winner


def _resolve_overlapping_vehicle_types(tracks, frames):
    """Copy a stable heavy-vehicle label to short duplicate track fragments."""
    boxes = _track_boxes({"frames": frames})
    boxes_by_time = {
        track_id: {round(second, 3): box for second, box in records}
        for track_id, records in boxes.items()
    }
    for short_id, short_records in boxes_by_time.items():
        short_type = tracks[short_id]["vehicle_type"]
        if short_type not in HEAVY_VEHICLE_TYPES:
            continue
        for long_id, long_records in boxes_by_time.items():
            if long_id == short_id or len(long_records) < 3 * len(short_records):
                continue
            long_type = tracks[long_id]["vehicle_type"]
            if long_type not in {"Xe tải", "Xe buýt"}:
                continue
            overlaps = [
                _box_iou(box, long_records[second])
                for second, box in short_records.items()
                if second in long_records
            ]
            if sum(overlap >= 0.8 for overlap in overlaps) >= 2:
                tracks[short_id]["vehicle_type"] = long_type
                break
    for frame in frames:
        for vehicle in frame["vehicles"]:
            vehicle["vehicle_type"] = tracks[vehicle["track_id"]]["vehicle_type"]


def _matching_track(source, source_boxes, target, target_boxes):
    """Match track identities only when their boxes overlap at multiple times."""
    best_id, best_score = None, 0.0
    source_by_time = {round(time, 1): box for time, box in source_boxes}
    for candidate in target:
        same_type = candidate["vehicle_type"] == source["vehicle_type"]
        heavy_vehicle_pair = {candidate["vehicle_type"], source["vehicle_type"]} <= HEAVY_VEHICLE_TYPES
        if not same_type and not heavy_vehicle_pair:
            continue
        overlaps = [
            _box_iou(source_by_time[round(time, 1)], box)
            for time, box in target_boxes[candidate["track_id"]]
            if round(time, 1) in source_by_time
        ]
        strong = [overlap for overlap in overlaps if overlap >= 0.4]
        if len(strong) < 2:
            continue
        score = sum(strong) / len(strong) + min(len(strong), 10) * 0.02
        if score > best_score:
            best_id, best_score = candidate["track_id"], score
    return best_id


def _coalesce_duplicate_plates(tracks, frames):
    """Show one row per plate even when classifiers create overlapping IDs."""
    canonical = {}
    remap = {}
    kept = []
    for track in sorted(tracks, key=lambda item: (item["first_seen"], item["track_id"])):
        key = PlatePostprocessor.clean_text(track["plate_number"]) if track["plate_number"] else None
        # A plate-only box and a vehicle box represent different geometry.
        # Keep the spatially validated plate tracks separate from this
        # legacy deduplication by recognized text.
        if track["vehicle_type"] == "Biển số":
            kept.append(track)
            continue
        previous = canonical.get(key) if key else None
        if previous:
            previous["last_seen"] = max(previous["last_seen"], track["last_seen"])
            previous["plate_observations"] += track["plate_observations"]
            previous["plate_candidates"] = list(dict.fromkeys(previous["plate_candidates"] + track["plate_candidates"]))
            if previous["plate_status"] != "needs_review" and track["plate_status"] == "confirmed":
                previous["plate_status"] = "confirmed"
            remap[track["track_id"]] = previous["track_id"]
        else:
            kept.append(track)
            if key:
                canonical[key] = track
    if remap:
        for frame in frames:
            seen = set()
            unique = []
            for vehicle in frame["vehicles"]:
                vehicle["track_id"] = remap.get(vehicle["track_id"], vehicle["track_id"])
                if vehicle["track_id"] not in seen:
                    unique.append(vehicle)
                    seen.add(vehicle["track_id"])
            frame["vehicles"] = unique
    return kept


def merge_video_results(fast, detailed):
    """Keep stable fast tracks and add plate evidence from the denser pass."""
    if fast["frame_width"] != detailed["frame_width"] or fast["frame_height"] != detailed["frame_height"]:
        raise ValueError("Hai lượt phân tích có kích thước khung hình khác nhau.")
    tracks = {item["track_id"]: dict(item) for item in fast["tracks"]}
    frames = [{"time": frame["time"], "vehicles": [dict(vehicle) for vehicle in frame["vehicles"]]} for frame in fast["frames"]]
    fast_boxes, detailed_boxes = _track_boxes(fast), _track_boxes(detailed)
    next_id = max(tracks, default=0) + 1

    for track in tracks.values():
        track["plate_candidates"] = [track["plate_number"]] if track["plate_number"] else []
        track["plate_status"] = "tentative" if track["plate_number"] else "unreadable"

    for detailed_track in detailed["tracks"]:
        if not detailed_track["plate_number"]:
            continue
        match_id = _matching_track(detailed_track, detailed_boxes[detailed_track["track_id"]], fast["tracks"], fast_boxes)
        if match_id is None:
            match_id = next_id
            next_id += 1
            tracks[match_id] = {**detailed_track, "track_id": match_id, "plate_candidates": [detailed_track["plate_number"]], "plate_status": "tentative"}
            for frame in detailed["frames"]:
                for vehicle in frame["vehicles"]:
                    if vehicle["track_id"] == detailed_track["track_id"]:
                        nearest = min(frames, key=lambda item: abs(item["time"] - frame["time"]))
                        if abs(nearest["time"] - frame["time"]) <= 0.26 and not any(item["track_id"] == match_id for item in nearest["vehicles"]):
                            nearest["vehicles"].append({**vehicle, "track_id": match_id})
            continue
        target = tracks[match_id]
        candidate = detailed_track["plate_number"]
        if not target["plate_number"]:
            target.update(plate_number=candidate, plate_confidence=detailed_track["plate_confidence"], plate_observations=detailed_track["plate_observations"], plate_candidates=[candidate], plate_status="tentative")
        elif PlatePostprocessor.clean_text(target["plate_number"]) == PlatePostprocessor.clean_text(candidate):
            target["plate_observations"] += detailed_track["plate_observations"]
            target["plate_status"] = "confirmed"
        else:
            target["plate_candidates"].insert(0, candidate)
            target["plate_number"] = candidate
            target["plate_confidence"] = detailed_track["plate_confidence"]
            target["plate_observations"] = detailed_track["plate_observations"]
            target["plate_status"] = "needs_review"

    merged_tracks = _coalesce_duplicate_plates(list(tracks.values()), frames)
    return {**fast, "mode": "combined", "frames": frames, "tracks": merged_tracks,
            "ninerouter": detailed.get("ninerouter")}


def associate_plates(vehicle_boxes, plate_boxes):
    """Attach each plate to the best-matching vehicle based on containment and center alignment."""
    if not vehicle_boxes or not plate_boxes:
        return defaultdict(list)

    candidates = []
    for p_idx, plate in enumerate(plate_boxes):
        px1, py1, px2, py2 = plate["bbox"]
        cx, cy = (px1 + px2) / 2, (py1 + py2) / 2
        for v in vehicle_boxes:
            vx1, vy1, vx2, vy2 = v["bbox"]
            vw = max(1, vx2 - vx1)
            vh = max(1, vy2 - vy1)
            vcx = (vx1 + vx2) / 2

            strictly_inside = (vx1 <= cx <= vx2) and (vy1 <= cy <= vy2)
            margin_inside = (
                (vx1 - vw * 0.08) <= cx <= (vx2 + vw * 0.08)
                and (vy1 - vh * 0.05) <= cy <= (vy2 + vh * 0.15)
            )
            if not strictly_inside and not margin_inside:
                continue

            inside_penalty = 0.0 if strictly_inside else 1.0
            horiz_offset = abs(cx - vcx) / vw
            area = vw * vh
            score = inside_penalty * 2.0 + horiz_offset * 1.5 + (area / 1e7)
            candidates.append((score, p_idx, v["track_id"], plate))

    candidates.sort(key=lambda item: item[0])
    assigned = defaultdict(list)
    used_plates = set()
    used_vehicles = set()

    for score, p_idx, track_id, plate in candidates:
        if p_idx not in used_plates and track_id not in used_vehicles:
            assigned[track_id].append(plate)
            used_plates.add(p_idx)
            used_vehicles.add(track_id)

    for score, p_idx, track_id, plate in candidates:
        if p_idx not in used_plates:
            assigned[track_id].append(plate)
            used_plates.add(p_idx)

    return assigned


def winning_plate(observations):
    """Prefer repeated valid readings; break ties using OCR confidence."""
    if not observations:
        return None
    counts = Counter(PlatePostprocessor.clean_text(item["plate_number"]) for item in observations)
    best = max(observations, key=lambda item: (counts[PlatePostprocessor.clean_text(item["plate_number"])], item["confidence"]))
    return {"plate_number": best["plate_number"], "plate_confidence": round(best["confidence"], 3), "plate_observations": counts[PlatePostprocessor.clean_text(best["plate_number"])]}


def plate_fits_vehicle(plate_number, vehicle_type):
    """Avoid assigning a two-line motorcycle-series read to a larger vehicle."""
    return vehicle_type == "Xe máy" or re.match(r"^[0-9]{2}-[A-Z][0-9] ", plate_number) is None


def _remember_plate_crop(best_crops, track_id, frame, plate, detector):
    confidence = float(plate["confidence"])
    crop = detector.crop_plate(frame, plate["bbox"])
    if crop is None or crop.size == 0:
        return
    # Measure image sharpness using Laplacian variance to prefer clearer frames
    try:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    except Exception:
        sharpness = 0.0
    quality = confidence + min(sharpness / 250.0, 0.4)
    if quality <= best_crops.get(track_id, (0.0, None))[0]:
        return
    best_crops[track_id] = (quality, crop.copy())


def _rescue_visible_plates(capture, frames, tracks, observations, plate_detector, ocr_engine,
                           inference_lock, fps, scale, remote_plate_crops):
    """Recheck a few large unreadable vehicles at crop resolution."""
    candidates = defaultdict(list)
    for frame in frames:
        for vehicle in frame["vehicles"]:
            track_id = vehicle["track_id"]
            if observations[track_id]:
                continue
            x1, y1, x2, y2 = vehicle["bbox"]
            candidates[track_id].append(((x2 - x1) * (y2 - y1), frame["time"], vehicle["bbox"]))
    ranked = sorted(
        (track_id for track_id in candidates if tracks[track_id]["last_seen"] - tracks[track_id]["first_seen"] >= 0.4),
        key=lambda track_id: (tracks[track_id]["vehicle_type"] != "Xe máy", -max(item[0] for item in candidates[track_id])),
    )[:15]
    for track_id in ranked:
        records = candidates[track_id]
        sample_indices = dict.fromkeys(round((len(records) - 1) * fraction) for fraction in (0, 0.25, 0.5, 0.75, 1))
        for index in sample_indices:
            area, second, bbox = records[index]
            if area < 4000:
                continue
            capture.set(cv2.CAP_PROP_POS_FRAMES, round(second * fps))
            ok, original = capture.read()
            if not ok:
                continue
            x1, y1, x2, y2 = [round(value / scale) for value in bbox]
            padding = round(max(x2 - x1, y2 - y1) * 0.04)
            x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
            x2, y2 = min(original.shape[1], x2 + padding), min(original.shape[0], y2 + padding)
            crop = original[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            with inference_lock:
                boxes = plate_detector.detect(crop, include_low_confidence=True)
                boxes = sorted((item for item in boxes if item["confidence"] >= 0.2
                                and (item["bbox"][1] + item["bbox"][3]) / 2 >= crop.shape[0] * 0.25),
                               key=lambda item: item["confidence"], reverse=True)
                for plate in boxes[:2]:
                    plate_crop = plate_detector.crop_plate(crop, plate["bbox"])
                    if plate_crop is None or plate_crop.size == 0:
                        continue
                    _remember_plate_crop(remote_plate_crops, track_id, crop, plate, plate_detector)
                    read = ocr_engine.recognize_local_yolo(plate_crop)
                    cleaned = PlatePostprocessor.clean_text(read.get("raw_text", ""))
                    formatted = PlatePostprocessor.format_vietnamese_plate(cleaned, plate_type=read.get("plate_type"), text_lines=read.get("text_lines"))
                    if PlatePostprocessor.validate_plate(formatted) and plate_fits_vehicle(formatted, tracks[track_id]["vehicle_type"]):
                        observations[track_id].append({"plate_number": formatted, "confidence": float(read.get("avg_conf", 0.0))})
                        break
            votes = Counter(PlatePostprocessor.clean_text(item["plate_number"]) for item in observations[track_id])
            if max(votes.values(), default=0) >= 2:
                break


def _rescue_plates_with_ninerouter(capture, frames, tracks, observations, plate_detector, ocr_engine,
                                   inference_lock, fps, scale, progress, remote_plate_crops=None):
    """Use one bounded remote request per unreadable track, on a vehicle or plate crop."""
    client = getattr(ocr_engine, "ninerouter_client", None)
    if client is None:
        return {"status": "disabled", "attempts": 0, "recognized": 0}
    if not client.is_available():
        return {"status": "unavailable", "attempts": 0, "recognized": 0}

    candidates = defaultdict(list)
    remote_plate_crops = remote_plate_crops or {}
    for frame in frames:
        for vehicle in frame["vehicles"]:
            track_id = vehicle["track_id"]
            if observations[track_id] or (track_id not in remote_plate_crops
                                          and tracks[track_id]["last_seen"] - tracks[track_id]["first_seen"] < 0.4):
                continue
            x1, y1, x2, y2 = vehicle["bbox"]
            area = (x2 - x1) * (y2 - y1)
            if area >= 4000 or track_id in remote_plate_crops:
                candidates[track_id].append((area, frame["time"], vehicle["bbox"]))

    ranked = sorted(candidates, key=lambda track_id: (
        track_id in remote_plate_crops,
        tracks[track_id]["last_seen"] - tracks[track_id]["first_seen"],
        max(item[0] for item in candidates[track_id]),
    ), reverse=True)[:MAX_NINEROUTER_CALLS]
    attempts = 0
    recognized = 0
    status = "available"
    for index, track_id in enumerate(ranked):
        if track_id in remote_plate_crops:
            read = client.recognize_plate(remote_plate_crops[track_id][1], timeout=settings.VIDEO_NINEROUTER_TIMEOUT)
            plate_visible = True
        else:
            _, second, bbox = max(candidates[track_id], key=lambda item: item[0])
            capture.set(cv2.CAP_PROP_POS_FRAMES, round(second * fps))
            ok, original = capture.read()
            if not ok:
                continue
            x1, y1, x2, y2 = [round(value / scale) for value in bbox]
            padding = round(max(x2 - x1, y2 - y1) * 0.04)
            x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
            x2, y2 = min(original.shape[1], x2 + padding), min(original.shape[0], y2 + padding)
            crop = original[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            with inference_lock:
                plate_boxes = plate_detector.detect(crop, include_low_confidence=True)
            plate_boxes = sorted((plate for plate in plate_boxes if plate["confidence"] >= 0.2
                                  and (plate["bbox"][1] + plate["bbox"][3]) / 2 >= crop.shape[0] * 0.25),
                                 key=lambda plate: plate["confidence"], reverse=True)
            if plate_boxes:
                plate_crop = plate_detector.crop_plate(crop, plate_boxes[0]["bbox"])
                if plate_crop is None or not plate_crop.size:
                    continue
                read = client.recognize_plate(plate_crop, timeout=settings.VIDEO_NINEROUTER_TIMEOUT)
                plate_visible = True
            else:
                read = client.detect_and_recognize_plate(crop, timeout=settings.VIDEO_NINEROUTER_TIMEOUT)
                plate_visible = bool(read.get("bbox"))
        attempts += 1

        cleaned = PlatePostprocessor.clean_text(read.get("raw_text", ""))
        formatted = PlatePostprocessor.format_vietnamese_plate(
            cleaned, plate_type=read.get("plate_type"), text_lines=read.get("text_lines"))
        if plate_visible and PlatePostprocessor.validate_plate(formatted) and plate_fits_vehicle(formatted, tracks[track_id]["vehicle_type"]):
            observations[track_id].append({"plate_number": formatted, "confidence": float(read.get("confidence", 0.0))})
            recognized += 1
        if read.get("error") in {"offline", "connection_error", "timeout", "http_error"}:
            status = "error"
            break
        progress(93 + round(6 * (index + 1) / max(1, len(ranked))))
    return {"status": status, "attempts": attempts, "recognized": recognized}


def process_video(path: Path, vehicle_model_path: Path, plate_detector, ocr_engine, inference_lock: Lock,
                  progress: Callable[[int], None], mode: str = "fast", use_remote_ocr: bool = True):
    """Return sparse vehicle tracks and plate votes, with bounded 9Router rescue."""
    if mode == "combined":
        fast = process_video(path, vehicle_model_path, plate_detector, ocr_engine, inference_lock,
                             lambda value: progress(round(value * 0.45)), mode="fast", use_remote_ocr=False)
        detailed = process_video(path, vehicle_model_path, plate_detector, ocr_engine, inference_lock,
                                 lambda value: progress(45 + round(value * 0.55)), mode="detailed", use_remote_ocr=use_remote_ocr)
        return merge_video_results(fast, detailed)
    from ultralytics import YOLO

    if mode not in TRACKING_PROFILES:
        raise ValueError("Chế độ phân tích video không hợp lệ.")
    sample_fps, track_imgsz = TRACKING_PROFILES[mode]
    if not vehicle_model_path.is_file():
        raise ValueError(f"Thiếu model phát hiện phương tiện: {vehicle_model_path}")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("Không đọc được video. Hãy dùng MP4, MOV, AVI hoặc WEBM hợp lệ.")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not 1 <= fps <= 120 or frame_count <= 0 or width <= 0 or height <= 0:
            raise ValueError("Video thiếu thông tin khung hình hoặc tốc độ phát hợp lệ.")
        duration = frame_count / fps
        if duration > MAX_VIDEO_SECONDS:
            raise ValueError(f"Video dài quá {MAX_VIDEO_SECONDS} giây. Hãy cắt một đoạn ngắn hơn.")
        if width * height > 1920 * 1080:
            raise ValueError("Video vượt quá độ phân giải Full HD.")

        model = YOLO(str(vehicle_model_path))  # a fresh tracker for every video
        stride = max(1, round(fps / sample_fps))
        scale = min(1.0, MAX_WIDTH / width)
        output_width, output_height = round(width * scale), round(height * scale)
        frames = []
        tracks = {}
        unassigned_plates = UnassignedPlates()
        observations = defaultdict(list)
        remote_plate_crops = {}
        vehicle_votes = defaultdict(list)
        next_ocr_frame = defaultdict(int)
        ocr_attempts = defaultdict(int)
        max_vehicle_area = defaultdict(float)
        track_frame_count = defaultdict(int)
        frame_index = 0
        while True:
            if frame_index / fps > MAX_VIDEO_SECONDS:
                raise ValueError(f"Video dài quá {MAX_VIDEO_SECONDS} giây. Hãy cắt một đoạn ngắn hơn.")
            if not capture.grab():
                break
            if frame_index % stride:
                frame_index += 1
                continue
            ok, original_frame = capture.retrieve()
            if not ok:
                break
            frame = cv2.resize(original_frame, (output_width, output_height), interpolation=cv2.INTER_AREA) if scale < 1 else original_frame
            result = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=list(VEHICLE_CLASSES), conf=0.25, imgsz=track_imgsz, verbose=False)[0]
            second = round(frame_index / fps, 3)
            vehicles = []
            if result.boxes.id is not None:
                for box in result.boxes:
                    track_id = int(box.id.item())
                    cls_id = int(box.cls.item())
                    bbox = [int(value) for value in box.xyxy[0].tolist()]
                    vehicle = {"track_id": track_id, "vehicle_type": VEHICLE_CLASSES[cls_id], "bbox": bbox}
                    vehicles.append(vehicle)
                    vehicle_votes[track_id].append(vehicle["vehicle_type"])
                    track_frame_count[track_id] += 1
                    track = tracks.setdefault(track_id, {"track_id": track_id, "vehicle_type": VEHICLE_CLASSES[cls_id], "first_seen": second, "last_seen": second})
                    track["last_seen"] = second

                    # Khi xe tiến lại gần và diện tích tăng rõ rệt (>= 25%), giải phóng khỏi backoff lockout
                    current_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                    if max_vehicle_area[track_id] > 0 and current_area >= max_vehicle_area[track_id] * 1.25 and current_area >= 4000:
                        next_ocr_frame[track_id] = frame_index
                    if current_area > max_vehicle_area[track_id]:
                        max_vehicle_area[track_id] = current_area

            # Scan unresolved tracks periodically; a newly visible clear plate
            # can bypass a failed track's retry backoff.
            unresolved = [item for item in vehicles if len(observations[item["track_id"]]) < 3
                          and max(Counter(PlatePostprocessor.clean_text(read["plate_number"]) for read in observations[item["track_id"]]).values(), default=0) < 2]
            due = {item["track_id"] for item in unresolved if frame_index >= next_ocr_frame[item["track_id"]]}
            scan_interval = max(1, round(fps * (2 if mode == "fast" else 1)))
            periodic_scan = bool(unresolved) and frame_index % scan_interval < stride
            # A close-up can show a plate even when YOLO/ByteTrack misses its
            # vehicle entirely. Probe empty scenes periodically. Follow a newly
            # observed unmatched plate at the normal sampling rate.
            probe_empty = not vehicles and frame_index % max(1, round(fps)) < stride
            follow_plate = second - unassigned_plates.last_seen <= 2 * stride / fps + 0.002
            if due or periodic_scan or probe_empty or follow_plate:
                with inference_lock:
                    plate_boxes = plate_detector.detect(original_frame, include_low_confidence=True)
                    scaled_plates = [{**plate, "original_bbox": plate["bbox"], "bbox": [round(value * scale) for value in plate["bbox"]]} for plate in plate_boxes]
                    assigned = associate_plates(vehicles, scaled_plates)
                    attached = {tuple(plate["bbox"]) for group in assigned.values() for plate in group}
                    unmatched = [plate for plate in scaled_plates if tuple(plate["bbox"]) not in attached]
                    unassigned_plates.observe(second, original_frame, unmatched, plate_detector, ocr_engine)
                    for vehicle in unresolved:
                        track_id = vehicle["track_id"]
                        plates_for_vehicle = list(assigned.get(track_id, []))

                        # Nếu phát hiện toàn cảnh bị trượt biển số của xe này, thử detect trên crop xe
                        if not plates_for_vehicle and (track_id in due or periodic_scan):
                            vx1, vy1, vx2, vy2 = [round(val / scale) for val in vehicle["bbox"]]
                            v_w, v_h = vx2 - vx1, vy2 - vy1
                            if v_w * v_h >= 3200:
                                pad_x = round(v_w * 0.05)
                                pad_y = round(v_h * 0.05)
                                cvx1, cvy1 = max(0, vx1 - pad_x), max(0, vy1 - pad_y)
                                cvx2, cvy2 = min(original_frame.shape[1], vx2 + pad_x), min(original_frame.shape[0], vy2 + pad_y)
                                v_crop = original_frame[cvy1:cvy2, cvx1:cvx2]
                                if v_crop.size > 0:
                                    local_plates = plate_detector.detect(v_crop, include_low_confidence=True)
                                    for lp in local_plates:
                                        if lp["confidence"] >= 0.2:
                                            lx1, ly1, lx2, ly2 = lp["bbox"]
                                            orig_p = [cvx1 + lx1, cvy1 + ly1, cvx1 + lx2, cvy1 + ly2]
                                            plates_for_vehicle.append({
                                                **lp,
                                                "original_bbox": orig_p,
                                                "bbox": [round(val * scale) for val in orig_p]
                                            })

                        clear_plate = any(plate["confidence"] >= 0.35 for plate in plates_for_vehicle)
                        if track_id not in due and not clear_plate:
                            continue
                        ocr_attempts[track_id] += 1
                        previous_reads = len(observations[track_id])
                        for plate in plates_for_vehicle:
                            crop = plate_detector.crop_plate(original_frame, plate["original_bbox"])
                            if crop is None or crop.size == 0:
                                continue
                            _remember_plate_crop(remote_plate_crops, track_id, original_frame,
                                                 {**plate, "bbox": plate["original_bbox"]}, plate_detector)
                            read = ocr_engine.recognize_local_yolo(crop)
                            cleaned = PlatePostprocessor.clean_text(read.get("raw_text", ""))
                            formatted = PlatePostprocessor.format_vietnamese_plate(cleaned, plate_type=read.get("plate_type"), text_lines=read.get("text_lines"))

                            # Nếu ảnh bị nhòe chuyển động dẫn đến đọc lỗi, thử làm nét (unsharp mask) và đọc lại
                            if not (PlatePostprocessor.validate_plate(formatted) and plate_fits_vehicle(formatted, vehicle["vehicle_type"])):
                                try:
                                    from src.core.image.preprocessor import PlatePreprocessor
                                    sharpened = PlatePreprocessor.sharpen_image(crop, strength=1.4)
                                    retry_read = ocr_engine.recognize_local_yolo(sharpened)
                                    retry_cleaned = PlatePostprocessor.clean_text(retry_read.get("raw_text", ""))
                                    retry_formatted = PlatePostprocessor.format_vietnamese_plate(
                                        retry_cleaned, plate_type=retry_read.get("plate_type"), text_lines=retry_read.get("text_lines"))
                                    if PlatePostprocessor.validate_plate(retry_formatted) and plate_fits_vehicle(retry_formatted, vehicle["vehicle_type"]):
                                        read, formatted = retry_read, retry_formatted
                                except Exception:
                                    pass

                            if PlatePostprocessor.validate_plate(formatted) and plate_fits_vehicle(formatted, vehicle["vehicle_type"]):
                                observations[track_id].append({"plate_number": formatted, "confidence": float(read.get("avg_conf", 0.0)), "time": second})
                                break
                        retry_seconds = 1 if len(observations[track_id]) > previous_reads else min(2 ** (ocr_attempts[track_id] - 1), 6)
                        next_ocr_frame[track_id] = frame_index + max(1, round(fps * retry_seconds))

            frames.append({"time": second, "vehicles": vehicles})
            progress(min(90, int(90 * frame_index / frame_count)))
            frame_index += 1

        if not frames:
            raise ValueError("Video không có khung hình để phân tích.")
        for track_id, track in tracks.items():
            track["vehicle_type"] = _stable_vehicle_type(vehicle_votes[track_id])
        _resolve_overlapping_vehicle_types(tracks, frames)
        if mode == "detailed":
            _rescue_visible_plates(capture, frames, tracks, observations, plate_detector, ocr_engine,
                                   inference_lock, fps, scale, remote_plate_crops)
        progress(92)
        ninerouter = {"status": "skipped", "attempts": 0, "recognized": 0}
        if use_remote_ocr:
            ninerouter = _rescue_plates_with_ninerouter(capture, frames, tracks, observations, plate_detector,
                                                        ocr_engine, inference_lock, fps, scale, progress,
                                                        remote_plate_crops)
        # Tách các track bị ID-switch khi lia máy quay (khi một track có nhiều biển số riêng biệt với >= 4 lần xuất hiện)
        next_track_id = max(tracks.keys(), default=0) + 1
        for track_id in list(tracks.keys()):
            track_obs = observations[track_id]
            counts = Counter(item["plate_number"] for item in track_obs)
            strong_plates = [plate for plate, cnt in counts.most_common() if cnt >= 4]
            if len(strong_plates) > 1:
                for extra_plate in strong_plates[1:]:
                    extra_obs = [item for item in track_obs if item["plate_number"] == extra_plate]
                    new_id = next_track_id
                    next_track_id += 1
                    p_first = min((item.get("time", tracks[track_id]["first_seen"]) for item in extra_obs), default=tracks[track_id]["first_seen"])
                    p_last = max((item.get("time", tracks[track_id]["last_seen"]) for item in extra_obs), default=tracks[track_id]["last_seen"])
                    tracks[new_id] = {
                        **tracks[track_id],
                        "track_id": new_id,
                        "first_seen": p_first,
                        "last_seen": p_last,
                    }
                    observations[new_id] = extra_obs
                    track_frame_count[new_id] = len(extra_obs)
                    max_vehicle_area[new_id] = max_vehicle_area[track_id]
                observations[track_id] = [item for item in track_obs if item["plate_number"] == strong_plates[0]]

        for track_id, track in tracks.items():
            track.update(winning_plate(observations[track_id]) or {"plate_number": None, "plate_confidence": None, "plate_observations": 0})
            track["plate_candidates"] = list(dict.fromkeys(item["plate_number"] for item in observations[track_id]))
            track["plate_status"] = (
                "confirmed" if track["plate_observations"] >= 2 else
                "needs_review" if len(track["plate_candidates"]) > 1 else
                "tentative" if track["plate_number"] else "unreadable"
            )
        progress(100)

        # Lọc bỏ các track rác ở hậu cảnh hoặc chớp nhoáng không có biển số
        valid_tracks = []
        for track_id, track in tracks.items():
            has_plate = bool(track["plate_number"])
            track_duration = track["last_seen"] - track["first_seen"]
            count = track_frame_count[track_id]
            area = max_vehicle_area[track_id]
            # Xe không đọc được biển chỉ giữ lại nếu xuất hiện rõ ràng: ít nhất 8 frame, thời gian >= 1.5s và diện tích >= 5000 px
            if has_plate or (count >= 8 and track_duration >= 1.5 and area >= 5000):
                valid_tracks.append(track)

        # Discard frame overlays for vehicle IDs filtered out of the result.
        retained_ids = {track["track_id"] for track in valid_tracks}
        for frame in frames:
            frame["vehicles"] = [v for v in frame["vehicles"] if v["track_id"] in retained_ids]
        unassigned_plates.add_confirmed(valid_tracks, frames, stride / fps, _box_iou)
        unique_tracks = _coalesce_duplicate_plates(valid_tracks, frames)
        return {"duration": round(duration, 2), "fps": round(fps, 2), "frame_width": output_width, "frame_height": output_height, "sample_fps": round(fps / stride, 2), "mode": mode, "frames": frames, "tracks": unique_tracks, "ninerouter": ninerouter}
    finally:
        capture.release()
