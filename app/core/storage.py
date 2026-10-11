from hashlib import sha256
from pathlib import Path
from typing import BinaryIO


class StorageLimitExceeded(ValueError):
    pass


class LocalStorage:
    def __init__(self, root: str, max_file_bytes: int) -> None:
        self.root = Path(root).resolve()
        self.max_file_bytes = max_file_bytes

    def _path(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if self.root != candidate and self.root not in candidate.parents:
            raise ValueError("Storage key escapes the configured storage root")
        return candidate

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
                        raise StorageLimitExceeded(
                            f"File exceeds the {self.max_file_bytes} byte storage limit"
                        )
                    digest.update(chunk)
                    target.write(chunk)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return size, digest.hexdigest()

    def path_for(self, storage_key: str) -> Path:
        return self._path(storage_key)

    def open(self, storage_key: str) -> BinaryIO:
        return self._path(storage_key).open("rb")

    def delete(self, storage_key: str) -> None:
        self._path(storage_key).unlink(missing_ok=True)

    def exists(self, storage_key: str) -> bool:
        return self._path(storage_key).is_file()
