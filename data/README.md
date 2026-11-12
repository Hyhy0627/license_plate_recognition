# Dữ liệu dự án

Các đường dẫn tính từ thư mục gốc repository. Git giữ tài liệu này, bộ ảnh và nhãn trong `test_cases/`, cùng các tệp `.gitkeep` của `raw/` và `outputs/`. Database, ảnh đầu ra và bằng chứng chạy thử được giữ cục bộ theo `.gitignore`; bản clone mới không có sẵn lịch sử nhận diện.

| Đường dẫn | Nội dung |
|---|---|
| `data/alpr.db` | Tài khoản, phiên và lịch sử nhận diện. Không xóa khi dọn cache. |
| `data/outputs/` | Ảnh cắt biển số và ảnh đánh dấu; có thể được database tham chiếu. |
| `data/test_cases/` | Ảnh tổng hợp và `ground_truth.json` cho kiểm thử, benchmark và notebook. |
| `data/test_real_web/` | Ảnh thật, nguồn ảnh, nhãn đối chứng và bằng chứng kiểm thử web. |
| `data/recognition_regression/` | Manifest, ảnh và kết quả so sánh các lượt nhận diện. |
| `data/benchmarks/` | Kết quả benchmark offline. |
| `data/notebook_runs/` | Bản notebook đã thực thi. |
| `data/auth_verification/` | Bằng chứng QA tài khoản và log dịch vụ. |
| `data/raw/` | Dữ liệu thô để bổ sung tập huấn luyện; hiện chỉ có `.gitkeep`. |

## Quy ước khi bổ sung dữ liệu

- Giữ ảnh gốc, nguồn ảnh và nhãn đối chứng đã xác minh để các lượt kiểm thử trước/sau dùng cùng đầu vào.
- Đặt tên ảnh trong `data/raw/` không dấu, không khoảng trắng; ví dụ `car_001.jpg`, `bike_001.jpg`.
- Với nhãn YOLO cho vùng biển số, dùng một lớp `license_plate` (ID `0`), vẽ khung sát toàn bộ biển và không cắt mất ký tự. Bỏ qua biển che khuất quá nặng hoặc không xác định được vị trí.
- Nếu tạo bộ huấn luyện mới, cân đối xe máy/ô tô, ngày/đêm, thời tiết và góc chụp; tách tập train/validation/test, ví dụ theo tỷ lệ 70/20/10. Đây là hướng dẫn thu thập, không phải mô tả dữ liệu hiện có.

## Theo dõi và dọn dữ liệu

`data/test_real_web/` được giữ cục bộ và không đưa lên Git. Lệnh hồi quy nên nhận manifest riêng qua `tool/check_regression.py --cases <đường-dẫn-manifest>`. Nếu chạy công cụ không có `--cases`, nó dùng ảnh và nhãn cục bộ trong thư mục này; bản clone mới sẽ không có các tệp đó.

Trước khi xóa một lượt chạy, kiểm tra tham chiếu trong notebook, manifest, [tài liệu QA](../docs/QA_TESTER.md) và các URL ảnh trong database. Notebook 01 dùng `data/recognition_regression/hardening_20261105/all_cases.json`; Notebook 03 trỏ tới các lượt benchmark và hồi quy ngày 05/11/2026. Một số manifest còn dùng ảnh ở `20261105T081832_650282Z_before`; không xóa chỉ vì tên thư mục cũ. Xem thêm [hướng dẫn notebook](../notebooks/README.md).
