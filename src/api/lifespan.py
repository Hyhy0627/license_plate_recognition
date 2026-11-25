"""Initialize local storage, database schema and recognition models."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from src.config import settings
from src.db.migrations import initialize_database
from src.db.session import engine
from src.services import model_runtime
from src.services.storage import get_storage
from src.utils.logger import logger


def initialize_services():
    if settings.STORAGE_BACKEND == "local":
        Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    else:
        get_storage()
    initialize_database(engine)
    logger.info("Database initialized.")


def preload_models():
    logger.info("Initializing ALPR System...")
    import torch

    torch.set_num_threads(max(1, settings.INFERENCE_THREADS))
    logger.info(f"Model Path: {settings.YOLO_MODEL_PATH}")
    logger.info(f"OCR Engine: {settings.OCR_ENGINE}")
    try:
        detector = model_runtime.get_detector()
        if detector.model is None:
            raise RuntimeError(f"Không nạp được model phát hiện biển số: {settings.YOLO_MODEL_PATH}")

        ocr_engine = model_runtime.get_ocr_engine()
        if not model_runtime.ocr_model_loaded(ocr_engine):
            raise RuntimeError("Không nạp được model OCR: kiểm tra OCR_MODEL_PATH hoặc cấu hình CCT ONNX.")

        logger.info("ALPR Models preloaded successfully into memory.")
    except Exception as exc:
        logger.error(f"ALPR startup failed while loading required models: {exc}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    if (settings.INFERENCE_WORKER_URL or settings.SESSION_BACKEND == "redis") and not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL là bắt buộc khi dùng worker riêng hoặc phiên Redis.")
    initialize_services()
    if not settings.INFERENCE_WORKER_URL:
        preload_models()
    yield
    logger.info("Shutting down ALPR System...")
