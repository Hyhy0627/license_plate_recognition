"""Public status and runtime readiness checks."""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.db.session import engine
from src.infrastructure.inference_worker import worker_ready
from src.services import model_runtime
from src.services.redis_runtime import redis_client
from src.services.storage import get_storage


router = APIRouter()


@router.get("/", tags=["Health Check"])
def root():
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "docs_url": "/docs",
    }


@router.get("/api/health", include_in_schema=False)
def deep_health():
    try:
        with engine.connect() as connection:
            connected = connection.scalar(text("SELECT 1")) == 1
    except SQLAlchemyError:
        connected = False
    writable = get_storage().check_writable()
    loaded = worker_ready() if settings.INFERENCE_WORKER_URL else model_runtime.image_models_loaded()
    redis_ready = True
    if settings.REDIS_URL:
        try:
            redis_ready = redis_client(settings.REDIS_URL).ping()
        except RedisError:
            redis_ready = False
    healthy = connected and loaded and writable and redis_ready
    return JSONResponse({
        "status": "healthy" if healthy else "unhealthy",
        "database": "connected" if connected else "unavailable",
        "models_loaded": loaded,
        "output_writable": writable,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, status_code=200 if healthy else 503)
