# ==========================================
# Dockerfile cho Backend ALPR System (FastAPI)
# Sử dụng bản PyTorch CPU; kích thước image phụ thuộc dependencies.
# ==========================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết cho OpenCV và xử lý ảnh
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt PyTorch CPU
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Cài đặt các dependencies còn lại
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy mã nguồn backend
COPY main.py .
COPY src/ src/
COPY scripts/run_worker.py scripts/run_worker.py

# Tạo các thư mục cần thiết
RUN mkdir -p data/outputs data/video_jobs models

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
