import cv2
import numpy as np
from typing import Tuple, List, Optional
import random


class PlatePreprocessor:
    """
    Module tiền xử lý ảnh biển số xe trước khi đưa vào OCR và Tăng cường dữ liệu (Data Augmentation).
    Phụ trách bởi: Người 1 (Kỳ Duyên - Dataset & Preprocessing) & Người 3 (Quang Huy).
    """

    @staticmethod
    def is_two_line_plate(plate_img: np.ndarray, threshold_ratio: float = 1.8) -> bool:
        """
        Xác định biển số là 1 dòng (dài) hay 2 dòng (vuông).
        - Biển dài (1 dòng): width / height > 2.0 (thường ~ 2.5 - 4.0)
        - Biển vuông (2 dòng): width / height < 1.8 (thường ~ 1.2 - 1.5)
        """
        if plate_img is None or plate_img.size == 0:
            return False
        h, w = plate_img.shape[:2]
        if h == 0:
            return False
        aspect_ratio = w / float(h)
        return aspect_ratio < threshold_ratio

    @staticmethod
    def sharpen_image(img: np.ndarray, strength: float = 1.4) -> np.ndarray:
        """
        Tăng cường độ sắc nét (Unsharp Masking) giúp làm nổi bật đường nét ký tự.
        """
        if img is None or img.size == 0:
            return img
        gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
        unsharp = cv2.addWeighted(img, strength, gaussian, -(strength - 1.0), 0)
        return unsharp

    @staticmethod
    def enhance_for_ocr(plate_img: np.ndarray) -> np.ndarray:
        """
        Chuỗi kỹ thuật tiền xử lý tối ưu cho OCR:
        1. Chuyển ảnh sang Grayscale
        2. Cân bằng tương phản thích ứng cục bộ (CLAHE)
        3. Lọc song phương (Bilateral Filter) khử nhiễu bề mặt giữ nét cạnh chữ
        """
        if plate_img is None or plate_img.size == 0:
            return plate_img

        if len(plate_img.shape) == 3:
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_img.copy()

        # Tăng độ tương phản bằng CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast_enhanced = clahe.apply(gray)

        # Khử nhiễu Bilateral Filter bảo toàn cạnh chữ
        denoised = cv2.bilateralFilter(contrast_enhanced, 9, 75, 75)

        return denoised

    @staticmethod
    def split_two_line_plate(plate_img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Cắt đôi biển số 2 dòng thành 2 vùng ảnh độc lập:
        - top_part: Dòng trên (Mã tỉnh + Seri chữ, VD: 59-A1)
        - bottom_part: Dòng dưới (Dãy số thứ tự, VD: 123.45)
        """
        if plate_img is None or plate_img.size == 0:
            return plate_img, plate_img
        h, w = plate_img.shape[:2]
        mid_h = int(h * 0.48)  # Tỷ lệ chia xấp xỉ dòng trên và dòng dưới
        
        top_part = plate_img[0:mid_h, :]
        bottom_part = plate_img[mid_h:h, :]
        
        return top_part, bottom_part

    @staticmethod
    def deskew_plate(plate_img: np.ndarray) -> np.ndarray:
        """
        Nắn thẳng góc nghiêng của biển số xe bằng minAreaRect và Affine Transform.
        """
        if plate_img is None or plate_img.size == 0:
            return plate_img

        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY) if len(plate_img.shape) == 3 else plate_img
        coords = np.column_stack(np.where(gray > 0))
        if len(coords) == 0:
            return plate_img

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        # Nếu độ nghiêng nằm trong khoảng cho phép, tiến hành xoay
        if abs(angle) > 1.0 and abs(angle) < 45.0:
            h, w = plate_img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                plate_img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
            )
            return rotated

        return plate_img

    @staticmethod
    def is_dark_or_blue_plate(plate_img: np.ndarray) -> bool:
        """
        Kiểm tra xem biển số có nền tối / nền xanh (biển xanh công vụ, biển đỏ quân đội) hay không:
        - Biển xanh: Tỷ lệ pixel xanh dương trong HSV > 18%
        - Biển nền tối: Độ sáng trung bình vùng viền < 115
        """
        if plate_img is None or plate_img.size == 0:
            return False

        hsv = cv2.cvtColor(plate_img, cv2.COLOR_BGR2HSV)
        blue_mask = cv2.inRange(hsv, np.array([90, 50, 40]), np.array([135, 255, 255]))
        blue_ratio = np.sum(blue_mask > 0) / float(plate_img.shape[0] * plate_img.shape[1])
        if blue_ratio > 0.18:
            return True

        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY) if len(plate_img.shape) == 3 else plate_img
        border = np.concatenate([gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]])
        if np.mean(border) < 115:
            return True

        return False

    @staticmethod
    def invert_plate(plate_img: np.ndarray) -> np.ndarray:
        """
        Đảo ngược độ sáng ảnh (chuyển chữ trắng nền tối thành chữ đen nền sáng)
        giúp mô hình OCR nhận dạng chính xác như biển trắng thông thường.
        """
        if plate_img is None or plate_img.size == 0:
            return plate_img
        if len(plate_img.shape) == 3:
            return cv2.bitwise_not(plate_img)
        return 255 - plate_img

    @staticmethod
    def augment_plate(
        image: np.ndarray,
        max_angle: float = 10.0,
        brightness_range: float = 0.20,
        add_noise: bool = True
    ) -> np.ndarray:
        """
        Kỹ thuật tăng cường dữ liệu (Data Augmentation) áp dụng cho khâu chuẩn bị dataset:
        1. Xoay ngẫu nhiên (+- 10 độ)
        2. Biến đổi độ sáng & tương phản (+- 20%)
        3. Tạo nhiễu hạt Gaussian nhẹ
        """
        if image is None or image.size == 0:
            return image

        augmented = image.copy()
        h, w = augmented.shape[:2]

        # 1. Xoay góc ngẫu nhiên [-max_angle, max_angle]
        angle = random.uniform(-max_angle, max_angle)
        if abs(angle) > 0.5:
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            augmented = cv2.warpAffine(augmented, M, (w, h), borderMode=cv2.BORDER_REPLICATE)

        # 2. Thay đổi độ sáng và tương phản [-20%, +20%]
        alpha = 1.0 + random.uniform(-brightness_range, brightness_range)  # Tương phản
        beta = random.uniform(-25, 25)                                     # Độ sáng
        augmented = cv2.convertScaleAbs(augmented, alpha=alpha, beta=beta)

        # 3. Tạo nhiễu hạt Gaussian nhẹ
        if add_noise and random.random() > 0.5:
            noise = np.random.normal(0, 8, augmented.shape).astype(np.float32)
            noisy_img = np.clip(augmented.astype(np.float32) + noise, 0, 255).astype(np.uint8)
            augmented = noisy_img

        return augmented
