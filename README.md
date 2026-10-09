# Hệ Thống Nhận Diện Và Nhận Dạng Biển Số Xe (ALPR)
> Automatic License Plate Recognition System cho biển số xe Việt Nam.

---

## 📌 1. Giới thiệu dự án
Dự án được xây dựng bởi nhóm 5 người, áp dụng mô hình Deep Learning kết hợp Computer Vision và Web Application:
- **Phát hiện biển số:** YOLOv8 / YOLOv11 (PyTorch).
- **Nhận dạng ký tự:** PaddleOCR / EasyOCR kết hợp OpenCV (xử lý biển 1 dòng & 2 dòng, nắn góc nghiêng, chuẩn hóa biển số Việt Nam).
- **Backend & Database:** FastAPI bất đồng bộ, PostgreSQL.
- **Frontend Dashboard:** Next.js, TailwindCSS, shadcn/ui.

---

## 📁 2. Cấu trúc thư mục dự án

`	ext
license_plate_recognition/
├── data/                           # Dữ liệu
│   ├── raw/                        # Ảnh thô thu thập ban đầu
│   ├── test_cases/                 # Các ca kiểm thử (mờ, tối, nghiêng, che khuất)
│   └── outputs/                    # Ảnh crop biển số & ảnh kết quả nhận diện
│       ├── cropped_plates/
│       └── final_results/
├── docs/                           # Tài liệu báo cáo, slide thuyết trình
│   ├── figures/
│   ├── presentation/
│   └── report.docx
├── models/                         # Trọng số mô hình đã huấn luyện
│   └── weights_readme.txt          # Hướng dẫn đặt file best.pt
├── notebooks/                      # Thử nghiệm Jupyter Notebook
│   ├── 01_data_exploration.ipynb
│   ├── 02_preprocessing_experiments.ipynb
│   └── 03_evaluation_metrics.ipynb
├── src/                            # Mã nguồn chính của hệ thống
│   ├── api/                        # FastAPI routes & schemas
│   │   ├── routes.py               # Endpoints: /detect, /history, /search, /{id}
│   │   └── schemas.py              # Pydantic schemas validate request/response
│   ├── core/                       # Lõi AI Pipeline
│   │   ├── detector.py             # YOLO detector (phát hiện & crop biển số)
│   │   ├── preprocessor.py         # Nắn thẳng góc nghiêng, phân loại & tách biển 2 dòng
│   │   ├── ocr_engine.py           # PaddleOCR / EasyOCR nhận diện ký tự
│   │   └── postprocessor.py        # Sửa lỗi quang học & Regex chuẩn biển số VN
│   ├── utils/                      # Tiện ích bổ trợ (Logger, Visualizer)
│   └── config.py                   # Cấu hình hệ thống & biến môi trường
├── .env.example                    # File cấu hình môi trường mẫu
├── .gitignore                      # Cấu hình bỏ qua file rác, checkpoints, venv
├── requirements.txt                # Danh sách thư viện Python cần thiết
├── app.py                          # Entrypoint tương thích
├── main.py                         # Entrypoint chính khởi chạy FastAPI Server
└── README.md                       # Tài liệu hướng dẫn dự án
`

---

## 🚀 3. Hướng dẫn cài đặt & Khởi chạy

### 3.1. Cài đặt môi trường Python
`ash
# Tạo môi trường ảo (khuyến nghị Python 3.10 - 3.12)
python -m venv venv

# Kích hoạt môi trường (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Cài đặt các thư viện cần thiết
pip install -r requirements.txt
`

### 3.2. Cấu hình biến môi trường
Tạo file .env từ file mẫu:
`ash
copy .env.example .env
`

### 3.3. Đặt weights mô hình
Sau khi huấn luyện xong mô hình YOLO, đặt file trọng số est.pt vào thư mục:
`	ext
models/best.pt
`

### 3.4. Khởi chạy Backend API
`ash
python main.py
`
- Swagger API Docs: http://localhost:8000/docs
- Redoc API Docs: http://localhost:8000/redoc

---

## 🔌 4. Danh mục API chính

| Phương thức | Endpoint | Chức năng |
| :--- | :--- | :--- |
| POST | /api/license-plates/detect | Upload ảnh phương tiện và nhận diện biển số |
| GET | /api/license-plates/history | Lấy danh sách lịch sử nhận diện (hỗ trợ phân trang) |
| GET | /api/license-plates/search?plate=... | Tìm kiếm theo biển số xe |
| GET | /api/license-plates/:id | Xem chi tiết một lượt nhận diện theo ID |
