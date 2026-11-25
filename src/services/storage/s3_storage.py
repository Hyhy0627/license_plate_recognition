"""Private media storage on AWS S3 or a compatible service such as MinIO."""

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile
from uuid import uuid4

import cv2
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError

from src.core.exceptions import ServiceUnavailableException
from src.services.storage.base import IStorageService, RemoteFile, VIDEO_CATEGORY, VIDEO_TYPES, copy_video, storage_key


class S3Storage(IStorageService):
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def _call(self, method, key, *, missing_ok=False, **options):
        try:
            return method(Bucket=self.bucket, Key=key, **options)
        except ClientError as exc:
            if missing_ok and exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise ServiceUnavailableException("Không truy cập được kho lưu trữ.") from exc
        except (BotoCoreError, S3UploadFailedError) as exc:
            raise ServiceUnavailableException("Không truy cập được kho lưu trữ.") from exc

    def save_image(self, category, filename, image):
        key = storage_key(category, filename)
        encoded, jpeg = cv2.imencode(".jpg", image)
        if not encoded:
            raise OSError("Could not encode the recognition image")
        self._call(self.client.put_object, key, Body=jpeg.tobytes(), ContentType="image/jpeg")

    def save_video(self, filename, source, *, max_bytes):
        key = storage_key(VIDEO_CATEGORY, filename)
        with TemporaryFile() as target:
            copy_video(source, target, max_bytes)
            target.seek(0)
            self._call(self.client.upload_fileobj, key, Fileobj=target,
                       ExtraArgs={"ContentType": VIDEO_TYPES[Path(filename).suffix]})

    def delete_file(self, category, filename):
        self._call(self.client.delete_object, storage_key(category, filename))

    def get_file(self, category, filename):
        key = storage_key(category, filename)
        metadata = self._call(self.client.head_object, key, missing_ok=True)

        def open_body(byte_range):
            options = {"Range": byte_range} if byte_range else {}
            return self._call(self.client.get_object, key, missing_ok=True, **options)["Body"]

        return RemoteFile(metadata["ContentLength"], metadata["ETag"], metadata["LastModified"], open_body)

    @contextmanager
    def video_file(self, filename):
        key = storage_key(VIDEO_CATEGORY, filename)
        with TemporaryDirectory(prefix="alpr-video-") as directory:
            path = Path(directory) / filename
            self._call(self.client.download_file, key, missing_ok=True, Filename=str(path))
            yield path

    def presigned_url(self, category, filename, *, expires_in=300):
        if not 1 <= expires_in <= 604800:
            raise ValueError("Presigned URLs must expire within 1 to 604800 seconds")
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": storage_key(category, filename)},
            ExpiresIn=expires_in,
        )

    def check_writable(self):
        key = f".health/{uuid4().hex}"
        try:
            self._call(self.client.put_object, key, Body=b"1")
            self._call(self.client.delete_object, key)
        except ServiceUnavailableException:
            return False
        return True
