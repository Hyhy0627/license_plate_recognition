# Dọn repository — giai đoạn 2

Ngày thực hiện: **19/11/2026**, Asia/Bangkok. Thực hiện theo phần giai đoạn 2 của `form.md` hiện tại. Không thay thuật toán AI so với working tree đầu giai đoạn; không xóa database, ảnh/video runtime hoặc secret trong môi trường máy.

## Thay đổi và file liên quan

| Trước | Sau | Cách xử lý |
|---|---|---|
| `yolov8n.pt` tại gốc | `models/yolov8n.pt` | Di chuyển file cục bộ vì trọng số chưa được track; SHA256 giữ nguyên |
| `data/test_cases/` | `tests/fixtures/test_cases/` | `git mv`; giữ nguyên 40 JPG và JSON nhãn, tổng 41 file |
| `data/README.md` | `docs/data.md` | `git mv`, cập nhật chính sách dữ liệu |
| Các script Python trong `benchmark/` | `scripts/` | Tập trung benchmark, hồi quy và phép đo thao tác API |
| `notebooks/run_notebooks.py` | `scripts/run_notebooks.py` | Ghi nhận qua đường dẫn gốc được track bằng `git mv` |
| Các nguồn tracked cũ trong `tool/` | `scripts/` hoặc `docs/tools/README.md` | Ghi nhận di chuyển bằng `git mv`, cập nhật nội dung hiện hành |
| Bản archive `test_single_video.py` | `run_single_video_legacy.py` trong cùng archive | Đổi tên cục bộ; không đưa script đường dẫn máy cá nhân vào source hoạt động |

- `src/config.py`, `src/api/video_routes.py`, `.env.example`, `docker-compose.yml`: cập nhật vị trí model phương tiện. Compose dùng volume `models/` đã có, bỏ mount riêng của file trọng số tại gốc. Dockerfile không có đường dẫn riêng tới file này nên không cần đổi lệnh COPY.
- `models/checksums.txt`: SHA256 cho **7 trọng số hiện có**. `best_toy.pt` được ghi như inventory cục bộ, không khẳng định nó được dùng trong runtime mặc định. Không đưa trọng số vào Git.
- `.gitignore`: ignore toàn bộ `/data/`. Bỏ tracking ba `.gitkeep` runtime nhưng giữ các file đó trên đĩa. `.env` vẫn bị ignore; `.env.example` khai báo đủ mọi trường Settings, bỏ biến không dùng, dùng default hybrid như code. `.env` thật không cần chỉnh vì trước đó dùng default model path; các lựa chọn OCR/API key thật được giữ nguyên.
- `.dockerignore`: loại dữ liệu runtime và fixture/test khỏi build context backend; model vẫn được mount khi chạy.
- `pytest.ini`: `testpaths=tests`, `pythonpath=.`, bỏ archive/handoff/external/venv khỏi discovery. Lệnh pytest không truyền thư mục đã chạy toàn bộ bộ test đang hoạt động.
- `scripts/__init__.py`, các script benchmark/runner, `notebooks/_support.py`, notebook 01 và `tests/test_benchmark.py`: cập nhật đường dẫn/import tới package scripts và fixture mới.
- README, kiến trúc, hướng dẫn benchmark/test/notebook/video/model/cloud và mục lục docs: cập nhật các lệnh, link, default cấu hình. Các kết quả cũ ở AUDIT/giai đoạn 1 giữ tính lịch sử; chỉ sửa link tài liệu đã chuyển.

Nguồn Python đã được chuyển cục bộ từ những lần làm trước được đưa qua tên tracked gốc trước khi gọi `git mv`, nhằm ghi nhận lịch sử mà vẫn giữ nội dung working tree hiện tại. Các script vốn chưa tracked được di chuyển cục bộ và thêm tại vị trí mới; không tạo commit trung gian chứa nguồn cũ.

## Công cụ tài liệu và dữ liệu cũ

`docs/tools/README.md` định nghĩa phạm vi công cụ báo cáo/sơ đồ. Không khôi phục các generator đã thiếu template hoặc chứa số liệu ghi sẵn thành công cụ đang hoạt động. Chúng vẫn nằm trong `.local_archive/` ngoài Git. Công cụ chạy video được duy trì là `scripts/benchmark_video.py`, nhận đường dẫn đầu vào qua CLI.

