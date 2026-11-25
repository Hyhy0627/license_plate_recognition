"""Select storage using configuration without loading S3 dependencies in local mode."""

from functools import lru_cache
from pathlib import Path

from src.config import BASE_DIR, settings
from src.services.storage.base import IStorageService
from src.services.storage.local_storage import LocalStorage


@lru_cache(maxsize=1)
def _s3_storage() -> IStorageService:
    import boto3
    from botocore.config import Config

    from src.services.storage.s3_storage import S3Storage

    if not settings.S3_BUCKET:
        raise ValueError("S3_BUCKET là bắt buộc khi STORAGE_BACKEND=s3.")
    access_key = settings.S3_ACCESS_KEY_ID
    secret_key = settings.S3_SECRET_ACCESS_KEY.get_secret_value()
    token = settings.S3_SESSION_TOKEN.get_secret_value()
    if bool(access_key) != bool(secret_key) or (token and not access_key):
        raise ValueError("Cấu hình thông tin xác thực S3 chưa đầy đủ.")
    credentials = {}
    if access_key:
        credentials = {"aws_access_key_id": access_key, "aws_secret_access_key": secret_key,
                       "aws_session_token": token or None}
    client = boto3.client(
        "s3", region_name=settings.S3_REGION, endpoint_url=settings.S3_ENDPOINT_URL or None,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path" if settings.S3_ENDPOINT_URL else "auto"}),
        **credentials,
    )
    return S3Storage(client, settings.S3_BUCKET)


def get_storage(*, video_dir: Path | None = None) -> IStorageService:
    if settings.STORAGE_BACKEND == "s3":
        return _s3_storage()
    return LocalStorage(
        Path(settings.OUTPUT_DIR), Path(settings.CROPPED_PLATES_DIR), Path(settings.FINAL_RESULTS_DIR),
        video_dir if video_dir is not None else BASE_DIR / "data" / "video_jobs",
    )
