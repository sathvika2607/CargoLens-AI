import json
import pytest
import httpx
from typing import AsyncIterator

from app.config import settings
from app.storage.base import StorageService
from app.storage.local import LocalStorageService
from app.storage.supabase import SupabaseStorageService
from app.storage import get_storage_service, reset_storage_service


async def _to_async_stream(data: bytes, chunk_size: int = 1024) -> AsyncIterator[bytes]:
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


@pytest.fixture(autouse=True)
def clean_storage_singleton():
    """Ensure storage singleton is reset before and after every test."""
    reset_storage_service()
    yield
    reset_storage_service()


# ==============================================================================
# 1. Initialization, Secrets Redaction, and Key Generation
# ==============================================================================

def test_supabase_storage_init_and_repr_redaction():
    service = SupabaseStorageService(
        supabase_url="https://test-project.supabase.co",
        service_role_key="super-secret-service-role-key-xyz",
        bucket="custom-bucket",
    )
    assert service.supabase_url == "https://test-project.supabase.co"
    assert service.bucket == "custom-bucket"
    assert service.service_role_key == "super-secret-service-role-key-xyz"

    # Representation must NEVER leak the secret key
    repr_str = repr(service)
    assert "super-secret-service-role-key-xyz" not in repr_str
    assert "custom-bucket" in repr_str
    assert "https://test-project.supabase.co" in repr_str


def test_supabase_storage_init_validation_errors():
    with pytest.raises(ValueError, match="SUPABASE_URL is required"):
        SupabaseStorageService(
            supabase_url="",
            service_role_key="secret-key",
            bucket="bucket",
        )

    with pytest.raises(ValueError, match="SUPABASE_SERVICE_ROLE_KEY is required"):
        SupabaseStorageService(
            supabase_url="https://test.supabase.co",
            service_role_key="",
            bucket="bucket",
        )

    with pytest.raises(ValueError, match="SUPABASE_STORAGE_BUCKET is required"):
        SupabaseStorageService(
            supabase_url="https://test.supabase.co",
            service_role_key="secret-key",
            bucket="",
        )


def test_get_safe_storage_key():
    service = SupabaseStorageService(
        supabase_url="https://test.supabase.co",
        service_role_key="secret-key",
        bucket="bucket",
    )

    pdf_key = service.get_safe_storage_key("pdf")
    assert pdf_key.endswith(".pdf")
    assert len(pdf_key.split(".")[0]) == 32

    upper_key = service.get_safe_storage_key(".PDF")
    assert upper_key.endswith(".pdf")

    no_ext = service.get_safe_storage_key("")
    assert "." not in no_ext
    assert len(no_ext) == 32


@pytest.mark.asyncio
async def test_unsafe_storage_key_rejections():
    service = SupabaseStorageService(
        supabase_url="https://test.supabase.co",
        service_role_key="secret-key",
        bucket="bucket",
    )

    # Path traversal rejection
    with pytest.raises(ValueError, match="Invalid or unsafe storage key"):
        await service.save_file(_to_async_stream(b"test"), "../../etc/passwd")

    with pytest.raises(ValueError, match="Invalid or unsafe storage key"):
        async for _ in service.get_file_stream("../secret.pem"):
            pass

    # Empty key rejection
    with pytest.raises(ValueError, match="Invalid or unsafe storage key"):
        await service.save_file(_to_async_stream(b"test"), "   ")

    # file_exists and delete_file safely return False on invalid keys
    assert await service.file_exists("../../secret.txt") is False
    assert await service.delete_file("../secret.txt") is False


# ==============================================================================
# 2. Upload Operations (save_file)
# ==============================================================================

@pytest.mark.asyncio
async def test_save_file_success():
    recorded_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(201, json={"Key": "cargolens-documents/doc123.pdf", "Id": "obj-123"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-service-key-999",
        bucket="cargolens-documents",
        client=client,
    )

    test_content = b"%PDF-1.4 sample customs document binary payload"
    written = await service.save_file(_to_async_stream(test_content), "doc123.pdf")

    assert written == len(test_content)
    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.method == "POST"
    assert req.url == httpx.URL("https://demo.supabase.co/storage/v1/object/cargolens-documents/doc123.pdf")
    assert req.headers["Authorization"] == "Bearer test-service-key-999"
    assert req.headers["apikey"] == "test-service-key-999"
    assert req.headers["Content-Type"] == "application/pdf"
    assert req.headers["x-upsert"] == "true"
    assert req.content == test_content


@pytest.mark.asyncio
async def test_save_file_http_failure_sanitizes_secret():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"error": "AccessDenied", "message": "Service key test-service-key-999 not allowed"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-service-key-999",
        bucket="cargolens-documents",
        client=client,
    )

    with pytest.raises(IOError) as exc_info:
        await service.save_file(_to_async_stream(b"test"), "error.pdf")

    err_msg = str(exc_info.value)
    assert "Supabase upload failed (403)" in err_msg
    # Crucial security guarantee: Secret key must be redacted
    assert "test-service-key-999" not in err_msg
    assert "[REDACTED]" in err_msg


