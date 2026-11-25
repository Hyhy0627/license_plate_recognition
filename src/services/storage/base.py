"""Storage contract and media identifiers shared by the local and S3 adapters."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Callable, Protocol

import numpy as np

from src.core.exceptions import InvalidPayloadException, PayloadTooLargeException


IMAGE_CATEGORIES = {"cropped_plates", "final_results"}
VIDEO_CATEGORY = "video_jobs"
VIDEO_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo", ".webm": "video/webm"}


def storage_key(category: str, filename: str) -> str:
    if category not in IMAGE_CATEGORIES and category != VIDEO_CATEGORY:
        raise ValueError("Unknown media category")
    if filename in {"", ".", ".."} or any(character in filename for character in "/\\:\0"):
        raise ValueError("Expected a single media filename")
    return f"{category}/{filename}"


def copy_video(source: BinaryIO, target: BinaryIO, max_bytes: int) -> None:
    size = 0
    while chunk := source.read(1024 * 1024):
        size += len(chunk)
        if size > max_bytes:
            raise PayloadTooLargeException("Video vượt quá 100 MB.")
        target.write(chunk)
    if not size:
        raise InvalidPayloadException("Video rỗng.")


@dataclass(frozen=True)
class RemoteFile:
    size: int
    etag: str
    last_modified: datetime
    open: Callable[[str | None], BinaryIO]


class IStorageService(Protocol):
    def save_image(self, category: str, filename: str, image: np.ndarray) -> None:
        ...

    def get_image_url(self, category: str, filename: str) -> str:
        if category not in IMAGE_CATEGORIES:
            raise ValueError("Expected an image category")
        return f"/static/{storage_key(category, filename)}"

    def save_video(self, filename: str, source: BinaryIO, *, max_bytes: int) -> None:
        ...

    def delete_file(self, category: str, filename: str) -> None:
        ...

    def get_file(self, category: str, filename: str) -> Path | RemoteFile:
        ...

    def video_file(self, filename: str) -> AbstractContextManager[Path]:
        ...

    def check_writable(self) -> bool:
        ...
