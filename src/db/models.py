from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from src.db.session import Base

class PlateHistory(Base):
    """
    Bảng lưu trữ lịch sử nhận diện biển số xe (SQL).
    """
    __tablename__ = "plate_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
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


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(60), nullable=False)
    email = Column(String(254), nullable=False, unique=True, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class UserSession(Base):
    __tablename__ = "user_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    id = Column(Integer, primary_key=True)
    key = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, index=True)
