# Trọng số mô hình

Các đường dẫn tính từ thư mục gốc repository. Trọng số được ignore trong Git.

Ảnh — bắt buộc khi backend khởi động:
- models/best.pt: YOLO phát hiện biển số.
- models/LP_ocr.pt: YOLO nhận dạng ký tự.

Hai file trên cần được cung cấp riêng từ bộ model hiện có. Repository chưa có
script tải tự động hoặc pipeline huấn luyện tái lập cho chúng. Không suy ra
nguồn dữ liệu/việc nhóm tự huấn luyện chỉ từ tên file best.pt hoặc LP_ocr.pt.

Video — cần khi phân tích video:
- models/yolov8n.pt: YOLO phát hiện phương tiện.
- models/video/DetectLisence_YOLO11.pt: detector biển của bộ video mặc định.
- models/video/cct_s_v1_vn.onnx: OCR của bộ video mặc định.
- models/video/cct_s_v1_vn_plate_config.yaml: cấu hình khớp OCR.

Cài hai trọng số biển video và cấu hình đi kèm:
    .\venv\Scripts\python.exe scripts/setup_video_models.py
Script kiểm tra SHA256, tải trọng số thiếu/sai checksum và sao chép cấu hình
đã lưu tại src/core/video_ocr.yaml. Script không cài yolov8n.pt; cần cung cấp
riêng file phương tiện đó. Nguồn/các thay đổi tích hợp: docs/video_onnx.md (mục Nguồn mã và model).

EasyOCR dòng dự phòng (tùy chọn):
    .\venv\Scripts\python.exe scripts/setup_ocr.py --download
Model lưu tại models/easyocr/english_g2.pth; script kiểm tra checksum theo
metadata EasyOCR. LocalLineOCR chỉ nạp file đã có, không tải trọng số trong request.
Nhánh OCR truyền thống khác của PlateOCREngine có cơ chế nạp riêng; không khẳng
định mọi engine EasyOCR/PaddleOCR đều đã nạp chỉ vì dependency được cài.

Hướng dẫn tổng thể: README.md.
Engine/mode video và điều kiện remote: docs/video_onnx.md, docs/cloud_ocr.md.

models/checksums.txt ghi SHA256 theo đường dẫn tính từ gốc cho mọi trọng số
đang có lúc dọn repository. best_toy.pt có trong inventory nhưng không được
coi là model runtime mặc định. Thay model cần cập nhật inventory sau kiểm tra.
