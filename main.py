from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os

from src.config import settings
from src.api.routes import router as plate_router
from src.utils.logger import logger
from src.db.session import engine, Base
import src.db.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng SQL nếu chưa tồn tại
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized: {settings.DATABASE_URL}")
    
    # Khởi động hệ thống: preload weights model vào RAM/GPU một lần duy nhất
    logger.info("Initializing ALPR System...")
    logger.info(f"Model Path: {settings.YOLO_MODEL_PATH}")
    logger.info(f"OCR Engine: {settings.OCR_ENGINE}")
    try:
        from src.api.routes import get_detector, get_ocr_engine
        get_detector()
        get_ocr_engine()
        logger.info("ALPR Models preloaded successfully into memory.")
    except Exception as e:
        logger.error(f"Error preloading models: {e}")
    yield
    logger.info("Shutting down ALPR System...")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Hệ thống nhận diện và nhận dạng biển số xe (Automatic License Plate Recognition - ALPR)",
    lifespan=lifespan
)

# Cấu hình CORS cho phép Frontend Next.js gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount thư mục lưu trữ ảnh static (ảnh crop & ảnh kết quả)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.OUTPUT_DIR), name="static")

# Đăng ký API router
app.include_router(plate_router, prefix="/api")

@app.get("/", tags=["Health Check"])
def root():
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
