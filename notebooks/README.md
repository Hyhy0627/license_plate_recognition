# Notebooks của đồ án ALPR

Notebook không nằm trong luồng chạy web. Backend dùng `src/`; frontend gọi API.
Giữ notebook để khám phá dữ liệu, thử nghiệm có đối chứng và kiểm tra số liệu.

| Notebook | Công việc | Giới hạn |
|---|---|---|
| `01_data_exploration.ipynb` | Kiểm tra ảnh, bbox, kích thước, độ sáng, hash và nguồn dữ liệu | Không suy loại xe từ tên file; không coi bbox đúng tọa độ là nhãn đúng nội dung |
| `02_preprocessing_experiments.ipynb` | Chạy OCR local trên cùng crop GT, so đầu vào gốc với CLAHE + bilateral | Mặc định 2 ảnh/nhóm; vị trí GT đã biết nên không phải kết quả detection/web |
| `03_evaluation_metrics.ipynb` | Tính lại benchmark từ dự đoán lưu; đối chiếu hồi quy local và Brave riêng | Phân tích lịch sử; không tự chạy lại endpoint hoặc suy tỷ lệ trên ảnh chưa kiểm thử |

## Mở và chạy

Trong VS Code, mở file `.ipynb`, chọn **Select Kernel → Python Environments → venv/Scripts/python.exe**, rồi **Run All**. Cần extension Jupyter nếu VS Code chưa có.
Chạy từ thư mục gốc dự án hoặc `notebooks`; không phụ thuộc đường dẫn `../` cố định.

Thư viện notebook được khai báo trong `requirements.txt`. Nếu môi trường cũ thiếu phần này:

```powershell
.\venv\Scripts\python.exe -m pip install nbformat nbclient ipykernel pandas matplotlib
```

Kiểm tra định dạng hoặc chạy cả ba notebook bằng Python của dự án:

```powershell
.\venv\Scripts\python.exe tool/run_notebooks.py
.\venv\Scripts\python.exe tool/run_notebooks.py --execute
```

`run_notebooks.py` dùng để kiểm tra và chạy tự động. Nó không sinh KPI ghi sẵn hoặc ghi đè notebook nguồn.
`--execute` tạo bản đã chạy và `execution.json` ở thư mục mới `data/notebook_runs/<UTC-run-id>/`.
Nguồn `.ipynb` giữ gọn, không lưu output; mở bản trong thư mục kết quả nếu muốn xem output có sẵn.

## Dữ liệu và bằng chứng cần có

- Notebook 01/02: ảnh và `data/test_cases/ground_truth.json`. Đây là dữ liệu tổng hợp, không phải ảnh giao thông thật.
- Notebook 02: `models/LP_ocr.pt`; không tự tải model, không gọi 9Router. Thiếu ảnh/model sẽ báo lỗi thay vì ghi số liệu thay thế.
- Notebook 01 dùng thêm `data/recognition_regression/hardening_20261105/all_cases.json` nếu có; từng ảnh được kiểm tra SHA256. Bộ hồi quy có ảnh trùng với bộ tổng hợp và ba khung hình cùng xe.
- Notebook 03: ô cấu hình trỏ rõ tới các lượt benchmark/hồi quy đã lưu ngày 05/11/2026. Đổi các đường dẫn này khi muốn phân tích lượt khác. Bằng chứng trong `data/benchmarks` và `data/recognition_regression` không được Git theo dõi; bản clone mới cần dữ liệu này để chạy.
- Một số manifest có ảnh ở `D:/ảnh`; trên máy khác cần cung cấp đúng ảnh hoặc lập manifest di chuyển đường dẫn, giữ nguyên hash và nhãn đối chứng. Không sửa nhãn để khớp OCR.

Notebook 03 kiểm tra lại metric tổng hợp từ `predictions.json`, kiểm tra nhãn/hash trước–sau, giữ số lượng biển lặp và cách chia prefix/serial. Khi mã nguồn hiện tại khác hash của lượt lưu, kết quả được ghi là lịch sử.
Benchmark offline, handler local và Brave/hybrid có phạm vi khác nhau; không gộp độ chính xác/độ trễ. Thiếu `after_ui/results.json` được ghi **chưa xác minh Brave sau sửa**.

Notebook hỗ trợ phân tích; kiểm thử tự động trong `tests/` và kiểm thử trực tiếp trên web vẫn là các bước riêng.
