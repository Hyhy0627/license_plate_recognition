from contextlib import asynccontextmanager
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
from time import perf_counter
from uuid import uuid4
import re
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import uvicorn
import os

from src.config import settings
from src.core import exceptions
from src.services import model_runtime, result_media
from src.api.routes import router as plate_router
from src.utils.logger import logger
from src.db.session import engine
from src.db.models import User
from src.db.session import get_db
from src.db.migrations import initialize_database
from src.api.auth import router as auth_router, get_current_user
from src.api.video_routes import router as video_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng SQL nếu chưa tồn tại
    initialize_database(engine)
    logger.info("Database initialized.")
    
    # Khởi động hệ thống: preload weights model vào RAM/GPU một lần duy nhất
    logger.info("Initializing ALPR System...")
    import torch
    torch.set_num_threads(max(1, settings.INFERENCE_THREADS))
    logger.info(f"Model Path: {settings.YOLO_MODEL_PATH}")
    logger.info(f"OCR Engine: {settings.OCR_ENGINE}")
    try:
        from src.services.model_runtime import get_detector, get_ocr_engine
        detector = get_detector()
        if detector.model is None:
            raise RuntimeError(f"Không nạp được model phát hiện biển số: {settings.YOLO_MODEL_PATH}")

        ocr_engine = get_ocr_engine()
        if not model_runtime.ocr_model_loaded(ocr_engine):
            raise RuntimeError("Không nạp được model OCR: models/LP_ocr.pt hoặc CCT ONNX đã cấu hình")

        logger.info("ALPR Models preloaded successfully into memory.")
    except Exception as exc:
        logger.error(f"ALPR startup failed while loading required models: {exc}")
        raise
    yield
    logger.info("Shutting down ALPR System...")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Hệ thống nhận diện và nhận dạng biển số xe (Automatic License Plate Recognition - ALPR)",
    lifespan=lifespan
)


DOMAIN_STATUS = {
    exceptions.InvalidPayloadException: 400,
    exceptions.AuthenticationException: 401,
    exceptions.PermissionDeniedException: 403,
    exceptions.EntityNotFoundException: 404,
    exceptions.ResourceConflictException: 409,
    exceptions.PayloadTooLargeException: 413,
    exceptions.RateLimitExceededException: 429,
    exceptions.ServiceUnavailableException: 503,
}


@app.exception_handler(exceptions.ALPRDomainException)
async def domain_error(request: Request, exc: exceptions.ALPRDomainException):
    headers = {}
    if isinstance(exc, exceptions.RateLimitExceededException) and exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse({"detail": str(exc)}, status_code=DOMAIN_STATUS[type(exc)], headers=headers)


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
    expose_headers=["X-Request-ID", "X-Process-Time"],
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


def _trace_headers(request):
    elapsed_ms = (perf_counter() - request.state.started_at) * 1000
    return {"X-Request-ID": request.state.request_id, "X-Process-Time": f"{elapsed_ms:.3f}"}


@app.middleware("http")
async def trace_request(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request.state.request_id = supplied if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", supplied) else str(uuid4())
    request.state.started_at = perf_counter()
    with logger.contextualize(request_id=request.state.request_id):
        response = await call_next(request)
        response.headers.update(_trace_headers(request))
        logger.info("{} {} {}", request.method, request.scope.get("route", request.url).path, response.status_code)
        return response


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    with logger.contextualize(request_id=request.state.request_id):
        logger.error("Unhandled request error: {}", type(exc).__name__)
    return PlainTextResponse("Internal Server Error", status_code=500, headers=_trace_headers(request))


@app.get('/static/{category}/{filename}', include_in_schema=False)
def private_result_image(category: str, filename: str, user: User=Depends(get_current_user), db: Session=Depends(get_db)):
    path = result_media.private_result_image(category, filename, user, db)
    return FileResponse(path, headers={"Cache-Control": "no-store"})

# Đăng ký API router
app.include_router(plate_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(video_router, prefix="/api")

@app.get("/", tags=["Health Check"])
def root():
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "docs_url": "/docs"
    }

@app.get("/api/health", include_in_schema=False)
def deep_health():
    try:
        with engine.connect() as connection:
            connected = connection.scalar(text("SELECT 1")) == 1
    except SQLAlchemyError:
        connected = False
    try:
        with NamedTemporaryFile(dir=settings.OUTPUT_DIR, prefix=".health-") as probe:
            probe.write(b"1")
            probe.flush()
        writable = True
    except OSError:
        writable = False
    loaded = model_runtime.image_models_loaded()
    healthy = connected and loaded and writable
    return JSONResponse({
        "status": "healthy" if healthy else "unhealthy",
        "database": "connected" if connected else "unavailable",
        "models_loaded": loaded,
        "output_writable": writable,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, status_code=200 if healthy else 503)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
