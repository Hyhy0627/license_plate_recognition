from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config import settings

# Cấu hình engine kết nối SQLite (check_same_thread=False cần thiết cho FastAPI multi-threading)
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    FastAPI dependency cung cấp database session trên mỗi request
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

