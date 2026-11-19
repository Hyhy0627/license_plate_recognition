"""Plate detection, OCR and track voting integrated into the ALPR backend.

Adapted from appStreamlit.py at revision f1c732e2270becc44df1de6529372f63ef251076.
Source and local adaptations are documented in docs/video_onnx.md (source attribution section).
This module has no Streamlit dependency or UI side effects.
"""

from collections import Counter, defaultdict
import re

import cv2
import numpy as np


class PlateReader:
    """YOLO detector with OCR, tracking buffers, and plate voting."""

    PLATE_4W = re.compile(r"^[0-9]{2}[A-Z]{1,2}[0-9]{4,6}$")
    PLATE_2LINE = re.compile(r"^[0-9]{2}[A-Z][0-9]{1,2}[0-9]{4,5}$")
    MIN_OCR_TEXT_LENGTH = 3

    def __init__(
        self, model_path=None, ocr_model_path=None, ocr_config_path=None,
        min_track_reads=2, use_tracking=True, preprocess_ocr=True, ocr_options=None,
    ):
        self.model = None
        if model_path is not None:
            from ultralytics import YOLO
            self.model = YOLO(str(model_path))
        self.min_track_reads = max(int(min_track_reads), 1)
        self.use_tracking = use_tracking
        self.preprocess_ocr = preprocess_ocr
        self.track_buffer = defaultdict(list)
        self.track_best_image = {}
        self.synthetic_track_id = 0
        self.tracking_fallback_frames = 0
        self.recognizer = None
        if ocr_model_path and ocr_config_path:
            from fast_plate_ocr import LicensePlateRecognizer
            self.recognizer = LicensePlateRecognizer(
                onnx_model_path=str(ocr_model_path),
                plate_config_path=str(ocr_config_path),
                device="auto", **(ocr_options or {}),
            )
        self.ocr_enabled = self.recognizer is not None

    @staticmethod
    def _check_cuda():
        try:
            import torch

            return torch.cuda.is_available()
        except Exception:
            return False

    @staticmethod
    def clean_text(value):
        if not value:
            return ""
        value = value.upper().replace("_", "").replace(" ", "").replace("-", "").strip()
        return re.sub(r"[^A-Z0-9]", "", value)

    @staticmethod
    def _normalize_char_confs(text, confs):
        if confs is None:
            return [0.0] * len(text)

        arr = np.asarray(confs, dtype=float).flatten()
        if len(arr) == 0:
            return [0.0] * len(text)

        values = arr[: len(text)].tolist()
        if len(values) < len(text):
            values.extend([float(np.mean(arr))] * (len(text) - len(values)))
        return [float(max(0.0, min(1.0, value))) for value in values]

    def validate_plate(self, plate_text):
        clean = self.clean_text(plate_text)
        if len(clean) < 7:
            return False
        return bool(self.PLATE_4W.match(clean) or self.PLATE_2LINE.match(clean))

    def preprocess_plate(self, plate_img):
        if plate_img is None or plate_img.size == 0:
            return None

        if len(plate_img.shape) == 2:
            plate_img = cv2.cvtColor(plate_img, cv2.COLOR_GRAY2BGR)

        h, w = plate_img.shape[:2]
        if h < 20 or w < 60:
            return None

        if h < 50 or w < 100:
            scale = max(64 / h, 200 / w)
            plate_img = cv2.resize(
                plate_img,
                (max(1, int(w * scale)), max(1, int(h * scale))),
                interpolation=cv2.INTER_CUBIC,
            )

        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        return cv2.fastNlMeansDenoisingColored(enhanced, None, 5, 5, 7, 15)

    def run_ocr(self, plate_img):
        """Read a BGR crop using Fast Plate OCR 1.1's prediction objects.

        Padding slots are removed before calculating character confidence.
        The API adapter disables preprocessing to preserve its existing input.
        """
        if self.recognizer is None or plate_img is None or plate_img.size == 0:
            return None, 0.0, []
        processed = self.preprocess_plate(plate_img) if getattr(self, "preprocess_ocr", False) else plate_img
        if processed is None:
            return None, 0.0, []
        if processed.ndim == 2:
            rgb = cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        predictions = self.recognizer.run(rgb, return_confidence=True, remove_pad_char=False)
        if not predictions:
            return None, 0.0, []
        prediction = predictions[0]
        slots = self._normalize_char_confs(prediction.plate, prediction.char_probs)
        indices = [i for i, char in enumerate(prediction.plate) if char.isascii() and char.isalnum()]
        text = self.clean_text(prediction.plate)
        char_confs = [slots[i] for i in indices]
        confidence = float(np.mean(char_confs)) if char_confs else 0.0
        return text or None, confidence, char_confs

    @staticmethod
    def crop_with_padding(frame, bbox, padding_ratio=0.10):
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        box_w = max(1, x2 - x1)
        box_h = max(1, y2 - y1)
        pad_x = max(int(box_w * padding_ratio), 4)
        pad_y = max(int(box_h * padding_ratio), 4)

        x1_c = max(0, x1 - pad_x)
        y1_c = max(0, y1 - pad_y)
        x2_c = min(w, x2 + pad_x)
        y2_c = min(h, y2 + pad_y)
        return frame[y1_c:y2_c, x1_c:x2_c]

    def vote_plate(self, track_id, min_reads=None):
        min_reads = min_reads or self.min_track_reads
        reads = self.track_buffer.get(track_id, [])
        if len(reads) < min_reads:
            return None, 0.0

        candidates = [
            (text, char_confs)
            for text, char_confs, _frame_num, _det_conf in reads
            if text and len(text) >= self.MIN_OCR_TEXT_LENGTH
        ]
        if not candidates:
            return None, 0.0

        target_len = Counter(len(text) for text, _ in candidates).most_common(1)[0][0]
        same_len = [(text, confs) for text, confs in candidates if len(text) == target_len]
        scores = [defaultdict(float) for _ in range(target_len)]

        for text, char_confs in same_len:
            normalized = self._normalize_char_confs(text, char_confs)
            for idx, (char, conf) in enumerate(zip(text, normalized)):
                scores[idx][char] += max(conf, 0.01)

        voted_chars = []
        position_conf = []
        for score in scores:
            if not score:
                continue
            total = sum(score.values())
            winner, winner_score = max(score.items(), key=lambda item: item[1])
            voted_chars.append(winner)
            position_conf.append(winner_score / total if total else 0.0)

        plate = "".join(voted_chars)
        avg_conf = float(np.mean(position_conf)) if position_conf else 0.0
        return plate, avg_conf

    def _best_read_for_track(self, track_id):
        reads = self.track_buffer.get(track_id, [])
        if not reads:
            return None
        return max(reads, key=lambda item: (float(np.mean(item[1])) if item[1] else 0.0, item[3]))

    def _build_final_detection(self, track_id, image_budget_remaining):
        voted_plate, voted_conf = self.vote_plate(track_id)

        best_read = self._best_read_for_track(track_id)
        if best_read is None:
            return None

        best_text, best_char_confs, frame_num, det_conf = best_read
        if not voted_plate:
            fallback_text = self.clean_text(best_text)
            if len(fallback_text) < self.MIN_OCR_TEXT_LENGTH:
                return None
            voted_plate = fallback_text
            voted_conf = float(np.mean(best_char_confs)) if best_char_confs else 0.0

        best_image = self.track_best_image.get(track_id)
        stored_image = best_image.copy() if best_image is not None and image_budget_remaining > 0 else None

        return {
            "track_id": track_id,
            "plate": voted_plate,
            "confidence": det_conf,
            "ocr_confidence": voted_conf,
            "is_valid": self.validate_plate(voted_plate),
            "frame": frame_num,
            "timestamp": None,
            "image": stored_image,
            "read_count": len(self.track_buffer.get(track_id, [])),
        }

    def finalize_lost_tracks(self, active_ids, image_budget_remaining):
        finalized = []
        active_set = set(active_ids)
        lost_ids = [track_id for track_id in list(self.track_buffer.keys()) if track_id not in active_set]

        for track_id in lost_ids:
            detection = self._build_final_detection(track_id, image_budget_remaining - len(finalized))
            if detection:
                finalized.append(detection)
            self.track_buffer.pop(track_id, None)
            self.track_best_image.pop(track_id, None)

        return finalized

    def finalize_all_tracks(self, image_budget_remaining):
        finalized = []
        for track_id in list(self.track_buffer.keys()):
            detection = self._build_final_detection(track_id, image_budget_remaining - len(finalized))
            if detection:
                finalized.append(detection)
            self.track_buffer.pop(track_id, None)
            self.track_best_image.pop(track_id, None)
        return finalized

    def _run_yolo(self, frame, min_confidence):
        if self.use_tracking:
            try:
                results = self.model.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    verbose=False,
                    conf=min_confidence,
                )
                return results, True
            except Exception:
                self.tracking_fallback_frames += 1

        return self.model(frame, verbose=False, conf=min_confidence), False

    def process_frame(self, frame, frame_num, min_confidence=0.35, image_budget_remaining=0):
        results, tracking_active = self._run_yolo(frame, min_confidence)
        annotated_frame = frame.copy()
        active_ids = []
        immediate_detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                conf = float(box.conf[0]) if box.conf is not None else 0.0
                if conf < min_confidence:
                    continue

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cropped = self.crop_with_padding(frame, (x1, y1, x2, y2))
                if cropped.size == 0:
                    continue

                if tracking_active and box.id is not None:
                    track_id = int(box.id[0])
                else:
                    self.synthetic_track_id += 1
                    track_id = -self.synthetic_track_id

                if tracking_active:
                    active_ids.append(track_id)
                plate_text, ocr_conf, char_confs = self.run_ocr(cropped)
                display_text = plate_text or "UNKNOWN"
                is_valid = self.validate_plate(display_text)

                if plate_text and tracking_active:
                    self.track_buffer[track_id].append((plate_text, char_confs, frame_num, conf))
                    current_best = self.track_best_image.get(track_id)
                    if current_best is None or ocr_conf >= self._best_image_conf(track_id):
                        self.track_best_image[track_id] = cropped.copy()

                voted_text, voted_conf = self.vote_plate(track_id) if tracking_active else (None, 0.0)
                if voted_text:
                    display_text = voted_text
                    ocr_conf = voted_conf
                    is_valid = self.validate_plate(voted_text)

                color = (0, 180, 0) if is_valid else (0, 0, 220)
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                label = f"ID {track_id}: {display_text} ({ocr_conf:.2f})"
                self._draw_label(annotated_frame, label, x1, y1, color)

                should_emit_immediate = not tracking_active and (plate_text or not self.ocr_enabled)
                if should_emit_immediate:
                    immediate_detections.append(
                        {
                            "track_id": track_id,
                            "plate": plate_text or "UNKNOWN",
                            "confidence": conf,
                            "ocr_confidence": ocr_conf,
                            "is_valid": is_valid,
                            "frame": frame_num,
                            "timestamp": None,
                            "image": cropped.copy() if image_budget_remaining > len(immediate_detections) else None,
                            "read_count": 1,
                        }
                    )

        finalized = self.finalize_lost_tracks(active_ids, image_budget_remaining) if tracking_active else []
        return annotated_frame, immediate_detections + finalized

    def _best_image_conf(self, track_id):
        best_read = self._best_read_for_track(track_id)
        if best_read is None or not best_read[1]:
            return 0.0
        return float(np.mean(best_read[1]))

    @staticmethod
    def _draw_label(frame, label, x, y, color):
        label_y = max(y, 20)
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(frame, (x, label_y - label_h - 8), (x + label_w + 4, label_y), color, -1)
        cv2.putText(
            frame,
            label,
            (x + 2, label_y - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
        )
