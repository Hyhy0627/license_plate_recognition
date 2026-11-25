# Giai đoạn 5 · Quản lý mô hình và runtime inference

## Thay đổi

- `src/core/models/` định nghĩa registry `baseline-v1` và factory `ModelRuntime`. Adapter local dùng Ultralytics và ONNX Runtime. Cache theo tiến trình và khóa suy luận nằm trong `src/services/model_runtime.py`.
- `scripts/download_models.py` cài trọng số từ HTTPS hoặc S3, dùng `models/checksums.txt` để kiểm tra trước khi thay tệp đích. `scripts/setup_video_models.py` giữ lệnh cài detector biển và OCR video. `--check` xác minh cục bộ.
- `src/config.py`, `src/core/ocr/engine.py`, `src/services/video_jobs.py` và `src/api/lifespan.py` dùng các đường dẫn qua registry hoặc cấu hình môi trường. `OCR_MODEL_PATH` cho phép chọn lại checkpoint OCR ký tự.
- `scripts/benchmark.py --api-throughput` dùng `scripts/benchmark_api.py` để đo HTTP thực. `scripts/benchmark_user_workflows.py` ghi checksum theo đường dẫn OCR đã cấu hình. `tests/test_model_registry.py` kiểm tra registry, giữ tệp cũ khi hash sai, tải qua SDK S3 và cấu hình runtime.

## Kết quả kiểm chứng

Các lệnh chạy từ thư mục gốc bằng Python trong `venv`.

| Lệnh hoặc phép kiểm tra | Exit code | Kết quả |
|---|---:|---|
| `python -m pytest tests -q -W error -p no:cacheprovider` | 0 | 141 test pass trong 21,81 giây, gồm tích hợp PostgreSQL 17 |
| `python -m ruff check main.py src scripts tests` và `git diff --check` | 0 | Qua kiểm tra |
| `python scripts/download_models.py --check` | 0 | 6 tệp khớp SHA‑256 trong 0,42 giây |
| Cài nhóm video vào thư mục trống rồi kiểm tra lại SHA‑256 | 0 | 3 trọng số tải qua HTTPS và 1 cấu hình đi kèm đều khớp. Tổng thời gian 599,19 giây. [Nguồn trọng số phương tiện](https://github.com/ultralytics/assets/releases/tag/v8.3.0) |
| `python scripts/benchmark.py --dataset-kind synthetic --limit 2 --no-plots` | 0 | Smoke offline chạy trong 10,68 giây, p95 pipeline 517,19 ms. Cả hai ảnh mờ tổng hợp đều không có biển dự đoán |
| `python scripts/benchmark_user_workflows.py --iterations 1 --image <ảnh> --video <video> --output <thư mục>` | 0 | 26 phản hồi đúng mã HTTP, gồm upload video, trạng thái hoàn tất và Range 206. Tổng thời gian 11,05 giây |
| So sánh OpenAPI JSON đã chuẩn hóa với snapshot trước khi sửa | 0 | 12 path, trùng từng byte. SHA‑256 `2c3a8f3e9a321e872281fad2a731383813a6120b3cd30c0a86f163e67e020622` |

## Benchmark throughput HTTP

```powershell
.\venv\Scripts\python.exe scripts/benchmark.py --api-throughput --api-image data/test_real_web/car_30A_11111.jpg --repeats 3 --duration 12 --metadata-clients 4 --inference-clients 2 --output-root data/benchmarks/architecture_stage5
```

Lệnh trả exit code 0 sau 123,77 giây. Máy dùng Windows 11 với CPU 12 luồng
logic và PyTorch dùng 2 luồng. Mỗi cấu hình chạy 3 lượt,
mỗi lượt đo 12 giây sau warmup, dùng SQLite và kho tệp tạm. Cả hai cấu hình gửi
cùng loại request và số client đọc lịch sử, đồng thời chạy detector và YOLO OCR.
Cấu hình tách tiến trình nhận request inference trên một tiến trình FastAPI
riêng cùng máy. Các số dưới đây là trung vị của từng chỉ số qua 3 lượt.

| Chỉ số | API chạy chung inference | API metadata và inference tách tiến trình |
|---|---:|---:|
| Lịch sử, request/giây | 178,75 | 201,75 |
| Lịch sử, p95 | 40,14 ms | 35,14 ms |
| Nhận diện ảnh, request/giây | 1,58 | 2,00 |
| Nhận diện ảnh, p95 | 1.323,04 ms | 1.004,23 ms |

Bằng chứng từng lượt nằm trong
`data/benchmarks/architecture_stage5/api_throughput_20261120T114452_106170Z.json`.
Phép đo đại diện cho fixture và máy kiểm thử. Lệnh benchmark dùng cấu hình
tách tiến trình riêng cho phép đo. FastAPI triển khai thông thường vẫn phục vụ
nhận diện ảnh đồng bộ và video local vẫn dùng executor hiện có.

## Tương thích và giới hạn

- Local dùng lại đường dẫn mặc định và model hiện có. Frontend dùng OpenAPI cũ.
- Phần cài trọng số độc lập với DB và lưu trữ media. Hai trọng số ảnh cần có sẵn hoặc cần một bucket/Release của nhóm. Kiểm thử S3 dùng phản hồi mô phỏng của SDK.
- Backend `local` đã được kiểm chứng. Triton, TorchServe và ONNX Runtime Server là các adapter có thể bổ sung vào factory. Chế độ worker Redis vẫn thuộc giai đoạn 4.
