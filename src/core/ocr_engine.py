import os
import cv2
import numpy as np
from typing import Dict, Any, List
from src.core.preprocessor import PlatePreprocessor
from src.config import settings, BASE_DIR
from src.utils.logger import logger

class PlateOCREngine:
    """
    Module OCR nhận dạng chuỗi ký tự trên ảnh biển số xe.
    Hỗ trợ kiến trúc Hybrid (Local YOLO OCR Siêu tốc + 9Router Vision AI Cứu cánh):
    1. Local YOLO Character Recognizer (LP_ocr.pt) kèm Auto-Invert màu cho biển xanh/đỏ (~20ms).
    2. 9Router Vision API (Gemini/GPT-4o) cứu cánh các ca khó, mờ, góc nghiêng hoặc bất thường.
    3. PaddleOCR / EasyOCR truyền thống dự phòng.
    """
    def __init__(self, engine_type: str = "hybrid"):
        self.engine_type = engine_type.lower()
        self.ninerouter_client = None
        self.yolo_ocr = None
        self.traditional_ocr = None
        self._init_ocr()

    def _init_ocr(self):
        # 1. Khởi tạo 9Router Vision Client (cho mode 9router hoặc hybrid)
        if self.engine_type in ["9router", "hybrid"]:
            try:
                from src.core.ninerouter_vision import NineRouterVisionClient
                self.ninerouter_client = NineRouterVisionClient()
                logger.info(f"9Router Vision Client initialized (Model: {settings.NINEROUTER_MODEL})")
            except Exception as e:
                logger.warning(f"Chưa khởi tạo 9Router Vision Client: {e}")
                self.ninerouter_client = None

        # 2. Khởi tạo Local YOLO Character Recognizer (LP_ocr.pt)
        yolo_ocr_path = os.path.join(BASE_DIR, "models", "LP_ocr.pt")
        if not os.path.exists(yolo_ocr_path):
            alt_path = os.path.join(BASE_DIR, "script", "copy", "models", "LP_ocr.pt")
            if os.path.exists(alt_path):
                yolo_ocr_path = alt_path

        if os.path.exists(yolo_ocr_path):
            try:
                from ultralytics import YOLO
                self.yolo_ocr = YOLO(yolo_ocr_path)
                logger.info(f"Local YOLO OCR initialized from {yolo_ocr_path}")
            except Exception as e:
                logger.error(f"Lỗi nạp Local YOLO OCR: {e}")
                self.yolo_ocr = None

        # 3. Engine truyền thống dự phòng (EasyOCR / PaddleOCR) được tải theo cơ chế Lazy Load khi cần
        self.traditional_ocr = None

    def _get_traditional_ocr(self):
        """Khởi tạo engine OCR truyền thống theo cơ chế Lazy-Loading để tối ưu thời gian khởi động."""
        if self.traditional_ocr is None:
            try:
                if self.engine_type == "easyocr":
                    import easyocr
                    self.traditional_ocr = easyocr.Reader(["en"], gpu=False)
                elif self.engine_type in ["paddleocr", "9router", "hybrid"]:
                    from paddleocr import PaddleOCR
                    self.traditional_ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            except Exception:
                self.traditional_ocr = None
        return self.traditional_ocr

    def _predict_yolo_boxes(self, img: np.ndarray, conf: float = 0.25) -> Dict[str, Any]:
        """Dự đoán ký tự bằng YOLO và sắp xếp theo dòng từ trái sang phải."""
        if self.yolo_ocr is None or img is None or img.size == 0:
            return {"raw_text": "", "plate_type": "unknown", "chars_count": 0, "avg_conf": 0.0}

        results = self.yolo_ocr.predict(img, conf=conf, verbose=False)
        boxes = results[0].boxes
        if len(boxes) == 0:
            return {"raw_text": "", "plate_type": "unknown", "chars_count": 0, "avg_conf": 0.0}

        chars = []
        confs = []
        for b in boxes:
            xyxy = b.xyxy[0].tolist()
            cls_id = int(b.cls[0])
            c_conf = float(b.conf[0])
            char_name = self.yolo_ocr.names[cls_id]
            chars.append(((xyxy[0], xyxy[1], xyxy[2], xyxy[3]), char_name))
            confs.append(c_conf)

        avg_conf = sum(confs) / len(confs) if confs else 0.0

        # Tính chiều cao trung bình để phân dòng
        heights = [box[3] - box[1] for box, _ in chars]
        avg_height = (sum(heights) / len(heights)) * 0.6 if heights else 15.0

        # Sắp xếp ký tự theo toạ độ Y để tách dòng
        sorted_by_y = sorted(chars, key=lambda c: c[0][1])
        rows = []
        current_row = []
        for c in sorted_by_y:
            if not current_row:
                current_row.append(c)
            else:
                prev_y = current_row[-1][0][1]
                if c[0][1] - prev_y > avg_height:
                    rows.append(current_row)
                    current_row = [c]
                else:
                    current_row.append(c)
        if current_row:
            rows.append(current_row)

        # Sắp xếp từng dòng từ trái sang phải theo toạ độ X
        text_parts = []
        for row in rows:
            sorted_row = sorted(row, key=lambda c: c[0][0])
            text_parts.append("".join(c[1] for c in sorted_row))

        raw_text = "".join(text_parts)
        plate_type = "two_line" if len(rows) > 1 else "one_line"

        return {
            "raw_text": raw_text,
            "plate_type": plate_type,
            "chars_count": len(raw_text),
            "avg_conf": avg_conf
        }

    def _recognize_with_yolo(self, plate_img: np.ndarray) -> Dict[str, Any]:
        """
        Nhận diện ký tự bằng Local YOLO OCR với cơ chế Auto-Invert màu thông minh:
        - Tự động nhận diện biển xanh/biển tối và đảo màu để đọc 100% chính xác.
        - Tự động so sánh giữa ảnh gốc và ảnh đảo màu để chọn phương án tối ưu nhất.
        """
        if self.yolo_ocr is None or plate_img is None or plate_img.size == 0:
            return {"raw_text": "", "plate_type": "unknown", "engine_used": "local_yolo"}

        # 1. Kiểm tra xem biển có phải nền tối / nền xanh (biển xanh 80A, 80B,...) hay không
        is_dark = PlatePreprocessor.is_dark_or_blue_plate(plate_img)

        if is_dark:
            # Biển tối: Ưu tiên chạy ảnh đảo màu trước
            inverted_img = PlatePreprocessor.invert_plate(plate_img)
            res_inv = self._predict_yolo_boxes(inverted_img, conf=0.25)
            if res_inv["chars_count"] >= 6:
                res_inv["engine_used"] = "local_yolo"
                return res_inv
            
            # Nếu đảo màu chưa đủ, thử thêm ảnh gốc
            res_orig = self._predict_yolo_boxes(plate_img, conf=0.25)
            best_res = res_inv if res_inv["chars_count"] >= res_orig["chars_count"] else res_orig
            best_res["engine_used"] = "local_yolo"
            return best_res
        else:
            # Biển trắng thông thường: Chạy ảnh gốc trước
            res_orig = self._predict_yolo_boxes(plate_img, conf=0.25)
            if res_orig["chars_count"] >= 7 and res_orig["avg_conf"] >= 0.70:
                res_orig["engine_used"] = "local_yolo"
                return res_orig

            # Nếu ảnh gốc ra ít ký tự, thử thêm đảo màu phòng trường hợp ngược sáng/bóng râm
            inverted_img = PlatePreprocessor.invert_plate(plate_img)
            res_inv = self._predict_yolo_boxes(inverted_img, conf=0.25)
            best_res = res_inv if res_inv["chars_count"] > res_orig["chars_count"] else res_orig
            best_res["engine_used"] = "local_yolo"
            return best_res

    def read_text(self, plate_img: np.ndarray) -> str:
        """Nhận diện chuỗi ký tự bằng EasyOCR/PaddleOCR dự phòng."""
        trad_ocr = self._get_traditional_ocr()
        if trad_ocr is None or plate_img is None or plate_img.size == 0:
            return ""

        text_result = ""
        try:
            if hasattr(trad_ocr, "readtext"):
                results = trad_ocr.readtext(plate_img)
                lines = [res[1] for res in results]
                text_result = "".join(lines)
            elif hasattr(trad_ocr, "ocr"):
                results = trad_ocr.ocr(plate_img, cls=True)
                if results and results[0]:
                    lines = [line[1][0] for line in results[0] if line and len(line) > 1]
                    text_result = "".join(lines)
        except Exception:
            text_result = ""

        return text_result

    def recognize_local_yolo(self, plate_img: np.ndarray) -> Dict[str, Any]:
        """
        Nhận diện chuỗi ký tự thuần Local YOLO OCR (LP_ocr.pt) kèm Auto-Invert màu (~20ms).
        Hoàn toàn Offline, siêu tốc.
        """
        return self._recognize_with_yolo(plate_img)

    def recognize_plate(self, plate_img: np.ndarray) -> Dict[str, Any]:
        """
        Nhận diện toàn bộ biển số theo chuẩn Hybrid Architecture:
        1. Local YOLO OCR siêu tốc (~20ms, Auto-Invert màu cho biển xanh/đỏ).
        2. Nếu Local AI đọc được chuỗi ký tự hợp lệ (>= 6 ký tự): Trả về ngay lập tức!
        3. Nếu Local AI đọc không ra hoặc ra quá ít (< 5 ký tự) VÀ có cấu hình 9Router:
           Tự động gọi 9Router Vision API để cứu trợ (Self-Healing).
        4. Dự phòng tiếp sang tiền xử lý nắn nghiêng + PaddleOCR/EasyOCR.
        """
        if plate_img is None or plate_img.size == 0:
            return {"raw_text": "", "plate_type": "unknown", "engine_used": "none"}

        # TH1: Chế độ ép buộc dùng 9Router từ đầu
        if self.engine_type == "9router" and self.ninerouter_client is not None:
            nine_res = self.ninerouter_client.recognize_plate(plate_img)
            if nine_res.get("raw_text"):
                return {
                    "raw_text": nine_res["raw_text"],
                    "plate_type": nine_res.get("plate_type", "one_line"),
                    "engine_used": "9router_vision"
                }

        # TH2: Chế độ HYBRID (hoặc YOLO): Ưu tiên Local AI trước
        local_res = self._recognize_with_yolo(plate_img)
        raw_text = local_res.get("raw_text", "")

        # Nếu Local AI đọc được biển số chuẩn (6 - 10 ký tự): Trả về ngay siêu tốc!
        if len(raw_text) >= 6:
            logger.info(f"Local YOLO OCR nhận diện thành công: {raw_text} ({local_res.get('plate_type')})")
            return {
                "raw_text": raw_text,
                "plate_type": local_res.get("plate_type", "one_line"),
                "engine_used": "local_yolo"
            }

        # Nếu Local AI đọc ra ít hoặc trống, kích hoạt Cứu trợ từ Cloud Vision API (9Router)
        if self.engine_type in ["hybrid", "9router"] and self.ninerouter_client is not None:
            try:
                logger.info(f"Local OCR trả về kết quả yếu ('{raw_text}'). Kích hoạt cứu trợ từ 9Router Vision AI...")
                nine_res = self.ninerouter_client.recognize_plate(plate_img)
                if nine_res.get("raw_text") and len(nine_res["raw_text"]) >= len(raw_text):
                    logger.info(f"9Router Vision cứu trợ thành công: {nine_res['raw_text']}")
                    return {
                        "raw_text": nine_res["raw_text"],
                        "plate_type": nine_res.get("plate_type", local_res.get("plate_type", "one_line")),
                        "engine_used": "9router_vision"
                    }
            except Exception as e:
                logger.warning(f"Lỗi khi gọi 9Router Vision API cứu trợ: {e}")

        # Nếu vẫn còn kết quả Local tốt hơn rỗng, trả về Local
        if raw_text:
            return {
                "raw_text": raw_text,
                "plate_type": local_res.get("plate_type", "one_line"),
                "engine_used": "local_yolo"
            }

        # Bước dự phòng cuối cùng: Nắn nghiêng + PaddleOCR/EasyOCR
        deskewed = PlatePreprocessor.deskew_plate(plate_img)
        enhanced = PlatePreprocessor.enhance_for_ocr(deskewed)

        is_2_line = PlatePreprocessor.is_two_line_plate(plate_img)
        if is_2_line:
            top_img, bottom_img = PlatePreprocessor.split_two_line_plate(enhanced)
            top_text = self.read_text(top_img)
            bottom_text = self.read_text(bottom_img)
            raw_text = f"{top_text}{bottom_text}"
            plate_type = "two_line"
        else:
            raw_text = self.read_text(enhanced)
            plate_type = "one_line"

        return {
            "raw_text": raw_text,
            "plate_type": plate_type,
            "engine_used": "traditional_ocr"
        }
