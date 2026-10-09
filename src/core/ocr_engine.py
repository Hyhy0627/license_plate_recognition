import numpy as np
from typing import Dict, Any, List
from src.core.preprocessor import PlatePreprocessor

class PlateOCREngine:
    """
    Module OCR nhận dạng chuỗi ký tự trên ảnh biển số xe.
    Hỗ trợ cả PaddleOCR và EasyOCR.
    Phụ trách bởi: Người 3 (AI OCR).
    """
    def __init__(self, engine_type: str = "paddleocr"):
        self.engine_type = engine_type.lower()
        self.ocr = None
        self._init_ocr()

    def _init_ocr(self):
        try:
            if self.engine_type == "paddleocr":
                from paddleocr import PaddleOCR
                # Sử dụng mode tiếng Anh/số để tăng tốc và giảm ký tự nhiễu
                self.ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            elif self.engine_type == "easyocr":
                import easyocr
                self.ocr = easyocr.Reader(["en"], gpu=False)
        except Exception:
            self.ocr = None

    def read_text(self, plate_img: np.ndarray) -> str:
        """
        Nhận diện ký tự từ ảnh 1 dòng đơn.
        """
        if self.ocr is None or plate_img is None or plate_img.size == 0:
            return ""

        text_result = ""
        try:
            if self.engine_type == "paddleocr":
                result = self.ocr.ocr(plate_img, cls=True)
                if result and result[0]:
                    lines = [line[1][0] for line in result[0] if line and len(line) > 1]
                    text_result = "".join(lines)
            elif self.engine_type == "easyocr":
                results = self.ocr.readtext(plate_img)
                lines = [res[1] for res in results]
                text_result = "".join(lines)
        except Exception:
            text_result = ""

        return text_result

    def recognize_plate(self, plate_img: np.ndarray) -> Dict[str, Any]:
        """
        Nhận diện toàn bộ biển số, tự động xử lý biển 1 dòng hoặc 2 dòng.
        """
        if plate_img is None or plate_img.size == 0:
            return {"raw_text": "", "plate_type": "unknown"}

        # Tiền xử lý nắn thẳng & tăng tương phản
        deskewed = PlatePreprocessor.deskew_plate(plate_img)
        enhanced = PlatePreprocessor.enhance_for_ocr(deskewed)

        # Kiểm tra loại biển
        is_2_line = PlatePreprocessor.is_two_line_plate(plate_img)

        if is_2_line:
            # Tách 2 nửa
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
            "plate_type": plate_type
        }
