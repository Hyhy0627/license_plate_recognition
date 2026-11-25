"""Local disk storage using the existing media directories and filenames."""

from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

import cv2

from src.services.storage.base import IStorageService, VIDEO_CATEGORY, copy_video, storage_key


@contextmanager
def _atomic_target(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=".upload-", suffix=path.suffix, delete=False) as file:
        temporary = Path(file.name)
    try:
        yield temporary
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class LocalStorage(IStorageService):
    def __init__(self, output_dir: Path, crops_dir: Path, results_dir: Path, video_dir: Path):
        self.output_dir = output_dir
        self.roots = {"cropped_plates": crops_dir, "final_results": results_dir, VIDEO_CATEGORY: video_dir}

    def _path(self, category, filename):
        storage_key(category, filename)
        root = self.roots[category].resolve()
        path = (root / filename).resolve()
        if not path.is_relative_to(root):
            raise FileNotFoundError(filename)
        return path

    def save_image(self, category, filename, image):
        with _atomic_target(self._path(category, filename)) as destination:
            if not cv2.imwrite(str(destination), image):
                raise OSError("Could not write the recognition image")

    def save_video(self, filename, source, *, max_bytes):
        with _atomic_target(self._path(VIDEO_CATEGORY, filename)) as destination:
            with destination.open("wb") as target:
                copy_video(source, target, max_bytes)

    def delete_file(self, category, filename):
        self._path(category, filename).unlink(missing_ok=True)

    def get_file(self, category, filename):
        path = self._path(category, filename)
        if not path.is_file():
            raise FileNotFoundError(filename)
        return path

    @contextmanager
    def video_file(self, filename):
        yield self.get_file(VIDEO_CATEGORY, filename)

    def check_writable(self):
        try:
            with NamedTemporaryFile(dir=self.output_dir, prefix=".health-") as probe:
                probe.write(b"1")
                probe.flush()
        except OSError:
            return False
        return True
