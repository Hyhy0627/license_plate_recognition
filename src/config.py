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
    
    # AI Paths
    YOLO_MODEL_PATH: str = str(BASE_DIR / "models" / "best.pt")
    OCR_ENGINE: str = "paddleocr"  # paddleocr or easyocr
    CONFIDENCE_THRESHOLD: float = 0.5
    
    # Storage
    OUTPUT_DIR: str = str(BASE_DIR / "data" / "outputs")
    CROPPED_PLATES_DIR: str = str(BASE_DIR / "data" / "outputs" / "cropped_plates")
    FINAL_RESULTS_DIR: str = str(BASE_DIR / "data" / "outputs" / "final_results")
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/alpr_db"
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Ensure necessary directories exist
os.makedirs(settings.CROPPED_PLATES_DIR, exist_ok=True)
os.makedirs(settings.FINAL_RESULTS_DIR, exist_ok=True)
