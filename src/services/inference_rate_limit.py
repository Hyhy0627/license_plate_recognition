"""Per-user admission limits for costly inference requests."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
import secrets

from redis.exceptions import RedisError

from src.config import settings
from src.core.exceptions import RateLimitExceededException, ServiceUnavailableException
from src.services.authentication import _SLIDING_WINDOW
from src.services.redis_runtime import redis_client


LIMITS = {"image": (20, 60), "video": (3, 300)}


class InferenceRateLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()
        self._redis = redis_client(settings.REDIS_URL) if settings.REDIS_URL else None
        self._script = self._redis.register_script(_SLIDING_WINDOW) if self._redis else None

    def check(self, kind: str, user_id: int):
        limit, window = LIMITS[kind]
        # User identity remains stable behind a reverse proxy. Nginx applies
        # the separate client-IP limit at the network edge.
        keys = (f"{kind}:user:{user_id}",)
        if self._script:
            names = [f"{{{settings.REDIS_NAMESPACE}}}:inference:{key}" for key in keys]
            try:
                allowed = self._script(
                    keys=names, args=[window * 1000, secrets.token_hex(16), limit])
            except RedisError as exc:
                raise ServiceUnavailableException("Tạm thời không thể kiểm tra giới hạn suy luận.") from exc
            if not allowed:
                raise RateLimitExceededException("Đã vượt giới hạn xử lý. Vui lòng thử lại sau.",
                                                 retry_after=window)
            return

        now = monotonic()
        with self._lock:
            for key in keys:
                events = self._events[key]
                while events and events[0] <= now - window:
                    events.popleft()
            if any(len(self._events[key]) >= limit for key in keys):
                raise RateLimitExceededException("Đã vượt giới hạn xử lý. Vui lòng thử lại sau.",
                                                 retry_after=window)
            for key in keys:
                self._events[key].append(now)


inference_rate_limiter = InferenceRateLimiter()
