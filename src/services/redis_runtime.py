"""Redis client shared by the task broker and authentication rate limiter."""

from functools import lru_cache

from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry


@lru_cache(maxsize=1)
def redis_client(url: str) -> Redis:
    return Redis.from_url(
        url, decode_responses=True, socket_connect_timeout=3, socket_timeout=5,
        retry=Retry(NoBackoff(), 0), health_check_interval=30,
    )
