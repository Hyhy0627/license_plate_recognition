"""Private image HTTP service and durable Redis video consumer."""

from contextlib import asynccontextmanager
from threading import Event, Thread
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
import uvicorn

from src.api.error_handlers import configure_error_handlers
from src.api.health_routes import router as health_router
from src.api.lifespan import initialize_services, preload_models
from src.api.middlewares import configure_middlewares
from src.api.routes import image_router
from src.config import settings
from src.core.exceptions import ServiceUnavailableException
from src.core.models.registry import resolve_path
from src.services.model_runtime import get_video_engines
from src.services.queue import get_redis_task_queue
from src.services.queue.base import VideoTask
from src.services.video_jobs import redis_video_jobs, run_redis_video_job
from src.utils.logger import logger


def consume_video(queue, stop: Event):
    consumer = uuid4().hex
    next_reconcile = 0
    while not stop.is_set():
        try:
            if monotonic() >= next_reconcile:
                queue.prepare_consumer()
                for job_id in redis_video_jobs():
                    queue.enqueue_video_job(VideoTask(job_id))
                next_reconcile = monotonic() + 5
            delivery = queue.read_job(consumer)
            if delivery is not None and run_redis_video_job(delivery.job_id):
                queue.acknowledge(delivery)
        except (RedisError, SQLAlchemyError, ServiceUnavailableException) as exc:
            logger.warning("Video consumer will retry after {}.", type(exc).__name__)
            next_reconcile = 0
            stop.wait(2)


@asynccontextmanager
async def lifespan(_app):
    if not settings.REDIS_URL or settings.INFERENCE_WORKER_URL:
        raise RuntimeError("Worker yêu cầu REDIS_URL và INFERENCE_WORKER_URL để trống.")
    initialize_services()
    preload_models()
    if not resolve_path(settings.VEHICLE_MODEL_PATH).is_file():
        raise RuntimeError("Worker thiếu VEHICLE_MODEL_PATH.")
    get_video_engines()
    queue = get_redis_task_queue()
    queue.prepare_consumer()
    stop = Event()
    worker = Thread(target=consume_video, args=(queue, stop), name="redis-video-worker")
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
configure_error_handlers(app)
configure_middlewares(app)
app.include_router(image_router, prefix="/api/license-plates")
app.include_router(health_router)


if __name__ == "__main__":
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
