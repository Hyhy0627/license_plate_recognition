"""Compose and expose the FastAPI application."""

from fastapi import FastAPI
import uvicorn

from src.api.auth import router as auth_router
from src.api.error_handlers import configure_error_handlers
from src.api.health_routes import router as health_router
from src.api.lifespan import lifespan
from src.api.media_routes import router as media_router
from src.api.middlewares import configure_middlewares
from src.api.routes import router as plate_router
from src.api.video_routes import router as video_router
from src.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        description="Hệ thống nhận diện và nhận dạng biển số xe (Automatic License Plate Recognition - ALPR)",
        lifespan=lifespan,
    )
    configure_error_handlers(app)
    configure_middlewares(app)
    app.include_router(media_router)
    app.include_router(plate_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(video_router, prefix="/api")
    app.include_router(health_router)
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
