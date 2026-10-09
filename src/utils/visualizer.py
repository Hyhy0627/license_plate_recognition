import cv2
import numpy as np

def draw_plate_box(
    image: np.ndarray,
    bbox: list,
    plate_text: str,
    confidence: float,
    color: tuple = (0, 255, 0)
) -> np.ndarray:
    """
    Vẽ khung chữ nhật bounding box và nhãn biển số lên ảnh.
    bbox: [x1, y1, x2, y2]
    """
    output = image.copy()
    x1, y1, x2, y2 = map(int, bbox)
    
    # Vẽ bounding box biển số
    cv2.rectangle(output, (x1, y1), (x2, y2), color, 3)
    
    # Chuẩn bị nhãn
    label = f"{plate_text} ({confidence:.2f})"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    thickness = 2
    
    (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)
    
    # Nền cho nhãn
    cv2.rectangle(
        output,
        (x1, max(0, y1 - text_h - 10)),
        (x1 + text_w, y1),
        color,
        -1
    )
    
    # Chữ nhãn
    cv2.putText(
        output,
        label,
        (x1, max(text_h, y1 - 5)),
        font,
        font_scale,
        (0, 0, 0),
        thickness,
        cv2.LINE_AA
    )
    
    return output
