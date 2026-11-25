# Tài liệu dự án

README ở gốc tập trung hướng dẫn cài đặt, cây thư mục, API hiện hành và sơ đồ C4 cấp 2 của kiến trúc mục tiêu. [Kiến trúc triển khai](../README.md#kien-truc-trien-khai)

## Lộ trình chuyển đổi

Môi trường chạy hiện tại gồm Next.js và FastAPI với SQLite, lưu trữ tệp cục bộ và executor video trong tiến trình API. Lộ trình dưới đây mô tả cách chuyển sang kiến trúc phân tán. `APP_ENV=production` hiện bật thuộc tính Secure của cookie. Việc chọn đồng thời cụm PostgreSQL, Redis, worker và MinIO/S3 thuộc giai đoạn triển khai production.

| Giai đoạn | Phạm vi |
|---|---|
| 1 | Mô tả cấu hình một máy chủ và kiến trúc mục tiêu, luồng dữ liệu và ranh giới bảo mật |
| 2 | `main.py` lắp ráp FastAPI qua `create_app()`. Vòng đời, middleware và route media nằm trong `src/api/`. [Adapter NineRouter](cloud_ocr.md) |
| 3 | Pool và migration SQLite/PostgreSQL, adapter local/S3, media riêng tư có HTTP Range. [Cấu hình dữ liệu](data.md) |
| 4 | Tách worker khỏi FastAPI, đưa hàng đợi và giới hạn đăng nhập phân tán lên Redis |
| 5 | Registry trọng số theo SHA‑256, factory ModelRuntime và phép đo throughput HTTP. [Kết quả giai đoạn 5](results/model_runtime_stage5.md) |
| 6 | Đóng gói cấu hình phát triển nhẹ và cụm production có Nginx |
| 7 | Kiểm tra hồi quy OpenAPI, tải đồng thời và bàn giao |

## Tài liệu chuyên đề

| Tài liệu | Phạm vi |
|---|---|
| [Backend hardening](results/backend_hardening.md) | Khóa suy luận, OCR thoát sớm/CCT, video jobs, Range, healthcheck và kiểm chứng |
| [Kết quả đánh giá trước đây](results/evaluation.md) | Pytest, lint/build, trình duyệt, Docker và benchmark local/cloud |
| [cloud_ocr.md](cloud_ocr.md) | Điều kiện gọi NineRouter, dữ liệu gửi đi và cấu hình local |
| [video_onnx.md](video_onnx.md) | Luồng video, mode/engine, giới hạn xử lý và cách đo |
| [security.md](security.md) | Tài khoản, lệnh seed riêng và phạm vi rà soát secret |
| [Đợt tách core/services](results/service_refactor.md) | Đối chiếu API và kết quả local trước–sau |
| [Đợt rà soát bảo mật](results/security_hardening.md) | Kiểm thử seed, migration và bảo mật cơ bản |
| [data.md](data.md) | Dữ liệu runtime và fixture được version hóa |
| [Đợt tổ chức lại thư mục](results/repository_cleanup.md) | Các đường dẫn đã chuyển và kiểm tra tính toàn vẹn |
| [Kiểm thử](../tests/TESTING.md) | Test phần mềm, benchmark, notebook |
| [Nguồn mã và model](video_onnx.md#nguon-ma-va-model) | Phần kế thừa và các điều chỉnh tích hợp |
| [Đợt đồng bộ tài liệu trước đây](results/documentation_sync.md) | Lệnh và kết quả kiểm tra của đợt đồng bộ |

## Trạng thái báo cáo và biểu đồ

`license_plate_recognition.docx` và `license_plate_recognition.pdf` là bản báo cáo đã có trước đợt đồng bộ Markdown này. Nội dung của hai file chưa được cập nhật/tái xuất ở giai đoạn 1. Số liệu lịch sử trong đó không được dùng như kết quả xác nhận của code hiện tại khi thiếu file bằng chứng tương ứng. Text DOCX đã được rà ở giai đoạn 0; PDF chưa được đối chiếu nội dung.

`figures/` chứa biểu đồ có sẵn. Tên file như `ablation_study.png` không đủ chứng minh đã chạy ablation. Chỉ công bố số liệu khi đối chiếu được dữ liệu đầu vào, cấu hình và kết quả thí nghiệm. Số đo mới cùng giới hạn áp dụng nằm trong [báo cáo giai đoạn 5](results/evaluation.md).

Tài liệu QA cục bộ, bản handoff và archive bị ignore không phải thành phần bảo đảm có sẵn trong bản clone. Khi sửa hướng dẫn, cập nhật tài liệu có phạm vi tương ứng và kiểm tra với code; không dùng báo cáo hoặc JSON sinh tự động làm nguồn sự thật thay cho implementation.
