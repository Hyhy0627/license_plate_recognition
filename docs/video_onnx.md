# Nhận diện video bằng YOLO11n và CCT-VN ONNX

Nguồn model: https://github.com/ddkhoa2605/LicensePlateDetection

Phiên bản đã kiểm tra: `f1c732e2270becc44df1de6529372f63ef251076`.
Repo được clone tại `external/LicensePlateDetection`; giữ nguyên mã và tài liệu
upstream ở đó. Dự án chính dùng adapter `src/core/video_models.py` để nạp model,
không chạy giao diện Streamlit của upstream. Repo upstream chưa có tệp LICENSE
riêng tại phiên bản này; cần làm rõ quyền sử dụng trước khi phân phối lại model.

## Cài đặt

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe tool/setup_video_models.py
```

Script cài đặt kiểm tra SHA256 của hai trọng số và cấu hình OCR rồi sao chép:

- `models/video/DetectLisence_YOLO11.pt`: phát hiện biển số.
- `models/video/cct_s_v1_vn.onnx`: đọc ký tự.
- `models/video/cct_s_v1_vn_plate_config.yaml`: cấu hình khớp với model OCR.

Các thư mục `external/` và `models/video/` không được đưa vào Git của dự án chính.
Clone dự án trên máy khác cần chạy lại script cài model. Script không ghi đè lên
phiên bản upstream khác hoặc chấp nhận trọng số sai checksum.

## Luồng xử lý

Trang `/video` gửi `mode=fast`, cũng là mặc định của API. Hệ thống theo vết xe bằng
YOLOv8n và ByteTrack, phát hiện biển bằng YOLO11n, đọc crop bằng CCT-VN ONNX,
chuẩn hóa biển Việt Nam và bỏ phiếu qua các khung hình. Model video được cache
trong mỗi tiến trình backend. Theo vết lấy mẫu 5 khung hình/giây ở kích thước suy
luận 640 để giữ khả năng bắt xe máy trong video có camera di chuyển.

Chế độ nhanh xử lý một lượt, không chạy lượt bổ sung `detailed` và không gọi
9Router. Các ID đọc cùng biển được gộp trong danh sách kết quả. Giao diện hiển
thị thời gian xử lý, các kết quả cần đối chiếu và các lượt đọc khác nhau.

API vẫn hỗ trợ `mode=combined` và `mode=detailed` với bộ model cũ. Hai chế độ này
có thể gọi OCR từ xa theo cấu hình cũ. Luồng nhận diện ảnh giữ bộ model hiện tại.

Cấu hình tùy chọn trong `.env`, khởi động lại backend sau khi đổi:

```dotenv
VIDEO_ENGINE=onnx
VIDEO_PLATE_MODEL_PATH=models/video/DetectLisence_YOLO11.pt
VIDEO_OCR_MODEL_PATH=models/video/cct_s_v1_vn.onnx
VIDEO_OCR_CONFIG_PATH=models/video/cct_s_v1_vn_plate_config.yaml
VIDEO_OCR_MIN_CONFIDENCE=0.7
```

`VIDEO_ENGINE=legacy` dùng detector/OCR cũ cho chế độ nhanh. Chế độ nhanh vẫn
không gọi OCR từ xa. Không tự động đổi sang bộ cũ khi thiếu model ONNX; lỗi job
sẽ chỉ rõ cách cài model để tránh chạy nhầm bộ model.

## Benchmark

```powershell
.\venv\Scripts\python.exe tool/benchmark_video.py "duong-dan-video.mp4" --output data/benchmarks/onnx.json
.\venv\Scripts\python.exe tool/benchmark_video.py "duong-dan-video.mp4" --engine legacy --mode combined --output data/benchmarks/legacy.json
```

Cả hai lệnh đều tắt OCR từ xa. JSON lưu thời gian nạp model, thời gian phân tích,
tổng thời gian, track, timestamp và biển số để kiểm tra kết quả. Thời gian tính
trong API bao gồm nạp model lần đầu, không bao gồm upload hoặc thời gian xếp hàng.

### Kết quả kiểm tra ngày 19/11/2026

Video trong dự án: 353 khung hình, 30 FPS, 1080×1920, dài 11,77 giây. Chạy CPU,
PyTorch không có CUDA, cấu hình 2 luồng suy luận. Đây là một video mẫu, chưa phải
bộ đánh giá độ chính xác.

| Luồng | Thời gian |
|---|---:|
| Cũ: YOLO OCR, `combined`, không OCR từ xa | 76,811 giây |
| Mới: ONNX, `fast`, 5 FPS, chạy CLI | 11,212 giây gồm nạp model |
| Mới: gọi qua API, xử lý và nạp model video | 13,398 giây |

Lần gọi API nhanh hơn khoảng 5,7 lần so với phép đo luồng cũ. Kết quả sau gộp
ID có hai chuỗi biển khác nhau; cần đối chiếu nhãn thật để tính độ chính xác.
Các tệp bằng chứng cục bộ, không đưa vào Git:

- `data/benchmarks/video_legacy_combined.json`
- `data/benchmarks/video_onnx_fast_5fps.json`
- `data/benchmarks/video_api_smoke.json`

Đã kiểm tra upload → tạo job → hoàn tất với model thật → đọc video bằng HTTP
Range; 20 bài kiểm thử video/model/API/khởi động đều đạt. TypeScript và ESLint
của trang video đạt. Sau khi cập nhật trên máy đang chạy, khởi động lại backend
và tải lại trang `/video` để dùng luồng mới.

Độ chính xác cần được đo riêng với nhãn thật; số chuỗi đọc được không phải số biển
đọc đúng. Kết quả lặp lại vẫn có thể sai. Biển nhỏ, mờ, bị che hoặc góc nghiêng lớn
cần đối chiếu hình ảnh. Mức lấy mẫu thấp hơn có thể nhanh hơn nhưng bỏ lỡ xe máy
và làm track đứt đoạn trong video có camera di chuyển.
