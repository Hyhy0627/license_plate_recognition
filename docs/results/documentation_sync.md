# Đồng bộ tài liệu — giai đoạn 1

Ngày thực hiện: **19/11/2026**, Asia/Bangkok. Phạm vi là bộ hướng dẫn Markdown/text của working tree hiện tại; không thay code AI, endpoint, schema, file môi trường, trọng số hoặc dữ liệu runtime. Bản `AUDIT.md` ghi nhận trạng thái trước sửa và có trong lịch sử Git.

## Thay đổi

- README chỉ giữ cách cài/chạy và mục lục; PROJECT_STRUCTURE là tài liệu kiến trúc, module, API và database hiện hành.
- Sửa phiên đăng nhập sang cookie opaque có trạng thái, scrypt và phân quyền theo chủ sở hữu; bỏ mô tả JWT/bcrypt, tài khoản/mật khẩu mặc định và quyền Admin/Guest không có trong code.
- Đối chiếu danh sách endpoint với OpenAPI thực tế. Sửa tên bảng ORM, trách nhiệm migration, trạng thái job video và giới hạn triển khai một backend.
- Nêu rõ engine chính cho ảnh/video, quan hệ mode/engine, phần mã kế thừa thực sự được gọi và trọng số cần cung cấp riêng.
- Bổ sung hướng dẫn NineRouter: thời điểm kích hoạt, crop/toàn ảnh gửi đi, gateway bên ngoài và chế độ local.
- Bỏ số thời gian/tăng tốc không có file bằng chứng khỏi hướng dẫn video. Chỉ ghi giới hạn cấu hình theo code; không chuyển chúng thành số đo hiệu năng.
- Đồng nhất các hướng dẫn frontend, test, benchmark, model, dữ liệu và notebook bằng liên kết theo phạm vi. Không tạo JSON inventory mới; hai JSON mô tả ở gốc không tồn tại lúc kiểm tra.
- Không xóa/di chuyển file trong giai đoạn này. Không cập nhật nội dung báo cáo Word/PDF; docs/README.md ghi rõ trạng thái bản cũ để tránh dùng chúng như mô tả runtime hiện hành.

## File thuộc bộ tài liệu

| File | Trách nhiệm |
|---|---|
| [README.md](../../README.md) | Cài đặt, khởi động và mục lục |
| `PROJECT_STRUCTURE.md` tại thời điểm rà soát | Kiến trúc, module, OpenAPI và ORM. Các mục này hiện nằm trong [README gốc](../../README.md) |
| [frontend/README.md](../../frontend/README.md) | API URL, cookie và kiểm tra frontend |
| [tests/TESTING.md](../../tests/TESTING.md) | Lệnh/phạm vi kiểm thử |
| [benchmark/README.md](../../benchmark/README.md) | Runner chức năng và ranh giới phép đo |
| [benchmark/ACCURACY.md](../../benchmark/ACCURACY.md) | Benchmark ảnh local có nhãn |
| [models/weights_readme.txt](../../models/weights_readme.txt) | Trọng số bắt buộc/tùy chọn và cách cài |
| [data/README.md](../data.md) | Fixture, dữ liệu runtime và giới hạn ignore hiện tại |
| [notebooks/README.md](../../notebooks/README.md) | Điều kiện thực thi và bằng chứng lịch sử |
| [docs/README.md](../README.md) | Mục lục chuyên đề và trạng thái báo cáo |
| [docs/video_onnx.md](../video_onnx.md) | Luồng video, cấu hình, giới hạn và đo hiệu năng |
| [docs/cloud_ocr.md](../cloud_ocr.md) | Điều kiện remote và dữ liệu gửi qua gateway |
| [THIRD_PARTY_NOTICES.md](../video_onnx.md#nguon-ma-va-model) | Ghi nhận nguồn mã/model đã có; giữ nội dung nguồn |
| Tài liệu này | Kết quả và giới hạn kiểm tra giai đoạn 1 |

Các tài liệu chuyên đề không duy trì thêm bảng endpoint/ORM hoặc cây thư mục đầy đủ. Code là nguồn đối chiếu khi cập nhật; các snapshot kiểm toán/báo cáo lịch sử có thời điểm riêng.

## Kiểm tra

| Lệnh/thao tác | Kết quả |
|---|---|
| `venv/Scripts/python.exe -B -u -m pytest tests/test_benchmark.py tests/test_video_models.py tests/test_notebook_evidence.py tests/test_plate_reader.py -q -p no:cacheprovider` | **25 passed, 1 warning, 1.66s**; exit 0 |
| `venv/Scripts/python.exe -B -u -m pytest tests -q -p no:cacheprovider` | **Chưa hoàn tất sau 60 giây**; tiến trình bị dừng theo timeout, không có tổng pass/fail/skip |
| `frontend/node_modules/.bin/tsc.cmd --noEmit --incremental false -p frontend/tsconfig.json` | Exit 0 |
| `npm --prefix frontend run lint` | Exit 0 |
| `docker compose config --quiet` | Exit 0; chỉ kiểm tra cấu hình, không khởi động container |
| `venv/Scripts/python.exe notebooks/run_notebooks.py` | Cả 3 notebook hợp lệ về định dạng; chưa thực thi cell |
| So tập method/path trong PROJECT_STRUCTURE với `main.app.openapi()` | Khớp cả **12** tổ hợp phương thức/đường dẫn |
| Quét hướng dẫn hiện hành tìm endpoint v1, mật khẩu demo, mô tả quảng cáo và số ms chưa có bằng chứng | Không phát hiện các mẫu đã kiểm tra |
| Kiểm tra liên kết nội bộ và whitespace | Đạt với 14 file tài liệu của giai đoạn; không có liên kết local bị hỏng hoặc whitespace cuối dòng |

Pytest chạy trong tiến trình con với `PYTHONUTF8=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, không sửa cấu hình dự án. Warning của nhóm 25 test là `PydanticDeprecatedSince20` tại `Settings.Config`; không sửa code trong giai đoạn tài liệu. Thời gian 1.66s là thời gian pytest báo cho nhóm test đó, không phải độ trễ nhận diện.

## Còn tồn đọng

- Chưa xác nhận toàn bộ pytest xanh. Không diễn giải kết quả nhóm 25 test thành kết quả toàn bộ.
- Chưa chạy production build/frontend browser hoặc `docker compose up` trong giai đoạn 1.
- Benchmark AI local/hybrid/video mới: **chưa đo**. Chưa có kết quả độ chính xác giao thông thật, MOTA/IDF1 hoặc ablation mới để bổ sung.
- Báo cáo Word/PDF và biểu đồ cũ cần được xử lý như snapshot; muốn phát hành lại phải cập nhật nội dung và kiểm tra layout riêng.
- Model phương tiện vẫn ở gốc; fixture vẫn trong data/test_cases; ignore file trực tiếp trong data/outputs chưa bao phủ hết; .env.example còn khác default code. Đây là các thay đổi cấu hình/bố trí được để lại cho giai đoạn sau.
- Nhiều thay đổi code/cấu hình từ trước vẫn chưa commit; commit giai đoạn này chỉ gom các file tài liệu đã kiểm tra, không nhận chúng là code đã commit hoặc đã được nghiệm thu.

Ghi chú giai đoạn 2: hướng dẫn dữ liệu đã chuyển sang [docs/data.md](../data.md). Các đường dẫn mô tả ở trên là snapshot giai đoạn 1; trạng thái mới xem [repository_cleanup.md](repository_cleanup.md).
