# Dữ liệu của dự án

Các đường dẫn dưới đây tính từ thư mục gốc repository. Dữ liệu được giữ theo mục đích sử dụng, không cần tải mọi thư mục vào ứng dụng.

| Đường dẫn | Mục đích | Khi dọn dữ liệu |
|---|---|---|
| `data/alpr.db` | Tài khoản, phiên và lịch sử nhận diện | Giữ; không xóa để dọn cache |
| `data/outputs/` | Ảnh cắt và ảnh đánh dấu của các lần nhận diện | Giữ ảnh còn được database hoặc bằng chứng kiểm thử tham chiếu |
| `data/test_cases/` | Ảnh tổng hợp và `ground_truth.json` dùng cho benchmark/notebook | Giữ nguyên ảnh và nhãn đối chứng |
| `data/test_real_web/` | Ảnh thật, nguồn ảnh, nhãn và bằng chứng kiểm thử web | Git chỉ nhận bộ đầu vào cố định bên dưới; bằng chứng chạy thử giữ cục bộ |
| `data/recognition_regression/` | Các lượt đối chứng local/hybrid, ảnh ca khó và kết quả trước/sau | Giữ mốc trước/sau và các fixture mà manifest sử dụng; có thể lưu trữ các lượt trung gian |
| `data/benchmarks/` | Kết quả benchmark offline | Giữ lượt được notebook hoặc tài liệu tham chiếu |
| `data/notebook_runs/` | Bản notebook đã chạy | Giữ lượt hoàn tất mới nhất; có thể dọn lượt lỗi hoặc thư mục rỗng |
| `data/auth_verification/` | Bằng chứng QA tài khoản và log dịch vụ | Giữ lượt QA được dẫn trong tài liệu; không dọn log đang được dịch vụ sử dụng |
| `data/raw/` | Chỗ đặt dữ liệu thô khi cần | Hiện giữ `.gitkeep` để duy trì cấu trúc |

## Tệp kiểm thử web được đưa lên Git

`.gitignore` bỏ qua mặc định toàn bộ `data/test_real_web/`, chỉ cho phép 7 tệp:

- Ba ảnh mẫu: `car_30A_11111.jpg`, `car_30A_88888.jpg`, `motorbike_69B1_77777.png`.
- `sources.json`: nguồn ảnh và nhãn biển số đối chứng.
- `ui_test_results.json`: tuy có kết quả UI, công cụ `tool/check_recognition_regression.py` hiện vẫn đọc tệp này để lấy ảnh và nhãn đối chứng.
- `hard_cases_20261105/cases.json` và `hard_cases_20261105/input_hashes.json`: danh sách ca khó, nhãn và mã băm ảnh đầu vào.

Ảnh chụp màn hình, log, báo cáo, kết quả từng lượt và tệp mới khác trong thư mục này chỉ lưu cục bộ. Quy tắc Git không xóa dữ liệu trên máy. Khi bổ sung ảnh hoặc manifest dùng chung, cập nhật danh sách ngoại lệ trong `.gitignore`.

## Những mốc đang được dùng

- Notebook 01 dùng `data/recognition_regression/hardening_20261105/all_cases.json`.
- Notebook 03 dùng benchmark `20261105T084132_896570Z`, lượt local trước `20261105T091906_946715Z_hardening_before_local`, lượt sau `20261105T093925_904428Z_hardening_final_local` và bằng chứng Brave trong `hardening_20261105/before_ui/`.
- Bộ đối chứng âm tính trong các manifest vẫn tham chiếu hai ảnh ở `20261105T081832_650282Z_before`. Không xóa thư mục này chỉ vì tên chứa ngày cũ.
- Bằng chứng QA tài khoản được dẫn từ [tài liệu QA](../docs/QA_TESTER.md). Một số lượt cũ còn được giữ vì là đầu vào hoặc bằng chứng cho các so sánh đó.

## Lần dọn ngày 06/11/2026

Đã bỏ khỏi `data` các lượt chạy dở, lượt trung gian đã có kết quả thay thế, ảnh chẩn đoán tạm và ảnh đầu ra không được database hay JSON bằng chứng còn lại tham chiếu. Database, bộ nhãn, ảnh đầu vào, kết quả đối chứng được giữ nguyên.

Đợt dọn này loại bỏ 236 tệp dư và 32 thư mục rỗng. Bản sao khôi phục đã được xóa theo yêu cầu sau khi xác minh 539 tệp dữ liệu được giữ lại cùng 47 tệp mã nguồn, cấu hình và trọng số không thay đổi. Database vẫn giữ 110 bản ghi lịch sử. Các tệp đã dọn không còn bản sao trong dự án.

Không coi mọi thư mục có ngày trong tên là dữ liệu rác. Trước khi dọn lượt tiếp theo, đối chiếu đường dẫn trong notebook, manifest, tài liệu QA và các URL ảnh trong database. Giữ ảnh/nhãn cố định khi so sánh trước–sau.

Hướng dẫn nhãn ban đầu: [dataset_guidelines.md](dataset_guidelines.md).
