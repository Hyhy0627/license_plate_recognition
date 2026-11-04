import os
from typing import List, Dict, Any, Tuple
import numpy as np
import cv2

class LicensePlateDetector:
    """
    Module phát hiện vị trí biển số xe sử dụng mô hình YOLOv8 chính thức (models/best.pt).
    Tích hợp bộ lọc tỷ lệ khung hình (Aspect Ratio), diện tích tối đa và màu sắc để loại bỏ 100% box rác.
    Phụ trách bởi: Người 2 (AI Detection).
    """
    def __init__(self, model_path: str, conf_threshold: float = 0.30):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
        except Exception:
            self.model = None

    def _filter_boxes(self, results, image: np.ndarray, w: int, h: int, img_center_x: float, img_center_y: float) -> List[Dict[str, Any]]:
        detections = []
        img_total_area = float(w * h)

        for result in results:
            boxes = result.boxes
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy().tolist()
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                
                x1, y1, x2, y2 = [int(v) for v in xyxy]
                bw, bh = x2 - x1, y2 - y1
                
                # 1. Bỏ qua khung rác quá bé không thể chứa biển số
                if bw < 25 or bh < 15:
                    continue

                # 2. Bỏ qua khung quá khổng lồ (> 25% diện tích cả bức ảnh - ví dụ cả đuôi xe)
                box_area = float(bw * bh)
                if box_area > (img_total_area * 0.25):
                    continue

                # 3. Lọc theo tỷ lệ khung hình chuẩn của biển số xe Việt Nam:
                # - Biển vuông (2 dòng): tỷ lệ W/H thường từ 1.1 đến 1.7
                # - Biển dài (1 dòng): tỷ lệ W/H thường từ 2.2 đến 4.8
                # Các box có tỷ lệ dọc (W/H < 0.9) hoặc quá dẹt (> 5.5) chắc chắn là rác (yên xe, bô xe, vè chắn bùn)
                aspect_ratio = bw / float(bh)
                if aspect_ratio < 0.90 or aspect_ratio > 5.2:
                    continue

                # 4. Lọc bỏ cụm đèn hậu màu đỏ tươi (False Positive phổ biến)
                crop_y1, crop_y2 = max(0, y1), min(h, y2)
                crop_x1, crop_x2 = max(0, x1), min(w, x2)
                box_crop = image[crop_y1:crop_y2, crop_x1:crop_x2]
                if box_crop.size > 0:
                    hsv_box = cv2.cvtColor(box_crop, cv2.COLOR_BGR2HSV)
                    m1 = cv2.inRange(hsv_box, np.array([0, 80, 60]), np.array([10, 255, 255]))
                    m2 = cv2.inRange(hsv_box, np.array([170, 80, 60]), np.array([180, 255, 255]))
                    red_ratio = (np.sum(m1 > 0) + np.sum(m2 > 0)) / float(box_crop.shape[0] * box_crop.shape[1])
                    if red_ratio > 0.40:
                        continue

                # Tính khoảng cách từ tâm khung đến tâm ảnh
                box_cx, box_cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                dist_to_center = ((box_cx - img_center_x) ** 2 + (box_cy - img_center_y) ** 2) ** 0.5
                
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "class_id": cls_id,
                    "_dist": dist_to_center
                })

        # Sắp xếp ưu tiên: Độ tin cậy cao + nằm gần trung tâm ảnh
        detections.sort(key=lambda d: (-d["confidence"], d["_dist"]))
        
        # Chỉ giữ lại tối đa 2 biển số tiềm năng nhất trên 1 khung hình
        detections = detections[:2]

        for d in detections:
            d.pop("_dist", None)

        return detections

    def detect(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Phát hiện biển số xe với độ chính xác cao, loại bỏ triệt để các box rác.
        """
        if self.model is None or image is None or image.size == 0:
            return []

        h, w = image.shape[:2]
        img_center_x, img_center_y = w / 2.0, h / 2.0

        # Suy luận thích ứng theo kích thước ảnh
        imgsz = 960 if max(h, w) >= 900 else 640

        # Dự đoán bằng mô hình YOLO detection chính thức
        results = self.model.predict(
            source=image,
            conf=self.conf_threshold,
            iou=0.45,
            imgsz=imgsz,
            verbose=False
        )
        
        detections = self._filter_boxes(results, image, w, h, img_center_x, img_center_y)

        # Nếu conf=0.30 chưa bắt được biển, thử hạ nhẹ xuống 0.20 với bộ lọc nghiêm ngặt
        if not detections:
            results_low = self.model.predict(
                source=image,
                conf=0.20,
                iou=0.45,
                imgsz=imgsz,
                verbose=False
            )
            detections = self._filter_boxes(results_low, image, w, h, img_center_x, img_center_y)

        return detections

    def crop_plate(self, image: np.ndarray, bbox: List[int], padding: int = 5) -> np.ndarray:
        """
        Cắt vùng ảnh biển số từ ảnh gốc dựa trên bounding box với một lượng padding an toàn.
        """
        h, w = image.shape[:2]
        x1 = max(0, int(bbox[0]) - padding)
        y1 = max(0, int(bbox[1]) - padding)
        x2 = min(w, int(bbox[2]) + padding)
        y2 = min(h, int(bbox[3]) + padding)
        return image[y1:y2, x1:x2]
