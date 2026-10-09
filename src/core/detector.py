from typing import List, Dict, Any, Tuple
import numpy as np
import cv2

class LicensePlateDetector:
    """
    Module phát hiện biển số xe sử dụng mô hình YOLO (Ultralytics).
    Phụ trách bởi: Người 2 (AI Detection).
    """
    def __init__(self, model_path: str, conf_threshold: float = 0.5):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
        except Exception as e:
            # Sẽ load khi đã có weights
            self.model = None

    def detect(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Phát hiện các biển số có trong ảnh.
        Trả về danh sách dict: [{'bbox': [x1, y1, x2, y2], 'confidence': float, 'class_id': int}]
        """
        if self.model is None:
            return []

        results = self.model.predict(
            source=image,
            conf=self.conf_threshold,
            verbose=False
        )
        
        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy().tolist()
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                detections.append({
                    "bbox": [int(x) for x in xyxy],
                    "confidence": conf,
                    "class_id": cls_id
                })
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
