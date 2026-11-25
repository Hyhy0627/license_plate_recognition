"""Keep frame evidence for readable plates whose vehicle wasn't tracked."""

from collections import defaultdict

from src.core.ocr.postprocessor import PlatePostprocessor


class UnassignedPlates:
    def __init__(self):
        self.sightings = defaultdict(list)
        self.last_seen = float("-inf")

    def observe(self, second, frame, plates, detector, ocr):
        for plate in plates:
            crop = detector.crop_plate(frame, plate["original_bbox"])
            if crop is None or not crop.size or ocr is None:
                continue
            read = ocr.recognize_local_yolo(crop)
            confidence = float(read.get("avg_conf", 0))
            if confidence < 0.70:
                continue
            number = PlatePostprocessor.format_vietnamese_plate(
                read.get("raw_text", ""), read.get("plate_type"),
                read.get("text_lines"), confidence)
            if PlatePostprocessor.validate_plate(number):
                self.sightings[number].append((second, plate["bbox"], confidence))
                self.last_seen = second

    def add_confirmed(self, tracks, frames, sample_period, box_iou):
        frame_at = {frame["time"]: frame for frame in frames}
        next_id = max((track["track_id"] for track in tracks), default=0) + 1
        for number, readings in self.sightings.items():
            # Agree on both text and position across distinct sampled frames.
            # A single OCR result, or two boxes in one frame, cannot confirm a plate.
            sequences = []
            for reading in readings:
                second, bbox, _ = reading
                matches = [(box_iou(seq[-1][1], bbox), i) for i, seq in enumerate(sequences)
                           if 0 < second - seq[-1][0] <= 2 * sample_period + 0.002]
                overlap, index = max(matches, default=(0, 0))
                if overlap >= 0.30:
                    sequences[index].append(reading)
                else:
                    sequences.append([reading])
            for seq in sequences:
                if len(seq) < 2:
                    continue
                tracks.append({
                    "track_id": next_id, "vehicle_type": "Biển số", "first_seen": seq[0][0],
                    "last_seen": seq[-1][0], "plate_number": number,
                    "plate_confidence": round(max(read[2] for read in seq), 3),
                    "plate_observations": len(seq), "plate_candidates": [number], "plate_status": "confirmed",
                })
                for second, bbox, _ in seq:
                    frame_at[second]["vehicles"].append({
                        "track_id": next_id, "vehicle_type": "Biển số", "bbox": bbox,
                    })
                next_id += 1
