# THƯ MỤC LƯU TRỮ MODEL WEIGHTS

Vui lòng đặt các file trọng số mô hình đã huấn luyện vào đây:

1. `best.pt`: Trọng số mô hình YOLO phát hiện biển số xe (được huấn luyện bởi Người 2).
   - Tải về từ quá trình train YOLO (ví dụ: runs/detect/train/weights/best.pt).
   - Đặt trực tiếp tại: `models/best.pt` hoặc `models/plate_detection/best.pt`.

2. Thư mục con `ocr/`: Chứa các trọng số fine-tune OCR (nếu Người 3 có tùy biến mô hình OCR).
