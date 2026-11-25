# Script kỹ thuật

Chạy từ thư mục gốc repository bằng Python trong `venv`. Các script chỉ chạy khi được gọi trực tiếp; việc import package không tải model hoặc chạy benchmark.

| Script | Mục đích | Hướng dẫn |
|---|---|---|
| `download_models.py` | Tải và xác minh SHA‑256 theo registry hoặc kiểm tra bản đã cài | [Model](../models/weights_readme.txt) |
| `setup_video_models.py` | Lệnh cũ để cài nhóm detector biển và OCR video | [Model](../models/weights_readme.txt) |
| `seed_user.py` | Tạo một tài khoản khi được gọi chủ động, đọc biến môi trường và giữ nguyên tài khoản đã có | [Tài khoản/secret](../docs/security.md) |
| `setup_ocr.py` | Cài EasyOCR dòng tùy chọn | [Model](../models/weights_readme.txt) |
| `benchmark.py` | Đánh giá ảnh có nhãn hoặc so sánh throughput HTTP với `--api-throughput` | [Độ chính xác](../benchmark/ACCURACY.md) |
| `benchmark_video.py` | Đo một video với engine/mode được chỉ định | [Video](../docs/video_onnx.md) |
| `benchmark_user_workflows.py` | Đo thao tác API với model thật, dữ liệu riêng | [Benchmark](../benchmark/README.md) |
| `benchmark_all.py` | Điều phối test/static checks/browser/model thật tùy chọn | [Benchmark](../benchmark/README.md) |
| `check_regression.py` | So sánh nhận diện trên manifest cố định | [Kiểm thử](../tests/TESTING.md) |
| `run_notebooks.py` | Kiểm tra định dạng hoặc thực thi bản sao notebook | [Notebook](../notebooks/README.md) |

Ví dụ kiểm tra cài đặt không chạy suy luận AI:

```powershell
.\venv\Scripts\python.exe scripts/benchmark.py --help
.\venv\Scripts\python.exe scripts/run_notebooks.py
```

Fixture có nhãn nằm tại `tests/fixtures/test_cases/`. Kết quả và database thử nghiệm nằm dưới `data/` và bị ignore.

`--api-throughput` dùng HTTP loopback và model ảnh thật. Mỗi cấu hình gửi cùng
số luồng đọc lịch sử và nhận diện ảnh. Hai cấu hình khác nhau ở vị trí chạy
inference. Mỗi lượt có SQLite và thư mục media tạm riêng. Kết quả JSON chứa
request/giây và p95 của cả hai luồng. Có thể chọn ảnh bằng `--api-image`.

```powershell
.\venv\Scripts\python.exe scripts/benchmark.py --api-throughput --duration 15 --repeats 3 --output-root data/benchmarks/architecture_stage5
```
