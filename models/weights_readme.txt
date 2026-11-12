# THƯ MỤC LƯU TRỮ MODEL WEIGHTS

Vui lòng đặt các file trọng số mô hình đã huấn luyện vào đây:

1. `best.pt`: Trọng số mô hình YOLO phát hiện biển số xe (được huấn luyện bởi Người 2).
   - Tải về từ quá trình train YOLO (ví dụ: runs/detect/train/weights/best.pt).
   - Đặt trực tiếp tại: `models/best.pt` hoặc `models/plate_detection/best.pt`.

2. Thư mục con `ocr/`: Chứa các trọng số fine-tune OCR (nếu Người 3 có tùy biến mô hình OCR).

3. `easyocr/english_g2.pth`: OCR dòng dự phòng local cho vùng biển YOLO chưa đọc được.
   - Cài rõ ràng bằng: `venv\Scripts\python.exe tool/setup_ocr.py --download`
   - Nguồn: https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip
   - Thư viện EasyOCR đã có trong requirements.txt; script kiểm tra checksum theo metadata của thư viện.
   - Backend chỉ nạp file có sẵn, không tự tải model trong request. Thiếu file thì bỏ qua bước dự phòng này.
