# Hướng dẫn kiểm thử và đánh giá

Mọi lệnh chạy từ **thư mục gốc repository**.

---

## 1. Kiểm thử tự động

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
npm --prefix frontend run lint
npm --prefix frontend run build
```

Các bài kiểm thử Python bao gồm: tài khoản, phân quyền dữ liệu, hậu xử lý biển số, ca khó, metric benchmark và tính nhất quán của bằng chứng notebook. Lệnh lint/build kiểm tra mã frontend; chúng không thay thế thao tác kiểm thử trên trình duyệt.

---

## 2. Benchmark offline có nhãn

Cần có ảnh và `data/test_cases/ground_truth.json` trước khi chạy:

```powershell
.\venv\Scripts\python.exe tool/benchmark.py --dataset-kind synthetic
```

Kết quả lưu vào `data/benchmarks/<run-id>/`, gồm `metrics.json`, `predictions.json`, `per_image.csv` và các biểu đồ nếu bật xuất biểu đồ.

Bộ `data/test_cases` hiện tại là ảnh tổng hợp. Benchmark đo detector, YOLO OCR và hậu xử lý; **không** bao gồm nhánh dự phòng API, cloud, HTTP, database hoặc giao diện. Chỉ số từ bộ này không đại diện độ chính xác trên ảnh giao thông thật.

Xem định nghĩa chỉ số, định dạng nhãn và phạm vi benchmark: [`tool/BENCHMARK.md`](../tool/BENCHMARK.md).

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
.\venv\Scripts\python.exe tool/check_regression.py --label local_before --mode local --cases data/my_test_set/cases.json
```

Công cụ gọi trực tiếp handler API, sử dụng database và thư mục ảnh đầu ra riêng cho từng lượt. Bằng chứng nằm trong `data/recognition_regression/<run-id>/`, gồm manifest, hash ảnh, nhãn đối chứng và phản hồi nhận diện.

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
.\venv\Scripts\python.exe tool/run_notebooks.py

# Chạy và lưu bản đã thực thi vào data/notebook_runs/<run-id>/
.\venv\Scripts\python.exe tool/run_notebooks.py --execute
```

Notebook cần dữ liệu, model và các lượt bằng chứng tương ứng; không tự có đủ dữ liệu sau khi clone.

Xem thêm: [`notebooks/README.md`](../notebooks/README.md). Khi chuyển máy, cập nhật đường dẫn ở ô cấu hình hoặc manifest cho phù hợp.
