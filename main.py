from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pathlib import Path
from sqlalchemy.orm import Session
import uvicorn
import os

from src.config import settings
from src.api.routes import router as plate_router
from src.utils.logger import logger
from src.db.session import engine, Base
import src.db.models
from src.db.models import PlateHistory, User
from src.db.session import get_db
from src.db.migrations import initialize_database
from src.api.auth import router as auth_router, get_current_user

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng SQL nếu chưa tồn tại
    initialize_database(engine)
    logger.info(f"Database initialized: {settings.DATABASE_URL}")
    
    # Khởi động hệ thống: preload weights model vào RAM/GPU một lần duy nhất
    logger.info("Initializing ALPR System...")
    import torch
    torch.set_num_threads(max(1, settings.INFERENCE_THREADS))
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


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Do not echo submitted passwords in Pydantic's default `input` error field.
    return JSONResponse(status_code=422, content={
        "detail": "Thông tin chưa hợp lệ. Kiểm tra email, tên (2–60 ký tự) và mật khẩu (8–128 ký tự khi đăng ký)."
        if request.url.path.startswith("/api/auth/") else "Dữ liệu yêu cầu không hợp lệ.",
        "fields": [str(error["loc"][-1]) for error in exc.errors()],
    })

# Cấu hình CORS cho phép Frontend Next.js gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount thư mục lưu trữ ảnh static (ảnh crop & ảnh kết quả)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

@app.middleware("http")
async def protect_browser_requests(request: Request, call_next):
    # CORS alone does not prevent cross-site form submissions using cookies.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        allowed = {value.strip() for value in settings.CORS_ORIGINS.split(",")}
        if origin and origin not in allowed:
            return JSONResponse(status_code=403, content={"detail": "Nguồn yêu cầu không được phép."})
    response = await call_next(request)
    if request.url.path.startswith(("/api/", "/static/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/static/{category}/{filename}", include_in_schema=False)
def private_result_image(category: str, filename: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if category not in {"cropped_plates", "final_results"} or Path(filename).name != filename or "\\" in filename:
        raise HTTPException(404, "Không tìm thấy ảnh.")
    url = f"/static/{category}/{filename}"
    field = PlateHistory.cropped_plate_url if category == "cropped_plates" else PlateHistory.annotated_image_url
    record = db.query(PlateHistory).filter(PlateHistory.owner_id == user.id, field == url).first()
    if record is None:
        raise HTTPException(404, "Không tìm thấy ảnh.")
    root = Path(settings.CROPPED_PLATES_DIR if category == "cropped_plates" else settings.FINAL_RESULTS_DIR).resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Không tìm thấy ảnh.")
    return FileResponse(path, headers={"Cache-Control": "no-store"})

# Đăng ký API router
app.include_router(plate_router, prefix="/api")
app.include_router(auth_router, prefix="/api")

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
