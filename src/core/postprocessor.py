import re
from typing import Optional

class PlatePostprocessor:
    """
    Module chuẩn hóa và sửa lỗi quang học cho biển số xe Việt Nam.
    Phụ trách bởi: Người 3 (AI OCR).
    """

    # Bảng ánh xạ khi ký tự bắt buộc phải là số
    CHAR_TO_DIGIT = {
        'O': '0', 'D': '0', 'Q': '0',
        'I': '1', 'L': '1',
        'Z': '2',
        'E': '3',
        'A': '4',
        'S': '5',
        'G': '6',
        'B': '8',
    }

    # Bảng ánh xạ khi ký tự bắt buộc phải là chữ
    DIGIT_TO_CHAR = {
        '0': 'D', # Hoặc O tuỳ vị trí seri
        '1': 'I',
        '2': 'Z',
        '4': 'A',
        '5': 'S',
        '8': 'B',
    }

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """
        Loại bỏ các ký tự đặc biệt, dấu chấm, gạch ngang, khoảng trắng, chuyển về chữ in hoa.
        """
        if not raw_text:
            return ""
        # Chỉ giữ lại A-Z và 0-9
        cleaned = re.sub(r'[^A-Za-z0-9]', '', raw_text).upper()
        return cleaned

    @classmethod
    def format_vietnamese_plate(cls, cleaned_text: str) -> str:
        """
        Sửa lỗi dựa trên cấu trúc vị trí biển số xe Việt Nam:
        - 2 ký tự đầu: Mã tỉnh (luôn là 2 chữ số, VD: 29, 30, 59, 90,...)
        - Ký tự thứ 3 (hoặc 3-4): Seri chữ (VD: A, B, K1, A1, LD,...)
        - Các ký tự còn lại: Số thứ tự (4 hoặc 5 chữ số)
        """
        text = list(cleaned_text)
        length = len(text)

        if length < 7 or length > 10:
            return cleaned_text

        # 1. Hai ký tự đầu bắt buộc phải là số (Mã tỉnh)
        for i in [0, 1]:
            if text[i] in cls.CHAR_TO_DIGIT:
                text[i] = cls.CHAR_TO_DIGIT[text[i]]

        # 2. Các ký tự cuối bắt buộc phải là số (thường là 4 hoặc 5 số cuối)
        # Nếu tổng chuỗi 8 ký tự: 2 số + 1 chữ + 5 số -> 5 số cuối
        # Nếu tổng chuỗi 9 ký tự: 2 số + 2 chữ/số + 5 số -> 5 số cuối
        tail_start = max(3, length - 5)
        for i in range(tail_start, length):
            if text[i] in cls.CHAR_TO_DIGIT:
                text[i] = cls.CHAR_TO_DIGIT[text[i]]

        # 3. Ký tự thứ 3 thường là chữ cái seri
        if length >= 3 and text[2] in cls.DIGIT_TO_CHAR:
            text[2] = cls.DIGIT_TO_CHAR[text[2]]

        return "".join(text)

    @classmethod
    def validate_plate(cls, plate_number: str) -> bool:
        """
        Kiểm tra tính hợp lệ bằng Regex chuẩn biển số Việt Nam:
        Ví dụ: 29A12345, 59K12345, 30H12345, 80B1234
        """
        pattern = r"^[0-9]{2}[A-Z]{1}[0-9A-Z]{0,2}[0-9]{4,5}$"
        return bool(re.match(pattern, plate_number))