@pytest.mark.asyncio
async def test_save_file_timeout():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out after 30s")

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="key",
        bucket="bucket",
        client=client,
    )

    with pytest.raises(TimeoutError, match="timed out for key"):
        await service.save_file(_to_async_stream(b"data"), "timeout.pdf")


# ==============================================================================
# 3. Download & Streaming (get_file_stream)
# ==============================================================================

@pytest.mark.asyncio
async def test_get_file_stream_success():
    expected_content = b"%PDF-1.4 Simulated Commercial Invoice Payload Chunks"

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == httpx.URL(
            "https://demo.supabase.co/storage/v1/object/authenticated/cargolens-documents/invoice_001.pdf"
        )
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["apikey"] == "test-key"
        return httpx.Response(200, content=expected_content)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-key",
        bucket="cargolens-documents",
        client=client,
    )

    downloaded = bytearray()
    async for chunk in service.get_file_stream("invoice_001.pdf", chunk_size=16):
        downloaded.extend(chunk)

    assert bytes(downloaded) == expected_content


@pytest.mark.asyncio
async def test_get_file_stream_not_found():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "Not Found", "message": "Object not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-key",
        bucket="cargolens-documents",
        client=client,
    )

    with pytest.raises(FileNotFoundError, match="Storage file for key 'missing.pdf' not found"):
        async for _ in service.get_file_stream("missing.pdf"):
            pass


@pytest.mark.asyncio
async def test_get_file_stream_http_error():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-key",
        bucket="cargolens-documents",
        client=client,
    )

    with pytest.raises(IOError, match="Supabase download failed with status code 500"):
        async for _ in service.get_file_stream("broken.pdf"):
            pass


# ==============================================================================
# 4. Existence Checking (file_exists)
# ==============================================================================

@pytest.mark.asyncio
async def test_file_exists_true_and_false():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "HEAD"
        if "existing.pdf" in str(request.url):
            return httpx.Response(200)
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-key",
        bucket="cargolens-documents",
        client=client,
    )

    assert await service.file_exists("existing.pdf") is True
    assert await service.file_exists("missing.pdf") is False


@pytest.mark.asyncio
async def test_file_exists_head_fallback_to_info():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD":
            return httpx.Response(405)  # Method not allowed on HEAD
        if request.method == "GET" and "/object/info/" in str(request.url):
            return httpx.Response(200, json={"size": 1234})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-key",
        bucket="cargolens-documents",
        client=client,
    )

    assert await service.file_exists("fallback.pdf") is True


# ==============================================================================
# 5. Delete Operations (delete_file)
# ==============================================================================

@pytest.mark.asyncio
async def test_delete_file_success():
    recorded_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(200, json=[{"name": "to_delete.pdf"}])

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-key",
        bucket="cargolens-documents",
        client=client,
    )

    result = await service.delete_file("to_delete.pdf")
    assert result is True
    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.method == "DELETE"
    assert req.url == httpx.URL("https://demo.supabase.co/storage/v1/object/cargolens-documents")
    assert json.loads(req.content.decode("utf-8")) == {"prefixes": ["to_delete.pdf"]}


@pytest.mark.asyncio
async def test_delete_file_already_absent_returns_true():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-key",
        bucket="cargolens-documents",
        client=client,
    )

    assert await service.delete_file("already_gone.pdf") is True


@pytest.mark.asyncio
async def test_delete_file_server_error_returns_false():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    service = SupabaseStorageService(
        supabase_url="https://demo.supabase.co",
        service_role_key="test-key",
        bucket="cargolens-documents",
        client=client,
    )

    assert await service.delete_file("error.pdf") is False


# ==============================================================================
# 6. Storage Factory & Backend Selection (app/storage/__init__.py)
# ==============================================================================

def test_storage_factory_local_selection(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    storage = get_storage_service()
    assert isinstance(storage, LocalStorageService)


def test_storage_factory_supabase_selection(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "supabase")
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://xyz.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "sb-secret-key-123")
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_BUCKET", "test-bucket")

    storage = get_storage_service()
    assert isinstance(storage, SupabaseStorageService)
    assert storage.supabase_url == "https://xyz.supabase.co"
    assert storage.bucket == "test-bucket"


def test_storage_factory_supabase_missing_url_raises(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "supabase")
    monkeypatch.setattr(settings, "SUPABASE_URL", None)
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_BUCKET", "bucket")

    with pytest.raises(ValueError, match="SUPABASE_URL is not configured"):
        get_storage_service()


def test_storage_factory_supabase_missing_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "supabase")
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://xyz.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_BUCKET", "bucket")

    with pytest.raises(ValueError, match="SUPABASE_SERVICE_ROLE_KEY is not configured"):
        get_storage_service()


def test_storage_factory_invalid_backend_raises(monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "aws_s3_unsupported")

    with pytest.raises(ValueError, match="Invalid or unsupported STORAGE_BACKEND: 'aws_s3_unsupported'"):
        get_storage_service()
