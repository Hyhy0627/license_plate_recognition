# Nguồn mã và model bên ngoài

## Lõi đọc biển số

- Tác giả/repository: [ddkhoa2605/LicensePlateDetection](https://github.com/ddkhoa2605/LicensePlateDetection).
- Phiên bản: `f1c732e2270becc44df1de6529372f63ef251076`.
- File gốc: `appStreamlit.py`, lớp `SimplePlateDetector`.
- File tích hợp: `src/core/plate_reader.py`, lớp `PlateReader`.
- Các thuật toán kế thừa: tiền xử lý crop, crop có padding, bỏ phiếu ký tự theo confidence, quản lý vòng đời track và xử lý frame.
- Điều chỉnh của đồ án: bỏ phụ thuộc Streamlit; nạp model tùy chọn; cập nhật API Fast Plate OCR 1.1; chuyển BGR sang RGB; loại padding trước khi tính confidence; cho phép tắt tiền xử lý trong adapter video để giữ luồng đang chạy.
- Backend dùng OCR từ lớp này qua `VideoPlateOCR`; theo vết phương tiện và schema trả về cho web vẫn nằm trong `src/core/video_tracker.py`.

Thông tin nguồn được giữ để phân biệt phần kế thừa với phần nhóm tự triển khai. Repository gốc không có file LICENSE riêng tại phiên bản được tích hợp; tài liệu này không cấp thêm quyền sử dụng.

## Trọng số và cấu hình OCR

`DetectLisence_YOLO11.pt`, `cct_s_v1_vn.onnx` và cấu hình `cct_s_v1_vn_plate_config.yaml` lấy từ cùng phiên bản trên. Cấu hình được lưu tại `src/core/video_ocr.yaml`; trọng số được cài riêng bằng `scripts/setup_video_models.py` với SHA256 cố định. Không coi các trọng số này là model do nhóm tự huấn luyện.

Ultralytics, Fast Plate OCR và ONNX Runtime vẫn là các thư viện cài qua `requirements.txt`, không phải mã do nhóm tự phát triển.
