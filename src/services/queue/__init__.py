"""Bind the configured background transport."""

from functools import lru_cache

from src.config import settings
from src.services.queue.base import ITaskQueue
from src.services.queue.in_memory_queue import InMemoryTaskQueue
from src.services.queue.redis_queue import RedisTaskQueue
from src.services.redis_runtime import redis_client


@lru_cache(maxsize=1)
def get_local_task_queue() -> InMemoryTaskQueue:
    return InMemoryTaskQueue()


@lru_cache(maxsize=1)
def _redis_queue(url: str, namespace: str, reclaim_seconds: int) -> RedisTaskQueue:
    return RedisTaskQueue(redis_client(url), namespace, reclaim_seconds)


def get_redis_task_queue() -> RedisTaskQueue:
    return _redis_queue(settings.REDIS_URL, settings.REDIS_NAMESPACE, settings.REDIS_JOB_RECLAIM_SECONDS)


def get_task_queue() -> ITaskQueue:
    return get_redis_task_queue() if settings.REDIS_URL else get_local_task_queue()
