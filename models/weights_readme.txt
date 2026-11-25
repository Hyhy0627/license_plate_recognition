# Bộ trọng số baseline-v1

Registry trong src/core/models/registry.py ánh xạ ID theo chức năng sang đường
dẫn và nguồn cài. models/checksums.txt cố định phiên bản của từng tệp bằng
SHA‑256. Git lưu registry, checksum và cấu hình OCR gốc.

Ảnh mặc định
- image-detector → models/best.pt
- image-ocr → models/LP_ocr.pt

Video mặc định
- vehicle-detector → models/yolov8n.pt
- video-detector → models/video/DetectLisence_YOLO11.pt
- sequence-ocr → models/video/cct_s_v1_vn.onnx
- sequence-config → models/video/cct_s_v1_vn_plate_config.yaml

Chạy từ thư mục gốc bằng PowerShell.

    .\venv\Scripts\python.exe scripts/download_models.py
    .\venv\Scripts\python.exe scripts/download_models.py --check

Các trọng số video có nguồn mặc định và cấu hình OCR được sao chép từ
src/core/video/video_ocr.yaml. Hai trọng số ảnh cần có sẵn với checksum khớp
hoặc được nhóm cung cấp qua nguồn riêng. Đặt đúng tên tệp trong cùng thư mục
Release hoặc cùng prefix S3, rồi chạy một trong hai lệnh sau.

    .\venv\Scripts\python.exe scripts/download_models.py --group image --source-base s3://your-model-bucket/baseline-v1
    .\venv\Scripts\python.exe scripts/download_models.py --group image --source-base https://github.com/OWNER/REPO/releases/download/baseline-v1

S3 dùng chuỗi xác thực mặc định của AWS SDK. Nếu dùng ALPR_MODEL_SOURCE thay cho
--source-base, đặt biến này trong môi trường shell. Nguồn chỉ định được dùng cho
mọi trọng số trong nhóm đã chọn. --artifact cho phép chọn từng ID có trong registry.

--check chỉ đọc tệp cục bộ. Chế độ cài bỏ qua tệp khớp checksum và chỉ thay tệp
đích sau khi bản tải về hoặc cấu hình đi kèm đã qua xác minh. Đường dẫn runtime
có thể cấu hình trong .env, chẳng hạn YOLO_MODEL_PATH, OCR_MODEL_PATH và các biến
VIDEO_*_PATH. Trình cài kiểm tra đường dẫn của bộ baseline-v1 trong registry.
Khi phát hành bộ trọng số mới, cập nhật phiên bản bộ, nguồn cố định và checksum
tương ứng. Dùng đường dẫn riêng nếu triển khai trọng số tùy chỉnh song song.

EasyOCR dòng dự phòng là tùy chọn. Cài bằng scripts/setup_ocr.py --download.
best_toy.pt là mục inventory, ngoài bộ mặc định.
Nguồn mô hình và phần tích hợp video được ghi trong docs/video_onnx.md.
