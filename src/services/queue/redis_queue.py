"""Redis Stream tasks with idempotent publication and recoverable delivery."""

from dataclasses import dataclass

from redis import Redis
from redis.exceptions import RedisError, ResponseError

from src.core.exceptions import ServiceUnavailableException
from src.services.queue.base import QueueStatus, VideoTask


_ENQUEUE = """
local existing = redis.call('HGET', KEYS[2], ARGV[1])
if existing then return existing end
local entry = redis.call('XADD', KEYS[1], '*', 'job_id', ARGV[1])
redis.call('HSET', KEYS[2], ARGV[1], entry)
return entry
"""

_STATUS = """
local entry = redis.call('HGET', KEYS[2], ARGV[1])
if not entry then return false end
local pending = redis.pcall('XPENDING', KEYS[1], ARGV[2], entry, entry, 1)
if pending.err then
    if string.find(pending.err, 'NOGROUP', 1, true) then return 'queued' end
    return pending
end
return #pending > 0 and 'running' or 'queued'
"""

_FINISH = """
local entry = ARGV[2]
local current = redis.call('HGET', KEYS[2], ARGV[1])
if entry == '' then
    if not current then return 0 end
    entry = current
end
redis.call('XDEL', KEYS[1], entry)
redis.pcall('XACK', KEYS[1], ARGV[3], entry)
if current == entry then redis.call('HDEL', KEYS[2], ARGV[1]) end
return 1
"""


@dataclass(frozen=True)
class Delivery:
    entry_id: str
    job_id: str


class RedisTaskQueue:
    group = "video-workers"

    def __init__(self, client: Redis, namespace: str, reclaim_seconds: int):
        self.client = client
        self.keys = (f"{{{namespace}}}:video:tasks", f"{{{namespace}}}:video:scheduled")
        self.reclaim_ms = 1000 * reclaim_seconds
        self._claim_cursor = "0-0"

    def _eval(self, script, *args):
        try:
            return self.client.eval(script, len(self.keys), *self.keys, *args)
        except RedisError as exc:
            raise ServiceUnavailableException("Hàng đợi video tạm thời không khả dụng.") from exc

    def enqueue_video_job(self, task: VideoTask) -> None:
        self._eval(_ENQUEUE, task.job_id)

    def get_job_status(self, job_id: str) -> QueueStatus | None:
        return self._eval(_STATUS, job_id, self.group)

    def cancel_job(self, job_id: str) -> bool:
        return bool(self._eval(_FINISH, job_id, "", self.group))

    def prepare_consumer(self):
        try:
            self.client.xgroup_create(self.keys[0], self.group, id="0-0", mkstream=True)
        except ResponseError as exc:
            if not str(exc).startswith("BUSYGROUP"):
                raise

    def read_job(self, consumer: str) -> Delivery | None:
        claimed = self.client.xautoclaim(
            self.keys[0], self.group, consumer, self.reclaim_ms, self._claim_cursor, count=1,
        )
        self._claim_cursor, entries = claimed[:2]
        if not entries:
            response = self.client.xreadgroup(self.group, consumer, {self.keys[0]: ">"}, count=1, block=1000)
            if not response:
                return None
            entries = response[0][1]
        entry, fields = entries[0]
        return Delivery(entry, fields.get("job_id", ""))

    def acknowledge(self, delivery: Delivery):
        self._eval(_FINISH, delivery.job_id, delivery.entry_id, self.group)
