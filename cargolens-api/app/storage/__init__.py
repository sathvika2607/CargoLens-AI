from app.storage.base import StorageService
from app.storage.local import LocalStorageService
from app.storage.supabase import SupabaseStorageService
from app.config import settings

_default_storage: StorageService | None = None


def get_storage_service() -> StorageService:
    """
    Returns the configured storage service singleton.
    Selects LocalStorageService when STORAGE_BACKEND=local,
    or SupabaseStorageService when STORAGE_BACKEND=supabase.
    Raises ValueError on invalid or missing configurations.
    """
    global _default_storage
    if _default_storage is None:
        backend = (settings.STORAGE_BACKEND or "local").lower().strip()
        if backend == "local":
            _default_storage = LocalStorageService()
        elif backend == "supabase":
            if not settings.SUPABASE_URL:
                raise ValueError("STORAGE_BACKEND is set to 'supabase' but SUPABASE_URL is not configured.")
            if not settings.SUPABASE_SERVICE_ROLE_KEY:
                raise ValueError(
                    "STORAGE_BACKEND is set to 'supabase' but SUPABASE_SERVICE_ROLE_KEY is not configured."
                )
            if not settings.SUPABASE_STORAGE_BUCKET:
                raise ValueError(
                    "STORAGE_BACKEND is set to 'supabase' but SUPABASE_STORAGE_BUCKET is not configured."
                )
            _default_storage = SupabaseStorageService(
                supabase_url=settings.SUPABASE_URL,
                service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
                bucket=settings.SUPABASE_STORAGE_BUCKET,
            )
        else:
            raise ValueError(
                f"Invalid or unsupported STORAGE_BACKEND: '{settings.STORAGE_BACKEND}'. "
                "Supported backends are 'local' and 'supabase'."
            )
    return _default_storage


def reset_storage_service() -> None:
    """
    Resets the singleton storage instance.
    Useful for unit testing and dynamic backend switching.
    """
    global _default_storage
    _default_storage = None


__all__ = [
    "StorageService",
    "LocalStorageService",
    "SupabaseStorageService",
    "get_storage_service",
    "reset_storage_service",
]
