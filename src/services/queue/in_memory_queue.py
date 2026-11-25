"""Single-threaded background execution for local development."""

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from src.services.queue.base import QueueStatus, VideoTask


class InMemoryTaskQueue:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-tracking")
        self._futures = {}
        self._lock = Lock()

    def enqueue_video_job(self, task: VideoTask) -> None:
        if task.run_local is None:
            raise ValueError("A local video task requires a callable.")
        with self._lock:
            if task.job_id in self._futures:
                return
            future = self._executor.submit(task.run_local)
            self._futures[task.job_id] = future

        def forget(done):
            with self._lock:
                self._futures.pop(task.job_id, None)
            if done.cancelled() and task.cancel_local is not None:
                task.cancel_local()

        future.add_done_callback(forget)

    def get_job_status(self, job_id: str) -> QueueStatus | None:
        with self._lock:
            future = self._futures.get(job_id)
            if future is None or future.done():
                return None
            return "running" if future.running() else "queued"

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            future = self._futures.get(job_id)
        return future is not None and future.cancel()
