from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import settings


def build_engine(database_url):
    url = make_url(database_url)
    dialect = url.get_backend_name()
    if dialect == "sqlite":
        options = {"connect_args": {"check_same_thread": False}}
        if url.database in {None, "", ":memory:"} or url.query.get("mode") == "memory":
            options["poolclass"] = StaticPool
        return create_engine(url, **options)
    if dialect == "postgresql":
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg2")
        return create_engine(
            url, pool_size=settings.DB_POOL_SIZE, max_overflow=settings.DB_MAX_OVERFLOW, pool_pre_ping=True,
        )
    raise ValueError("DATABASE_URL phải dùng sqlite hoặc postgresql.")


engine = build_engine(settings.DATABASE_URL)
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

