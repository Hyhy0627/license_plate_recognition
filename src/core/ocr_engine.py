import os
import cv2
import numpy as np
from typing import Dict, Any, List
from src.core.preprocessor import PlatePreprocessor
from src.core.postprocessor import PlatePostprocessor
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
        from src.core.line_ocr import LocalLineOCR
        self.line_ocr = LocalLineOCR(os.path.join(BASE_DIR, 'models', 'easyocr'))
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

        results = self.yolo_ocr.predict(img, conf=conf, agnostic_nms=True, iou=0.4, verbose=False)
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
        row_slopes = []
        for row in rows:
            sorted_row = sorted(row, key=lambda c: c[0][0])
            text_parts.append("".join(c[1] for c in sorted_row))
            # Use character centres on the same row, not every nonblack pixel
            # in the crop (which measures the image rectangle, not plate tilt).
            centres = [((c[0][0] + c[0][2]) / 2, (c[0][1] + c[0][3]) / 2) for c in sorted_row]
            for i, (x, y) in enumerate(centres):
                for xx, yy in centres[i + 1:]:
                    if xx - x > max(heights) and abs((yy - y) / (xx - x)) < 0.5:
                        row_slopes.append((yy - y) / (xx - x))

        raw_text = "".join(text_parts)
        plate_type = "two_line" if len(rows) > 1 else "one_line"

        return {
            "raw_text": raw_text,
            "text_lines": text_parts,
            "plate_type": plate_type,
            "chars_count": len(raw_text),
            "avg_conf": avg_conf,
            "skew_angle": float(np.degrees(np.arctan(np.median(row_slopes)))) if row_slopes else 0.0,
        }

    def _recognize_with_yolo(self, plate_img: np.ndarray) -> Dict[str, Any]:
        """
        Nhận diện ký tự bằng Local YOLO OCR với cơ chế Auto-Invert màu thông minh:
        - Tự động nhận diện biển xanh/biển tối và đảo màu để đọc 100% chính xác.
        - Tự động so sánh giữa ảnh gốc và ảnh đảo màu để chọn phương án tối ưu nhất.
        """
        if self.yolo_ocr is None or plate_img is None or plate_img.size == 0:
            return {"raw_text": "", "plate_type": "unknown", "engine_used": "local_yolo"}

        # Phóng to crop nhỏ trước OCR để giữ nét ký tự khi biển chiếm ít pixel.
        height, width = plate_img.shape[:2]
        upscale = max(1, min(3, int(160 / max(1, height))))
        ocr_img = plate_img
        if upscale > 1:
            ocr_img = cv2.resize(
                plate_img, (width * upscale, height * upscale),
                interpolation=cv2.INTER_CUBIC,
            )

        is_dark = PlatePreprocessor.is_dark_or_blue_plate(ocr_img)

        def best_result(*results):
            return max(results, key=self._result_quality)

        if is_dark:
            inverted_img = PlatePreprocessor.invert_plate(ocr_img)
            result = best_result(
                self._predict_yolo_boxes(inverted_img, conf=0.20),
                self._predict_yolo_boxes(ocr_img, conf=0.20),
            )
        else:
            inverted_img = PlatePreprocessor.invert_plate(ocr_img)
            result = best_result(
                self._predict_yolo_boxes(ocr_img, conf=0.20),
                self._predict_yolo_boxes(inverted_img, conf=0.20),
            )

        # Lần đọc bổ sung ở ngưỡng thấp giữ các ký tự mờ hoặc nhỏ.
        if not self._result_quality(result)[0] or result.get("avg_conf", 0.0) < 0.65:
            retry_img = inverted_img if is_dark else ocr_img
            retry = self._predict_yolo_boxes(retry_img, conf=0.12)
            result = best_result(result, retry)

        # Worn paint can retain contrast in the original pixels but disappear
        # after cubic upscaling. Only try thresholding for an unreadable crop;
        # it is another OCR observation, never a reconstruction of missing text.
        if not self._result_quality(result)[0]:
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY) if plate_img.ndim == 3 else plate_img
            binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            threshold_result = self._predict_yolo_boxes(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR), conf=0.20)
            result = best_result(result, threshold_result)

        angle = result.get("skew_angle", 0.0)
        if 2.5 <= abs(angle) <= 25 and 6 <= result.get("chars_count", 0) <= 10:
            h, w = ocr_img.shape[:2]
            matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
            aligned = cv2.warpAffine(ocr_img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            corrected = self._predict_yolo_boxes(aligned, conf=0.20)
            # A higher mean confidence after dropping a glyph is not an
            # improvement over a structurally complete observed reading.
            if not self._result_quality(result)[0] or corrected.get("chars_count", 0) >= result.get("chars_count", 0):
                result = best_result(result, corrected)

        result["engine_used"] = "local_yolo"
        return result

    @staticmethod
    def _result_quality(result):
        formatted = PlatePostprocessor.format_vietnamese_plate(
            result.get("raw_text", ""), result.get("plate_type"), result.get("text_lines"))
        return (PlatePostprocessor.validate_plate(formatted), result.get("avg_conf", 0.0),
                -abs(result.get("chars_count", 0) - 8))

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
