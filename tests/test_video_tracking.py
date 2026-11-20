import tempfile
from collections import defaultdict
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from src.core.video_tracker import _rescue_plates_with_ninerouter, _resolve_overlapping_vehicle_types, _stable_vehicle_type, associate_plates, merge_video_results, plate_fits_vehicle, process_video, winning_plate
from src.config import BASE_DIR


def test_plate_assignment_uses_containing_vehicle():
    vehicles = [
        {"track_id": 1, "bbox": [0, 0, 100, 100]},
        {"track_id": 2, "bbox": [120, 0, 220, 100]},
    ]
    plates = [{"bbox": [20, 70, 60, 90]}, {"bbox": [150, 70, 190, 90]}, {"bbox": [240, 70, 280, 90]}]
    assigned = associate_plates(vehicles, plates)
    assert [item["bbox"] for item in assigned[1]] == [[20, 70, 60, 90]]
    assert [item["bbox"] for item in assigned[2]] == [[150, 70, 190, 90]]


def test_repeated_plate_reading_beats_single_high_confidence_error():
    observations = [
        {"plate_number": "30A-123.45", "confidence": 0.66},
        {"plate_number": "30A-128.45", "confidence": 0.98},
        {"plate_number": "30A-123.45", "confidence": 0.72},
    ]
    assert winning_plate(observations) == {"plate_number": "30A-123.45", "plate_confidence": 0.72, "plate_observations": 2}


def test_combined_result_keeps_stable_ids_and_exposes_conflicting_reads():
    def track(track_id, box, plate):
        return {"track_id": track_id, "vehicle_type": "Ô tô", "first_seen": 0, "last_seen": 1,
                "plate_number": plate, "plate_confidence": 0.8 if plate else None,
                "plate_observations": 2 if plate else 0, "bbox": box}

    def result(mode, first, second):
        tracks = [track(*first), track(*second)]
        frames = [{"time": time, "vehicles": [{"track_id": item["track_id"], "vehicle_type": "Ô tô", "bbox": item["bbox"]} for item in tracks]} for time in (0.0, 1.0)]
        for item in tracks:
            item.pop("bbox")
        return {"mode": mode, "frame_width": 320, "frame_height": 180, "sample_fps": 2,
                "duration": 2, "frames": frames, "tracks": tracks}

    fast = result("fast", (1, [0, 0, 100, 100], "81A 233.34"), (2, [150, 0, 250, 100], "51C-868.49"))
    detailed = result("detailed", (10, [2, 1, 102, 101], "61A 233.34"), (20, [152, 1, 252, 101], None))
    merged = merge_video_results(fast, detailed)

    assert merged["mode"] == "combined"
    assert [item["track_id"] for item in merged["tracks"]] == [1, 2]
    assert merged["tracks"][0]["plate_number"] == "61A 233.34"
    assert merged["tracks"][0]["plate_candidates"] == ["61A 233.34", "81A 233.34"]
    assert merged["tracks"][0]["plate_status"] == "needs_review"
    assert merged["tracks"][1]["plate_status"] == "tentative"


def test_combined_result_matches_truck_relabelled_as_bus():
    def result(mode, track_id, vehicle_type):
        return {"mode": mode, "frame_width": 320, "frame_height": 180, "sample_fps": 2,
                "duration": 2, "frames": [
                    {"time": time, "vehicles": [{"track_id": track_id, "vehicle_type": vehicle_type, "bbox": [20, 20, 180, 150]}]}
                    for time in (0.0, 1.0)],
                "tracks": [{"track_id": track_id, "vehicle_type": vehicle_type, "first_seen": 0, "last_seen": 1,
                            "plate_number": "51C-868.49", "plate_confidence": 0.8, "plate_observations": 1}]}

    merged = merge_video_results(result("fast", 38, "Xe tải"), result("detailed", 56, "Xe buýt"))
    assert len(merged["tracks"]) == 1
    assert merged["tracks"][0]["track_id"] == 38
    assert merged["tracks"][0]["plate_status"] == "confirmed"


