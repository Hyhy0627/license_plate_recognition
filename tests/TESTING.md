# Hướng dẫn kiểm thử và đánh giá

Mọi lệnh chạy từ **thư mục gốc repository**. Test tài khoản dùng cookie phiên và kiểm tra chủ sở hữu dữ liệu. [Cơ chế xác thực](../docs/security.md)

Bộ kiểm thử thao tác người dùng và benchmark tổng hợp mới:
[benchmark/README.md](../benchmark/README.md). Chạy
`.\venv\Scripts\python.exe scripts/benchmark_all.py` để xuất báo cáo HTML/JSON/CSV
bao gồm pytest, TypeScript, ESLint và Playwright. Runner không chạy production build; lệnh build được chạy riêng bên dưới. Thêm `--real` để đo model thật.

---

## 1. Kiểm thử tự động

Các test tích hợp PostgreSQL chạy khi đặt `ALPR_TEST_POSTGRES_URL` trỏ đến cơ sở dữ liệu kiểm thử. Tài khoản cần quyền tạo schema. Mỗi test tạo và dọn schema riêng. Bộ kiểm thử mặc định chạy bằng SQLite và dùng nguồn media giả lập để kiểm tra HTTP Range của S3. [Cấu hình cơ sở dữ liệu và lưu trữ](../docs/data.md)

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
npm --prefix frontend run lint
npm --prefix frontend run build
```

Các bài kiểm thử Python bao gồm: tài khoản, phân quyền dữ liệu, hậu xử lý biển số, ca khó, metric benchmark và tính nhất quán của bằng chứng notebook. Lệnh lint/build kiểm tra mã frontend; chúng không thay thế thao tác kiểm thử trên trình duyệt.

---

## 2. Benchmark offline có nhãn

Cần có ảnh và `tests/fixtures/test_cases/ground_truth.json` trước khi chạy:

```powershell
.\venv\Scripts\python.exe scripts/benchmark.py --dataset-kind synthetic
```

Kết quả lưu vào `data/benchmarks/<run-id>/`, gồm `metrics.json`, `predictions.json`, `per_image.csv` và các biểu đồ nếu bật xuất biểu đồ.

Bộ `tests/fixtures/test_cases` hiện tại là ảnh tổng hợp. Benchmark đo detector, YOLO OCR và hậu xử lý; **không** bao gồm nhánh dự phòng API, cloud, HTTP, database hoặc giao diện. Chỉ số từ bộ này không đại diện độ chính xác trên ảnh giao thông thật.

Xem định nghĩa chỉ số, định dạng nhãn và phạm vi benchmark: [`benchmark/ACCURACY.md`](../benchmark/ACCURACY.md).

---

## 3. Kiểm thử hồi quy trên ảnh cố định

Tạo thư mục ảnh, ví dụ `data/my_test_set/`, và manifest `data/my_test_set/cases.json`. Đường dẫn `path` trong manifest tính từ thư mục làm việc.

**Ví dụ cấu trúc manifest** — thay tên ảnh và nhãn bằng dữ liệu đã kiểm tra thủ công:

```json
{
  "cases": [
    {
      "id": "vehicle_01",
      "path": "data/my_test_set/vehicle_01.jpg",
      "kind": "real",
      "expected": ["29A-123.45"]
    },
    {
      "id": "negative_01",
      "path": "data/my_test_set/negative_01.jpg",
      "kind": "real",
      "expected": []
    }
  ]
}
```

`expected` liệt kê tất cả biển số có thể xác định trong ảnh; dùng mảng rỗng cho ảnh không có biển. Ảnh tổng hợp dùng `kind: "synthetic"`, không trộn với nhóm ảnh thật khi tổng hợp kết quả.

```powershell
.\venv\Scripts\python.exe scripts/check_regression.py --label local_before --mode local --cases data/my_test_set/cases.json
```

Công cụ gọi trực tiếp service ảnh dùng chung với API, sử dụng database và thư mục ảnh đầu ra riêng cho từng lượt. Bằng chứng nằm trong `data/recognition_regression/<run-id>/`, gồm manifest, hash ảnh, nhãn đối chứng và phản hồi nhận diện.

Sau khi sửa nhận diện, chạy lại với cùng ảnh, cùng nhãn và đổi nhãn thành `local_after`. Dùng `--mode hybrid` để đánh giá riêng chế độ có dịch vụ Vision. Không gộp kết quả local/hybrid hoặc sửa nhãn để khớp dự đoán.

---

## 4. Kiểm thử trực tiếp trên web

Chạy cả backend và frontend, đăng nhập bằng tài khoản kiểm thử và tải lên đúng các ảnh trong manifest. Đối chiếu từng biển hiển thị với `expected`, kiểm tra lịch sử và lưu bằng chứng trước/sau.

Kiểm thử qua trình duyệt tự động cần Playwright cùng trình duyệt được cài riêng và nên dùng môi trường kiểm thử riêng.

---

## 5. Notebooks phân tích

Notebook phục vụ thực nghiệm và phân tích; không cần chạy để khởi động web.

| Notebook | Nội dung |
|---|---|
| [01 — Khám phá dữ liệu](../notebooks/01_data_exploration.ipynb) | Kiểm tra ảnh, bbox, kích thước, độ sáng và nguồn dữ liệu |
| [02 — Thực nghiệm tiền xử lý](../notebooks/02_preprocessing_experiments.ipynb) | So sánh OCR trên cùng crop trước/sau tăng cường ảnh |
| [03 — Đánh giá kết quả](../notebooks/03_evaluation_metrics.ipynb) | Tính lại metric từ dự đoán lưu và so sánh các lượt hồi quy |

```powershell
# Chỉ kiểm tra định dạng
.\venv\Scripts\python.exe scripts/run_notebooks.py

