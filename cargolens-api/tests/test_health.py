import pytest
from unittest.mock import patch
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Verifies that the root endpoint returns 200 OK and expected API metadata."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CargoLens AI API"
    assert "version" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    """Verifies that GET /health returns 200 OK and healthy service status."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "CargoLens AI API"
    assert data["environment"] == "development"


@pytest.mark.asyncio
async def test_api_v1_health_endpoint(async_client: AsyncClient):
    """Verifies that GET /api/v1/health returns 200 OK."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_db_health_unhealthy_when_database_down(async_client: AsyncClient):
    """Verifies that GET /health/db returns 503 Service Unavailable when the database is offline."""
    with patch("app.api.v1.health.check_database_connection") as mock_check:
        mock_check.return_value = {
            "connected": False,
            "dialect": "postgresql",
            "latency_ms": 50.12,
            "error": "Connection refused to PostgreSQL on localhost:5432",
        }
        response = await async_client.get("/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "Connection refused" in data["error"]


@pytest.mark.asyncio
async def test_db_health_healthy_when_database_connected(async_client: AsyncClient):
    """Verifies that GET /health/db returns 200 OK when the database is reachable."""
    with patch("app.api.v1.health.check_database_connection") as mock_check:
        mock_check.return_value = {
            "connected": True,
            "dialect": "postgresql",
            "latency_ms": 2.15,
            "error": None,
        }
        response = await async_client.get("/health/db")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["latency_ms"] == 2.15
        assert data["error"] is None