def test_vehicle_type_uses_whole_track_and_stabilizes_frame_labels():
    class Box:
        id = np.array([4])
        xyxy = np.array([[10, 10, 200, 130]])

        def __init__(self, vehicle_class):
            self.cls = np.array([vehicle_class])

    class Boxes(list):
        id = np.array([4])

    class Model:
        def __init__(self, _path):
            self.calls = 0

        def track(self, *_args, **_kwargs):
            vehicle_class = 5 if self.calls == 0 else 7
            self.calls += 1
            return [SimpleNamespace(boxes=Boxes([Box(vehicle_class)]))]

    class PlateDetector:
        def detect(self, _frame, **_kwargs):
            return []

    with tempfile.TemporaryDirectory(dir=BASE_DIR / "data") as directory:
        video_path = Path(directory) / "clip.avi"
        weight_path = Path(directory) / "vehicle.pt"
        weight_path.touch()
        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 180))
        assert writer.isOpened()
        for _ in range(25):
            writer.write(np.full((180, 320, 3), 120, dtype=np.uint8))
        writer.release()
        with patch("ultralytics.YOLO", Model):
            result = process_video(video_path, weight_path, PlateDetector(), None, Lock(), lambda _: None)

    assert result["tracks"][0]["vehicle_type"] == "Xe tải"
    assert {vehicle["vehicle_type"] for frame in result["frames"] for vehicle in frame["vehicles"]} == {"Xe tải"}
    assert _stable_vehicle_type(["Xe buýt", "Xe buýt", "Xe tải", "Xe tải", "Xe tải"]) == "Chưa rõ xe tải hay xe buýt"
    assert _stable_vehicle_type(["Xe buýt"]) == "Chưa rõ xe tải hay xe buýt"


def test_short_duplicate_track_inherits_long_truck_label():
    tracks = {1: {"vehicle_type": "Xe tải"}, 2: {"vehicle_type": "Xe buýt"}}
    frames = []
    for second in range(9):
        vehicles = [{"track_id": 1, "vehicle_type": "Xe tải", "bbox": [10, 10, 110, 110]}]
        if second in (3, 4):
            vehicles.append({"track_id": 2, "vehicle_type": "Xe buýt", "bbox": [12, 12, 108, 108]})
        frames.append({"time": float(second), "vehicles": vehicles})

    _resolve_overlapping_vehicle_types(tracks, frames)

    assert tracks[2]["vehicle_type"] == "Xe tải"
    assert all(vehicle["vehicle_type"] == "Xe tải" for frame in frames for vehicle in frame["vehicles"])


def test_ninerouter_reads_one_detected_plate_crop_for_unreadable_track():
    class Capture:
        def set(self, *_args):
            pass

        def read(self):
            return True, np.full((180, 320, 3), 120, dtype=np.uint8)

    class Detector:
        def detect(self, _crop, **_kwargs):
            return [{"bbox": [40, 60, 120, 90], "confidence": 0.8}]

        def crop_plate(self, crop, bbox):
            x1, y1, x2, y2 = bbox
            return crop[y1:y2, x1:x2]

    class Client:
        def __init__(self):
            self.calls = 0

        def is_available(self):
            return True

        def recognize_plate(self, crop, **_kwargs):
            assert crop.size
            self.calls += 1
            return {"raw_text": "30A12345", "plate_type": "one_line", "confidence": 0.88}

        def detect_and_recognize_plate(self, _crop, **_kwargs):
            raise AssertionError("A detected plate should be sent as a crop")

    client = Client()
    tracks = {4: {"vehicle_type": "Ô tô", "first_seen": 0.0, "last_seen": 1.0}}
    frames = [{"time": second, "vehicles": [{"track_id": 4, "bbox": [10, 10, 200, 150]}]}
              for second in (0.0, 1.0)]
    observations = {4: []}
    result = _rescue_plates_with_ninerouter(Capture(), frames, tracks, observations, Detector(),
                                            SimpleNamespace(ninerouter_client=client), Lock(), 10, 1.0, lambda _: None)

    assert client.calls == 1
    assert result == {"status": "available", "attempts": 1, "recognized": 1}
    assert observations[4] == [{"plate_number": "30A-123.45", "confidence": 0.88}]


