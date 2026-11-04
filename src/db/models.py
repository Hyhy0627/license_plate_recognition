from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from src.db.session import Base

class PlateHistory(Base):
    """
    Bảng lưu trữ lịch sử nhận diện biển số xe (SQL).
    """
    __tablename__ = "plate_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    plate_number = Column(String(50), index=True, nullable=False)
    confidence = Column(Float, nullable=False)
    plate_type = Column(String(50), nullable=True)  # one_line hoặc two_line
    engine_used = Column(String(50), nullable=True, default="local_yolo") # local_yolo hoặc 9router_vision
    cropped_plate_url = Column(String(255), nullable=True)
    annotated_image_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "plate_number": self.plate_number,
            "confidence": round(self.confidence, 4),
            "plate_type": self.plate_type or "unknown",
            "engine_used": self.engine_used or "local_yolo",
            "cropped_plate_url": self.cropped_plate_url,
            "annotated_image_url": self.annotated_image_url,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }
