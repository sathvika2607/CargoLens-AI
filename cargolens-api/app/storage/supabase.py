import logging
import uuid
from typing import AsyncIterator
import httpx

from app.config import settings
from app.storage.base import StorageService

logger = logging.getLogger(__name__)


class SupabaseStorageService(StorageService):
    """
    Production-ready Supabase Storage implementation of StorageService.
    Interacts directly with Supabase Storage REST API using httpx.
    Keeps buckets private and strictly avoids exposing secret keys in logs,
    exceptions, or responses.
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        bucket: str | None = None,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ):
        raw_url = supabase_url if supabase_url is not None else (settings.SUPABASE_URL or "")
        self.supabase_url = raw_url.strip().rstrip("/")
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL is required for SupabaseStorageService")

        raw_key = service_role_key if service_role_key is not None else (settings.SUPABASE_SERVICE_ROLE_KEY or "")
        self.service_role_key = raw_key.strip()
        if not self.service_role_key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY is required for SupabaseStorageService")

        raw_bucket = bucket if bucket is not None else (settings.SUPABASE_STORAGE_BUCKET or "")
        self.bucket = raw_bucket.strip()
        if not self.bucket:
            raise ValueError("SUPABASE_STORAGE_BUCKET is required for SupabaseStorageService")

        self.timeout = timeout
        self._custom_client = client
        self._client: httpx.AsyncClient | None = client

    def __repr__(self) -> str:
        # Strictly exclude service_role_key to avoid leaking secrets in debugging or repr
        return f"<SupabaseStorageService(url='{self.supabase_url}', bucket='{self.bucket}')>"

    @property
    def _base_storage_url(self) -> str:
        return f"{self.supabase_url}/storage/v1"

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_role_key}",
            "apikey": self.service_role_key,
        }

    def _sanitize_error(self, message: str) -> str:
        """Strips the secret key from any error messages to prevent leakage."""
        if self.service_role_key and self.service_role_key in message:
            return message.replace(self.service_role_key, "[REDACTED]")
        return message

    def _validate_storage_key(self, storage_key: str) -> str:
        """
        Validates storage key format and rejects path traversal attempts.
        Preserves relative folder prefixes if safe.
        """
        if not storage_key or not isinstance(storage_key, str):
            raise ValueError(f"Invalid storage key: {storage_key!r}")

        cleaned = storage_key.strip().replace("\\", "/")
        if not cleaned or ".." in cleaned or "\0" in cleaned:
            raise ValueError(f"Invalid or unsafe storage key: {storage_key}")

        # Strip any leading slashes
        cleaned = cleaned.lstrip("/")
        if not cleaned or ".." in cleaned:
            raise ValueError(f"Invalid or unsafe storage key: {storage_key}")

        return cleaned

    def get_safe_storage_key(self, extension: str) -> str:
        """
        Generates a collision-resistant UUID-based key.
        Extension is sanitized to alphanumeric characters only.
        """
        clean_ext = extension.lstrip(".").lower()
        clean_ext = "".join(c for c in clean_ext if c.isalnum())
        file_id = uuid.uuid4().hex
        return f"{file_id}.{clean_ext}" if clean_ext else file_id

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
        return self._client

    async def close(self) -> None:
        """Closes internal HTTP client if managed by this service instance."""
        if self._client and not self._client.is_closed and self._custom_client is None:
            await self._client.aclose()
            self._client = None

    async def save_file(self, content_stream: AsyncIterator[bytes], storage_key: str) -> int:
        """
        Streams bytes into Supabase storage under the given storage key.
        Uses x-upsert: true for idempotent writes and returns total bytes written.
        """
        clean_key = self._validate_storage_key(storage_key)

        chunks: list[bytes] = []
        total_written = 0
        async for chunk in content_stream:
            if chunk:
                chunks.append(chunk)
                total_written += len(chunk)

        payload = b"".join(chunks)

        # Content-type detection
        content_type = "application/octet-stream"
        key_lower = clean_key.lower()
        if key_lower.endswith(".pdf"):
            content_type = "application/pdf"
        elif key_lower.endswith(".jpg") or key_lower.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif key_lower.endswith(".png"):
            content_type = "image/png"

        url = f"{self._base_storage_url}/object/{self.bucket}/{clean_key}"
        headers = {
            **self._auth_headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        client = await self._ensure_client()
        try:
            response = await client.post(url, content=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Supabase storage upload timed out for key: '{clean_key}'") from exc
        except httpx.RequestError as exc:
            msg = self._sanitize_error(str(exc))
            raise IOError(f"Network error during Supabase upload for key '{clean_key}': {msg}") from exc

        if response.status_code not in (200, 201):
            error_detail = "Unknown error"
            try:
                err_json = response.json()
                error_detail = err_json.get("message") or err_json.get("error") or str(err_json)
            except Exception:
                error_detail = response.text[:200]
            clean_err = self._sanitize_error(str(error_detail))
            raise IOError(f"Supabase upload failed ({response.status_code}): {clean_err}")

        return total_written

    async def get_file_stream(self, storage_key: str, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        """
        Yields chunks of the stored file from Supabase private storage.
        Raises FileNotFoundError if the object does not exist.
        """
        clean_key = self._validate_storage_key(storage_key)
        url = f"{self._base_storage_url}/object/authenticated/{self.bucket}/{clean_key}"
        client = await self._ensure_client()

        try:
            req = client.build_request("GET", url, headers=self._auth_headers)
            response = await client.send(req, stream=True)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Supabase download timed out for key: '{clean_key}'") from exc
        except httpx.RequestError as exc:
            msg = self._sanitize_error(str(exc))
            raise IOError(f"Network error during Supabase download for key '{clean_key}': {msg}") from exc

        if response.status_code == 404:
            await response.aclose()
            raise FileNotFoundError(f"Storage file for key '{storage_key}' not found.")

        if response.is_error:
            status_code = response.status_code
            await response.aclose()
            raise IOError(f"Supabase download failed with status code {status_code}")

        try:
            async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                if chunk:
                    yield chunk
        finally:
            await response.aclose()

    async def delete_file(self, storage_key: str) -> bool:
        """
        Removes file associated with the storage key via Supabase Storage bulk delete API.
        Returns True if deleted or already absent, False on failure.
        """
        try:
            clean_key = self._validate_storage_key(storage_key)
        except ValueError:
            return False

        url = f"{self._base_storage_url}/object/{self.bucket}"
        headers = {
            **self._auth_headers,
            "Content-Type": "application/json",
        }
        payload = {"prefixes": [clean_key]}

        client = await self._ensure_client()
        try:
            req = client.build_request("DELETE", url, json=payload, headers=headers)
            response = await client.send(req)
            # Supabase returns 200 or 204 on delete, or 404 if already absent
            return response.status_code in (200, 204, 404)
        except Exception as exc:
            logger.warning(
                "Failed to delete file '%s' from Supabase: %s",
                clean_key,
                self._sanitize_error(str(exc)),
            )
            return False

    async def file_exists(self, storage_key: str) -> bool:
        """
        Checks whether the file exists in private storage using HEAD request.
        """
        try:
            clean_key = self._validate_storage_key(storage_key)
        except ValueError:
            return False

        url = f"{self._base_storage_url}/object/authenticated/{self.bucket}/{clean_key}"
        client = await self._ensure_client()
        try:
            response = await client.head(url, headers=self._auth_headers)
            if response.status_code == 200:
                return True
            if response.status_code == 404:
                return False
            # Fallback for gateways that disallow HEAD: check metadata info
            if response.status_code in (405, 501):
                info_url = f"{self._base_storage_url}/object/info/authenticated/{self.bucket}/{clean_key}"
                info_resp = await client.get(info_url, headers=self._auth_headers)
                return info_resp.status_code == 200
            return False
        except Exception:
            return False
