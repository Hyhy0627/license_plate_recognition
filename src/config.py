import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "Automatic License Plate Recognition System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # AI Paths & OCR
    YOLO_MODEL_PATH: str = str(BASE_DIR / "models" / "best.pt")
    VEHICLE_MODEL_PATH: str = str(BASE_DIR / "models" / "yolov8n.pt")
    VIDEO_ENGINE: str = "onnx"  # onnx | legacy
    VIDEO_PLATE_MODEL_PATH: str = str(BASE_DIR / "models/video/DetectLisence_YOLO11.pt")
    VIDEO_OCR_MODEL_PATH: str = str(BASE_DIR / "models/video/cct_s_v1_vn.onnx")
    VIDEO_OCR_CONFIG_PATH: str = str(BASE_DIR / "models/video/cct_s_v1_vn_plate_config.yaml")
    VIDEO_OCR_MIN_CONFIDENCE: float = 0.7
    OCR_ENGINE: str = "hybrid"  # hybrid | fastplate | yolo | onnx | cct | 9router | paddleocr | easyocr
    CONFIDENCE_THRESHOLD: float = 0.5
    INFERENCE_THREADS: int = 2
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_SESSION_DAYS: int = 7
    
    # 9Router Vision API Settings
    NINEROUTER_BASE_URL: str = "http://localhost:20128/v1"
    NINEROUTER_API_KEY: str = ""
    NINEROUTER_MODEL: str = "ag/gemini-3.8-flash"
    NINEROUTER_TIMEOUT: float = 6.0
    VIDEO_NINEROUTER_TIMEOUT: float = 10.0
    
    # Storage
    OUTPUT_DIR: str = str(BASE_DIR / "data" / "outputs")
    CROPPED_PLATES_DIR: str = str(BASE_DIR / "data" / "outputs" / "cropped_plates")
    FINAL_RESULTS_DIR: str = str(BASE_DIR / "data" / "outputs" / "final_results")
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR.as_posix()}/data/alpr.db"
    
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()

# Ensure necessary directories exist
os.makedirs(settings.CROPPED_PLATES_DIR, exist_ok=True)
os.makedirs(settings.FINAL_RESULTS_DIR, exist_ok=True)
