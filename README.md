# Nhận diện biển số xe Việt Nam

Ứng dụng web nhận diện biển số từ ảnh và video tải lên, theo vết phương tiện và lưu lịch sử nhận diện ảnh theo tài khoản. Phạm vi triển khai hiện tại là một backend FastAPI và một frontend Next.js trên một máy chủ.

## Cài đặt

Mọi lệnh dưới đây chạy từ thư mục gốc repository bằng PowerShell. Môi trường đã kiểm tra dùng Python 3.13; Dockerfile backend dùng Python 3.11. Next.js yêu cầu Node.js từ 20.9.

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix frontend ci
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Để xử lý ảnh cục bộ, đặt `OCR_ENGINE=yolo` trong `.env`. Default trong code là `hybrid`, còn `.env.example` hiện chọn `9router`; giá trị trong môi trường/`.env` quyết định chế độ khi chạy. Xem [cách hoạt động của OCR từ xa](docs/cloud_ocr.md) trước khi chọn chế độ có NineRouter.

Chuẩn bị `models/best.pt`, `models/LP_ocr.pt` và `yolov8n.pt` theo [hướng dẫn trọng số](models/weights_readme.txt). Hai model ảnh là bắt buộc khi backend khởi động; model phương tiện ở thư mục gốc được dùng khi xử lý video. Trọng số không được đưa lên Git.

Cài bộ model bổ trợ cho video mặc định:

```powershell
.\venv\Scripts\python.exe scripts/setup_video_models.py
```

EasyOCR dòng dự phòng là tùy chọn: `.\venv\Scripts\python.exe scripts/setup_ocr.py --download`.

## Khởi động

Mở hai terminal tại thư mục gốc:

```powershell
# Terminal 1: backend
.\venv\Scripts\python.exe main.py
```

```powershell
# Terminal 2: frontend
npm --prefix frontend run dev
```

Mở [giao diện web](http://localhost:3000) và đăng ký tại `/register`. Database được khởi tạo khi backend chạy; code không seed tài khoản mặc định. Các tài khoản có sẵn trên máy phát triển không đi kèm bản clone.

| Trang | Chức năng |
|---|---|
| `/` | Tải ảnh, nhận diện và xem ảnh đánh dấu |
| `/video` | Tải video, xem tiến trình và kết quả theo vết |
| `/history` | Tìm kiếm, phân trang lịch sử nhận diện ảnh của tài khoản |
| `/login`, `/register` | Đăng nhập, đăng ký |

Backend có [Swagger](http://localhost:8000/docs) và [ReDoc](http://localhost:8000/redoc). Danh sách endpoint và cơ chế xác thực được mô tả tại [kiến trúc dự án](PROJECT_STRUCTURE.md). Khi đổi địa chỉ API, xem [cấu hình frontend](frontend/README.md).

## Tài liệu theo công việc

| Cần làm | Tài liệu |
|---|---|
| Hiểu module, luồng xử lý, API và database | [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) |
| Cài model | [models/weights_readme.txt](models/weights_readme.txt) |
| Hiểu dữ liệu gửi qua NineRouter | [docs/cloud_ocr.md](docs/cloud_ocr.md) |
| Cấu hình và đánh giá video | [docs/video_onnx.md](docs/video_onnx.md) |
| Chạy test và kiểm tra frontend | [tests/TESTING.md](tests/TESTING.md) |
| Đo thao tác ứng dụng hoặc độ chính xác ảnh | [benchmark/README.md](benchmark/README.md), [benchmark/ACCURACY.md](benchmark/ACCURACY.md) |
| Phân tích bằng notebook | [notebooks/README.md](notebooks/README.md) |
| Phân biệt fixture và dữ liệu runtime | [data/README.md](data/README.md) |
| Tra nguồn mã/model và trạng thái báo cáo | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [docs/README.md](docs/README.md) |

Tốc độ và độ chính xác AI hiện tại **chưa đo trong đợt đồng bộ tài liệu**. Bộ ảnh kèm repository là ảnh tổng hợp; số test phần mềm đạt không thể thay cho đánh giá trên giao thông thực tế. Xem [kết quả kiểm tra giai đoạn 1](docs/results/documentation_sync.md) để biết phạm vi đã kiểm chứng.
