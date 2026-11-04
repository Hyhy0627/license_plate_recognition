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
    def format_vietnamese_plate(cls, cleaned_text: str, plate_type: Optional[str] = None) -> str:
        """
        Sửa lỗi dựa trên cấu trúc vị trí biển số xe Việt Nam và thêm định dạng dấu gạch/chấm chuẩn:
        - 2 ký tự đầu: Mã tỉnh (luôn là 2 chữ số, VD: 29, 30, 59, 88, 90,...)
        - Ký tự thứ 3 (hoặc 3-4): Seri chữ (VD: A, B, G1, A1, LD,...)
        - Các ký tự còn lại: Số thứ tự (4 hoặc 5 chữ số)

        Định dạng chuẩn theo quy định biển số xe Việt Nam:
        - Biển xe máy (2 dòng): 88-G1 333.43 (Dòng 1: '88-G1', Dòng 2: '333.43')
        - Biển ô tô (1 dòng):   30A-123.45 hoặc 51F-866.88
        - Biển ô tô vuông:      30A 123.45
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
        tail_start = max(3, length - 5)
        for i in range(tail_start, length):
            if text[i] in cls.CHAR_TO_DIGIT:
                text[i] = cls.CHAR_TO_DIGIT[text[i]]

        # 3. Ký tự thứ 3 thường là chữ cái seri
        if length >= 3 and text[2] in cls.DIGIT_TO_CHAR:
            text[2] = cls.DIGIT_TO_CHAR[text[2]]

        raw = "".join(text)

        # Nhận diện nếu là biển xe máy hoặc biển 2 dòng:
        # Đặc điểm xe máy VN: 9 ký tự, ký tự thứ 3 là chữ + ký tự thứ 4 là SỐ (VD: 88G1..., 29X1...)
        # Phân biệt: nếu text[3] cũng là chữ (VD: 29LD...) thì đó là biển cơ quan/liên doanh, KHÔNG phải xe máy
        is_motorcycle_pattern = (
            length == 9 and text[2].isalpha() and text[3].isdigit()
        )
        is_two_line = (plate_type == "two_line") or is_motorcycle_pattern

        if is_two_line:
            # Biển 2 dòng / Biển xe máy:
            # Dòng 1: Mã tỉnh - Seri (VD: 88-G1, 29-X1)
            # Dòng 2: Dãy số thứ tự (VD: 333.43)
            # Giữa 2 dòng phân cách bằng dấu cách
            if length == 9:
                return f"{raw[:2]}-{raw[2:4]} {raw[4:7]}.{raw[7:]}"
            elif length == 8:
                if text[2].isalpha() and text[3].isalpha():
                    # Biển xe máy seri 2 chữ cái: VD: 29-LD 1234
                    return f"{raw[:2]}-{raw[2:4]} {raw[4:]}"
                else:
                    # Biển ô tô vuông (2 dòng): VD: 80A 005.38
                    return f"{raw[:3]} {raw[3:6]}.{raw[6:]}"
            elif length == 7:
                return f"{raw[:3]} {raw[3:]}"

        # Biển 1 dòng (Ô tô hình chữ nhật dài)
        if length == 8:  # VD: 30A12345 -> 30A-123.45
            return f"{raw[:3]}-{raw[3:6]}.{raw[6:]}"
        elif length == 9:
            if text[2].isalpha() and text[3].isalpha():
                # Xe liên doanh / cơ quan: VD: 29LD12345 -> 29LD-123.45
                return f"{raw[:4]}-{raw[4:7]}.{raw[7:]}"
            else:
                # Fallback định dạng xe máy
                return f"{raw[:2]}-{raw[2:4]} {raw[4:7]}.{raw[7:]}"
        elif length == 7:  # VD: 51F9999 -> 51F-9999
            return f"{raw[:3]}-{raw[3:]}"

        return raw

    @classmethod
    def validate_plate(cls, plate_number: str) -> bool:
        """
        Kiểm tra tính hợp lệ bằng Regex chuẩn biển số Việt Nam (hỗ trợ cả có dấu và không dấu):
        Ví dụ: 29A12345, 59G2-777.77, 30A-123.45, 51F-9999
        """
        if not plate_number:
            return False
        clean = re.sub(r'[^A-Za-z0-9]', '', plate_number).upper()
        pattern = r"^[0-9]{2}[A-Z]{1}[0-9A-Z]{0,2}[0-9]{4,5}$"
        return bool(re.match(pattern, clean))
