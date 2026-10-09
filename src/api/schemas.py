from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DetectionResult(BaseModel):
    plate_number: str
    confidence: float
    plate_type: str
    bbox: List[int]
    cropped_image_url: Optional[str] = None
    annotated_image_url: Optional[str] = None
    is_valid_format: bool

class PlateDetectionResponse(BaseModel):
    success: bool
    message: str
    total_detected: int
    processing_time_ms: float
    results: List[DetectionResult]

class DetectionHistoryItem(BaseModel):
    id: int
    plate_number: str
    confidence: float
    plate_type: str
    created_at: datetime
    image_url: Optional[str] = None
    cropped_plate_url: Optional[str] = None

class DetectionHistoryResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[DetectionHistoryItem]