def test_ninerouter_prefers_plate_seen_in_an_earlier_frame():
    class Capture:
        def set(self, *_args):
            raise AssertionError("A saved plate crop should avoid seeking the video")

    class Detector:
        def detect(self, *_args, **_kwargs):
            raise AssertionError("A saved plate crop should avoid another detection")

    class Client:
        def is_available(self):
            return True

        def recognize_plate(self, crop, **_kwargs):
            assert crop.shape == (30, 80, 3)
            return {"raw_text": "30A12345", "plate_type": "one_line", "confidence": 0.9}

    frames = [{"time": 0.0, "vehicles": [{"track_id": 4, "bbox": [10, 10, 200, 150]}]}]
    tracks = {4: {"vehicle_type": "Ô tô", "first_seen": 0.0, "last_seen": 0.0}}
    observations = defaultdict(list)
    result = _rescue_plates_with_ninerouter(Capture(), frames, tracks, observations, Detector(),
                                            SimpleNamespace(ninerouter_client=Client()), Lock(), 10, 1.0,
                                            lambda _: None, {4: (0.8, np.ones((30, 80, 3), dtype=np.uint8))})
    assert result == {"status": "available", "attempts": 1, "recognized": 1}


def test_ninerouter_vehicle_crop_requires_a_located_plate():
    class Capture:
        def set(self, *_args):
            pass

        def read(self):
            return True, np.full((180, 320, 3), 120, dtype=np.uint8)

    class Detector:
        def detect(self, _crop, **_kwargs):
            return []

    class Client:
        def __init__(self, bbox):
            self.bbox = bbox

        def is_available(self):
            return True

        def detect_and_recognize_plate(self, _crop, **_kwargs):
            return {"raw_text": "30A12345", "plate_type": "one_line", "confidence": 0.9, "bbox": self.bbox}

    observations = defaultdict(list)
    frames = [{"time": second, "vehicles": [{"track_id": 4, "bbox": [10, 10, 200, 150]}]}
              for second in (0.0, 1.0)]
    tracks = {4: {"vehicle_type": "Ô tô", "first_seen": 0.0, "last_seen": 1.0}}
    _rescue_plates_with_ninerouter(Capture(), frames, tracks, observations, Detector(),
                                   SimpleNamespace(ninerouter_client=Client(None)), Lock(), 10, 1.0, lambda _: None)
    assert observations[4] == []
    _rescue_plates_with_ninerouter(Capture(), frames, tracks, observations, Detector(),
                                   SimpleNamespace(ninerouter_client=Client([40, 60, 120, 90])), Lock(), 10, 1.0, lambda _: None)
    assert observations[4] == [{"plate_number": "30A-123.45", "confidence": 0.9}]


def test_ninerouter_calls_are_bounded_and_offline_gateway_is_skipped():
    class Capture:
        def set(self, *_args):
            pass

        def read(self):
            return True, np.full((180, 320, 3), 120, dtype=np.uint8)

    class Detector:
        def detect(self, _crop, **_kwargs):
            return []

    class Client:
        def __init__(self, available):
            self.available = available
            self.calls = 0

        def is_available(self):
            return self.available

        def detect_and_recognize_plate(self, _crop, **_kwargs):
            self.calls += 1
            return {"raw_text": "", "bbox": None}

    tracks = {track_id: {"vehicle_type": "Ô tô", "first_seen": 0.0, "last_seen": 1.0}
              for track_id in range(10)}
    frames = [{"time": second, "vehicles": [
        {"track_id": track_id, "bbox": [10, 10, 200, 150]} for track_id in tracks]}
              for second in (0.0, 1.0)]
    offline, online = Client(False), Client(True)
    statuses = []
    for client in (offline, online):
        statuses.append(_rescue_plates_with_ninerouter(Capture(), frames, tracks, defaultdict(list), Detector(),
                                                       SimpleNamespace(ninerouter_client=client), Lock(), 10, 1.0, lambda _: None))
    assert offline.calls == 0
    assert online.calls == 6
    assert statuses == [{"status": "unavailable", "attempts": 0, "recognized": 0},
                        {"status": "available", "attempts": 6, "recognized": 0}]


def test_motorcycle_series_is_not_attached_to_bus_and_duplicate_plate_has_one_row():
    assert plate_fits_vehicle("59-L2 1431", "Xe máy")
    assert not plate_fits_vehicle("59-L2 1431", "Xe buýt")
    assert plate_fits_vehicle("51B-053.49", "Xe tải")
    fast = {"mode": "fast", "frame_width": 320, "frame_height": 180, "sample_fps": 2, "duration": 2,
            "frames": [{"time": 0.0, "vehicles": [
                {"track_id": 1, "vehicle_type": "Ô tô", "bbox": [0, 0, 100, 100]},
                {"track_id": 2, "vehicle_type": "Xe tải", "bbox": [2, 1, 102, 101]}]}],
            "tracks": [{"track_id": track_id, "vehicle_type": kind, "first_seen": 0, "last_seen": 1,
                        "plate_number": "51B-053.49", "plate_confidence": 0.8, "plate_observations": 1}
                       for track_id, kind in ((1, "Ô tô"), (2, "Xe tải"))]}
    detailed = {**fast, "mode": "detailed", "frames": [], "tracks": []}
    merged = merge_video_results(fast, detailed)
    assert len(merged["tracks"]) == 1
    assert len(merged["frames"][0]["vehicles"]) == 1


