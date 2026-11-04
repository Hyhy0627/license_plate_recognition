import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "Automatic License Plate Recognition System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # AI Paths & OCR
    YOLO_MODEL_PATH: str = str(BASE_DIR / "models" / "best.pt")
    OCR_ENGINE: str = "hybrid"  # hybrid | yolo | 9router | paddleocr | easyocr
    CONFIDENCE_THRESHOLD: float = 0.5
    
    # 9Router Vision API Settings
    NINEROUTER_BASE_URL: str = "http://localhost:20128/v1"
    NINEROUTER_API_KEY: str = "sk-61f55deb9d48b9e9-nh78ky-98700cc2"
    NINEROUTER_MODEL: str = "ag/gemini-3.8-flash"
    NINEROUTER_TIMEOUT: float = 6.0
    
    # Storage
    OUTPUT_DIR: str = str(BASE_DIR / "data" / "outputs")
    CROPPED_PLATES_DIR: str = str(BASE_DIR / "data" / "outputs" / "cropped_plates")
    FINAL_RESULTS_DIR: str = str(BASE_DIR / "data" / "outputs" / "final_results")
    
    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR.as_posix()}/data/alpr.db"
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Ensure necessary directories exist
os.makedirs(settings.CROPPED_PLATES_DIR, exist_ok=True)
os.makedirs(settings.FINAL_RESULTS_DIR, exist_ok=True)
