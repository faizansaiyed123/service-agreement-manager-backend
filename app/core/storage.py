from hashlib import sha256
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings


class StorageLimitExceeded(ValueError):
    pass


class LocalStorage:
    def __init__(self, root: str, max_file_bytes: int) -> None:
        self.root = Path(root).resolve()
        self.max_file_bytes = max_file_bytes

    def save_stream(self, source: BinaryIO, storage_key: str) -> tuple[int, str]:
        destination = self._path(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        digest = sha256()
        size = 0
        try:
            with temporary.open("wb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_file_bytes:
                        raise StorageLimitExceeded(f"File exceeds the {self.max_file_bytes} byte storage limit")
                    digest.update(chunk)
                    target.write(chunk)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return size, digest.hexdigest()

    def _path(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ValueError("Storage key escapes the configured storage root")
        return candidate

    def open(self, storage_key: str) -> BinaryIO:
        return self._path(storage_key).open("rb")

    def delete(self, storage_key: str) -> None:
        self._path(storage_key).unlink(missing_ok=True)

    def exists(self, storage_key: str) -> bool:
        return self._path(storage_key).is_file()


class S3Storage:
    def __init__(
        self,
        bucket: str,
        region: str,
        max_file_bytes: int,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.max_file_bytes = max_file_bytes
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def save_stream(self, source: BinaryIO, storage_key: str) -> tuple[int, str]:
        digest = sha256()
        size = 0
        temporary = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
        try:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > self.max_file_bytes:
                    raise StorageLimitExceeded(f"File exceeds the {self.max_file_bytes} byte storage limit")
                digest.update(chunk)
                temporary.write(chunk)
            temporary.seek(0)
            self.client.upload_fileobj(
                temporary,
                self.bucket,
                storage_key,
                ExtraArgs={"ServerSideEncryption": "AES256"},
            )
        finally:
            temporary.close()
        return size, digest.hexdigest()

    def open(self, storage_key: str) -> BinaryIO:
        return self.client.get_object(Bucket=self.bucket, Key=storage_key)["Body"]

    def delete(self, storage_key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=storage_key)
        except ClientError:
            pass

    def exists(self, storage_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except ClientError:
            return False


def build_storage():
    settings = get_settings()
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalStorage(settings.storage_root, settings.storage_max_file_bytes)
    if backend in {"s3", "s3-compatible"}:
        if not settings.storage_bucket:
            raise ValueError("STORAGE_BUCKET is required for S3 storage")
        return S3Storage(
            settings.storage_bucket,
            settings.storage_region,
            settings.storage_max_file_bytes,
            settings.storage_endpoint_url,
            settings.storage_access_key_id,
            settings.storage_secret_access_key,
        )
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
