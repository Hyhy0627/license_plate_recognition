# Tài liệu dự án

[README ở gốc](../README.md) là điểm bắt đầu để cài đặt/chạy ứng dụng. [PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md) là mô tả kiến trúc, module, API và database hiện hành. Các tài liệu dưới đây bổ sung theo công việc, không duy trì một cây thư mục hay danh sách API thứ hai.

| Tài liệu | Phạm vi |
|---|---|
| [cloud_ocr.md](cloud_ocr.md) | Điều kiện gọi NineRouter, dữ liệu gửi đi và cấu hình local |
| [video_onnx.md](video_onnx.md) | Luồng video, mode/engine, giới hạn xử lý và cách đo |
| [Kiểm thử](../tests/TESTING.md) | Test phần mềm, benchmark, notebook |
| [Nguồn mã và model](../THIRD_PARTY_NOTICES.md) | Phần kế thừa và các điều chỉnh tích hợp |
| [Kết quả giai đoạn 1](results/documentation_sync.md) | Lệnh/kết quả kiểm tra của đợt đồng bộ tài liệu |
| [Kiểm toán giai đoạn 0](../AUDIT.md) | Snapshot sai lệch trước đồng bộ; không phải hướng dẫn cấu hình mới |

## Trạng thái báo cáo và biểu đồ

`license_plate_recognition.docx` và `license_plate_recognition.pdf` là bản báo cáo đã có trước đợt đồng bộ Markdown này. Nội dung của hai file chưa được cập nhật/tái xuất ở giai đoạn 1. Số liệu lịch sử trong đó không được dùng như kết quả xác nhận của code hiện tại khi thiếu file bằng chứng tương ứng. Text DOCX đã được rà ở giai đoạn 0; PDF chưa được đối chiếu nội dung.

`figures/` chứa biểu đồ có sẵn. Tên file như `ablation_study.png` không đủ chứng minh đã chạy ablation. Chỉ công bố số liệu khi đối chiếu được dữ liệu đầu vào, cấu hình và kết quả thí nghiệm. Tốc độ/độ chính xác AI trong đợt đồng bộ hiện tại: **chưa đo**.

Tài liệu QA cục bộ, bản handoff và archive bị ignore không phải thành phần bảo đảm có sẵn trong bản clone. Khi sửa hướng dẫn, cập nhật tài liệu có phạm vi tương ứng và kiểm tra với code; không dùng báo cáo hoặc JSON sinh tự động làm nguồn sự thật thay cho implementation.