def test_short_video_tracks_and_attaches_valid_plate():
    class Box:
        id = np.array([7])
        cls = np.array([2])
        xyxy = np.array([[10, 10, 200, 130]])

    class Boxes(list):
        id = np.array([7])

    class Model:
        def __init__(self, _path):
            pass

        def track(self, *_args, **_kwargs):
            return [SimpleNamespace(boxes=Boxes([Box()]))]

    class PlateDetector:
        def __init__(self):
            self.calls = 0

        def detect(self, _frame, **_kwargs):
            self.calls += 1
            return [{"bbox": [80, 100, 140, 120], "confidence": 0.9}]

        def crop_plate(self, frame, bbox):
            x1, y1, x2, y2 = bbox
            return frame[y1:y2, x1:x2]

    class LatePlateDetector(PlateDetector):
        def detect(self, frame, **kwargs):
            self.calls += 1
            if self.calls < 3:
                return []
            return [{"bbox": [80, 100, 140, 120], "confidence": 0.9}]

    class OCR:
        def recognize_local_yolo(self, _crop):
            return {"raw_text": "30A12345", "avg_conf": 0.8, "plate_type": "one_line"}

    with tempfile.TemporaryDirectory(dir=BASE_DIR / "data") as directory:
        video_path = Path(directory) / "clip.avi"
        weight_path = Path(directory) / "vehicle.pt"
        weight_path.touch()
        writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 180))
        assert writer.isOpened()
        for _ in range(50):
            writer.write(np.full((180, 320, 3), 120, dtype=np.uint8))
        writer.release()
        progress = []
        detector = PlateDetector()
        with patch("ultralytics.YOLO", Model):
            result = process_video(video_path, weight_path, detector, OCR(), Lock(), progress.append)
            detailed = process_video(video_path, weight_path, PlateDetector(), OCR(), Lock(), lambda _: None, mode="detailed")
            late = process_video(video_path, weight_path, LatePlateDetector(), OCR(), Lock(), lambda _: None)

    assert len(result["frames"]) == 25
    assert result["mode"] == "fast"
    assert len(detailed["frames"]) == 25
    assert detailed["mode"] == "detailed"
    assert result["tracks"][0]["track_id"] == 7
    assert result["tracks"][0]["plate_number"] == "30A-123.45"
    assert result["tracks"][0]["plate_observations"] == 2
    assert detector.calls == 2
    assert late["tracks"][0]["plate_number"] == "30A-123.45"
    assert progress[-1] == 100


def test_detailed_pass_reads_plate_visible_only_in_vehicle_crop():
    class Box:
        id = np.array([4])
        cls = np.array([3])
        xyxy = np.array([[10, 10, 250, 150]])

    class Boxes(list):
        id = np.array([4])

    class Model:
        def __init__(self, _path):
            pass

        def track(self, *_args, **_kwargs):
            return [SimpleNamespace(boxes=Boxes([Box()]))]

    class PlateDetector:
        def detect(self, frame, **_kwargs):
            return [{"bbox": [80, 80, 140, 110], "confidence": 0.8}] if frame.shape[1] < 300 else []

        def crop_plate(self, frame, bbox):
            x1, y1, x2, y2 = bbox
            return frame[y1:y2, x1:x2]

    class OCR:
        def recognize_local_yolo(self, _crop):
            return {"raw_text": "61F120627", "avg_conf": 0.8, "plate_type": "two_line"}

    with tempfile.TemporaryDirectory(dir=BASE_DIR / "data") as directory:
        path = Path(directory) / "clip.avi"
        weight_path = Path(directory) / "vehicle.pt"
        weight_path.touch()
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (320, 180))
        for _ in range(20):
            writer.write(np.full((180, 320, 3), 120, dtype=np.uint8))
        writer.release()
        with patch("ultralytics.YOLO", Model):
            result = process_video(path, weight_path, PlateDetector(), OCR(), Lock(), lambda _: None, mode="detailed")

    assert result["tracks"][0]["plate_number"] is not None
