import os
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.models.registry import PROJECT_ROOT, default_path

BASE_DIR = PROJECT_ROOT

class Settings(BaseSettings):
    APP_NAME: str = "Automatic License Plate Recognition System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # AI Paths & OCR
    MODEL_RUNTIME: Literal["local"] = "local"
    YOLO_MODEL_PATH: str = str(default_path("image-detector"))
    OCR_MODEL_PATH: str = str(default_path("image-ocr"))
    VEHICLE_MODEL_PATH: str = str(default_path("vehicle-detector"))
    VIDEO_ENGINE: str = "onnx"  # onnx | legacy
    VIDEO_PLATE_MODEL_PATH: str = str(default_path("video-detector"))
    VIDEO_OCR_MODEL_PATH: str = str(default_path("sequence-ocr"))
    VIDEO_OCR_CONFIG_PATH: str = str(default_path("sequence-config"))
    VIDEO_OCR_MIN_CONFIDENCE: float = 0.7
    OCR_ENGINE: str = "hybrid"  # hybrid | fastplate | yolo | onnx | cct | 9router | paddleocr | easyocr
    CONFIDENCE_THRESHOLD: float = 0.5
    INFERENCE_THREADS: int = 2
    INFERENCE_WORKER_URL: str = ""
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_SESSION_DAYS: int = 7
    SESSION_BACKEND: Literal["database", "redis"] = "database"
    
    # 9Router Vision API Settings
    NINEROUTER_BASE_URL: str = "http://localhost:20128/v1"
    NINEROUTER_API_KEY: str = ""
    NINEROUTER_MODEL: str = "ag/gemini-3.8-flash"
    NINEROUTER_TIMEOUT: float = 6.0
    VIDEO_NINEROUTER_TIMEOUT: float = 10.0
    
    # Storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    OUTPUT_DIR: str = str(BASE_DIR / "data" / "outputs")
    CROPPED_PLATES_DIR: str = str(BASE_DIR / "data" / "outputs" / "cropped_plates")
    FINAL_RESULTS_DIR: str = str(BASE_DIR / "data" / "outputs" / "final_results")
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    S3_SESSION_TOKEN: SecretStr = SecretStr("")
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR.as_posix()}/data/alpr.db"
    DB_POOL_SIZE: int = Field(default=5, gt=0)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0)

    # Redis is optional for local development.
    REDIS_URL: str = ""
    REDIS_NAMESPACE: str = Field(default="alpr", pattern=r"^[a-zA-Z0-9_.-]{1,64}$")
    REDIS_JOB_RECLAIM_SECONDS: int = Field(default=60, ge=1)
    
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()

if settings.STORAGE_BACKEND == "local":
    os.makedirs(settings.CROPPED_PLATES_DIR, exist_ok=True)
    os.makedirs(settings.FINAL_RESULTS_DIR, exist_ok=True)