`handoff_unpushed/` được giữ nguyên ngoài Git; bản form hiện tại không yêu cầu dọn handoff. Các ảnh/manifest thực tế và bằng chứng lịch sử trong `data/` không được dịch chuyển/sửa nhãn hàng loạt; chúng là dữ liệu thử nghiệm cục bộ không có trong clone. Fixture được version hóa nằm riêng trong `tests/fixtures/`. Khi dùng lại manifest cũ, phải ánh xạ đường dẫn và kiểm tra hash thay vì sửa kết quả lịch sử.

Theo xác nhận của người dùng trong lúc thực hiện, nội dung `THIRD_PARTY_NOTICES.md` được gộp nguyên phần ghi nguồn vào `docs/video_onnx.md`; các liên kết và docstring nguồn được cập nhật, file riêng đã bị xóa được bỏ khỏi Git. Không xóa thêm dữ liệu người dùng. Thư mục `tool/` rỗng được tạo tạm để ghi nhận rename đã được thu dọn. Placeholder `tool/.gitkeep` đã vắng từ trước được bỏ khỏi index. Các xóa/sửa khác có từ trước, ngoài phạm vi giai đoạn, không được gom vào commit này.

## Kiểm tra thực tế

| Kiểm tra/lệnh | Kết quả |
|---|---|
| `venv/Scripts/python.exe -B -u -m pytest -q -p no:cacheprovider` | **85 passed, 1 warning, 15.17s**; exit 0 |
| Hash 41 file fixture trước/sau | Khớp toàn bộ, nhãn/ảnh không đổi byte |
| Hash model phương tiện trước/sau | Khớp; không còn file model ở gốc |
| Kiểm tra SHA256 theo `models/checksums.txt` | Cả 7 file khớp |
| Hash `data/alpr.db` trước/sau sắp xếp và kiểm thử | Khớp; không thay DB người dùng |
| Đọc nhãn qua `scripts.benchmark.load_annotations()` và notebook helper | Cùng đọc đủ 40 ảnh; giải mã được tất cả ảnh |
| Nạp model phương tiện theo Settings hiệu lực và factory video | YOLO phương tiện, detector biển và OCR video nạp thành công từ vị trí cục bộ |
| Đối chiếu `.env.example` với các trường Settings | Đủ biến, không có trường thừa |
| `scripts/run_notebooks.py` | Cả 3 notebook hợp lệ về định dạng; chưa thực thi cell |
| CLI `scripts/benchmark.py --help`, `scripts/benchmark_all.py --help` | Thành công |
| `frontend/node_modules/.bin/tsc.cmd --noEmit --incremental false -p frontend/tsconfig.json` | Exit 0 |
| `docker compose config --format json` | Thành công; kiểm tra model path và volume models đúng vị trí mới |
| Kiểm tra link tài liệu, cú pháp Python, Git ignore và đường dẫn cũ | Đạt: 15 tài liệu, 90 liên kết local, không có đường dẫn/import cũ trong source hoạt động; runtime không được track và được ignore |

Lượt pytest đầy đủ chạy ngoài sandbox với `PYTHONUTF8=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, timeout tối đa 60 giây. Điều kiện chạy được ghi rõ vì các lượt trong sandbox ở giai đoạn trước bị timeout. Không kết luận nguyên nhân chi tiết của timeout trước đó chỉ từ việc lượt này hoàn tất. Warning là `PydanticDeprecatedSince20` tại `Settings.Config`; chưa sửa ở giai đoạn dọn file.

## Giới hạn và việc tiếp theo

- Chưa chạy `docker compose up`, build frontend production, Playwright hoặc benchmark độ chính xác/hiệu năng mới trong giai đoạn 2. Số test xanh không thay cho số đo AI; tốc độ/độ chính xác mới: **chưa đo**.
- Khởi động lại backend đang chạy để nạp default model path mới. Tiến trình cũ có thể còn giữ cấu hình/model trong bộ nhớ.
- Cấu hình snapshot đưa vào commit dùng API key rỗng; một giá trị key từng có trong HEAD cũ đã được bỏ trong working tree từ trước. Không sao chép giá trị đó vào tài liệu. Kiểm toán/thu hồi secret trong lịch sử Git chưa được thực hiện; nếu key còn hiệu lực cần thay tại nhà cung cấp.
- Báo cáo Word/PDF và biểu đồ cũ không được tái xuất. Các khác biệt thuật toán đang có từ trước ở tracker không bị ghi đè.
- Working tree còn các thay đổi tính năng từ trước chưa commit. Commit giai đoạn 2 chỉ ghi nhận các file sắp xếp/cấu hình/đường dẫn liên quan, không tuyên bố đã nghiệm thu hoặc đóng gói toàn bộ ứng dụng để clone độc lập.