# Chạy và lưu bản đã thực thi vào data/notebook_runs/<run-id>/
.\venv\Scripts\python.exe scripts/run_notebooks.py --execute
```

Notebook cần dữ liệu, model và các lượt bằng chứng tương ứng; không tự có đủ dữ liệu sau khi clone.

Xem thêm: [`notebooks/README.md`](../notebooks/README.md). Khi chuyển máy, cập nhật đường dẫn ở ô cấu hình hoặc manifest cho phù hợp.

## 6. Ghi kết quả theo lần chạy

Ghi lệnh, ngày chạy, phiên bản/cấu hình và tổng pass/fail/skip từ kết quả thực tế. Lượt timeout hoặc bị dừng được ghi **chưa hoàn tất**, không suy ra toàn bộ test xanh. Chạy một nhóm file chỉ xác nhận nhóm đó. Xem [kết quả giai đoạn 1](../docs/results/documentation_sync.md).

Khi cần tái hiện lượt kiểm tra không dùng plugin pytest ngoài, đặt `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` trong môi trường của tiến trình kiểm tra và ghi rõ lựa chọn này; đây không phải cấu hình mặc định của runner tổng hợp. `pytest.ini` đặt `testpaths=tests` và loại archive/handoff khỏi discovery; cả `pytest` và `pytest tests` đều nhắm vào bộ test đang hoạt động. Các bản sao cục bộ không được coi là test bổ sung.

Môi trường phát triển/CI cài `python -m pip install -r requirements-dev.txt` để có HTTPX cho TestClient và Ruff. Chạy `python -m ruff check main.py src scripts tests --select E9,F63,F7,F82` để kiểm tra lỗi cú pháp và tên không xác định; đây không phải kiểm tra toàn bộ quy tắc định dạng. CI còn chạy pytest và lint/typecheck/build frontend. Việc dependency đã có trên máy phát triển không chứng minh một môi trường mới đã đầy đủ. Kết quả test phần mềm, benchmark local và đánh giá có cloud phải được báo cáo riêng.

Kết quả kiểm thử và benchmark mới nhất, lệnh tái hiện và các phần chưa đo: [giai đoạn 5](../docs/results/evaluation.md). Workflow GitHub chỉ chạy trên máy chủ sau khi push/PR; kết quả chạy cục bộ không được gọi là CI đã xanh.

Kết quả tái cấu trúc core/services và đối chiếu OpenAPI/benchmark local giới hạn xem [báo cáo giai đoạn 4](../docs/results/service_refactor.md). Các mock được đặt tại service/factory mới; assertion về endpoint và quyền dữ liệu được giữ nguyên.
