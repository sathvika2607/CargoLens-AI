import os
import uuid
import anyio
from pathlib import Path
from typing import AsyncIterator
from app.config import settings
from app.storage.base import StorageService


class LocalStorageService(StorageService):
    """
    Local filesystem implementation of StorageService.
    Stores files securely outside of static web directories with path-traversal prevention.
    """

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or settings.STORAGE_LOCAL_DIR).resolve()
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve_path(self, storage_key: str) -> Path:
        """
        Resolves storage key to absolute filesystem path and prevents path traversal.
        """
        # Strip leading slashes or backslashes
        cleaned_key = os.path.basename(storage_key.strip())
        if not cleaned_key or ".." in storage_key:
            raise ValueError(f"Invalid storage key: {storage_key}")

        target_path = (self.base_dir / cleaned_key).resolve()
        if not target_path.is_relative_to(self.base_dir):
            raise ValueError(f"Path traversal detected for key: {storage_key}")

        return target_path

    def get_safe_storage_key(self, extension: str) -> str:
        """
        Generates a collision-resistant UUID-based key.
        Extension is sanitized to alphanumeric characters only.
        """
        clean_ext = extension.lstrip(".").lower()
        clean_ext = "".join(c for c in clean_ext if c.isalnum())
        file_id = uuid.uuid4().hex
        return f"{file_id}.{clean_ext}" if clean_ext else file_id

    async def save_file(self, content_stream: AsyncIterator[bytes], storage_key: str) -> int:
        target_path = self._resolve_path(storage_key)
        total_written = 0
        temp_path = target_path.with_suffix(".tmp")

        try:
            # Write to temp file asynchronously
            async with await anyio.open_file(temp_path, "wb") as f:
                async for chunk in content_stream:
                    if chunk:
                        await f.write(chunk)
                        total_written += len(chunk)

            # Atomic rename after full write
            if os.path.exists(temp_path):
                os.replace(temp_path, target_path)

            return total_written
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    async def get_file_stream(self, storage_key: str, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        target_path = self._resolve_path(storage_key)
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"Storage file for key '{storage_key}' not found.")

        async with await anyio.open_file(target_path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete_file(self, storage_key: str) -> bool:
        try:
            target_path = self._resolve_path(storage_key)
            if target_path.exists():
                os.remove(target_path)
            return True
        except Exception:
            return False

    async def file_exists(self, storage_key: str) -> bool:
        try:
            target_path = self._resolve_path(storage_key)
            return target_path.exists() and target_path.is_file()
        except Exception:
            return False
