"""Transport contract for background video work."""

from dataclasses import dataclass
from typing import Callable, Literal, Protocol


QueueStatus = Literal["queued", "running"]


@dataclass(frozen=True)
class VideoTask:
    job_id: str
    # Only the in-process adapter receives callbacks. Redis stores the ID.
    run_local: Callable[[], None] | None = None
    cancel_local: Callable[[], None] | None = None


class ITaskQueue(Protocol):
    def enqueue_video_job(self, task: VideoTask) -> None:
        ...

    def get_job_status(self, job_id: str) -> QueueStatus | None:
        ...

    def cancel_job(self, job_id: str) -> bool:
        ...
