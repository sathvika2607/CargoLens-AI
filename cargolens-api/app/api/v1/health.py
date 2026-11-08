from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import check_database_connection
from app.schemas.health import HealthResponse, DatabaseHealthResponse

router = APIRouter(tags=["Health & Diagnostics"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Probe",
    description="Returns the operational status of the CargoLens AI API service.",
)
async def get_health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
    )


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    summary="Database Connectivity Probe",
    description="Actively verifies PostgreSQL database connectivity using asyncpg.",
    responses={
        200: {"description": "Database connection verified successfully."},
        503: {"description": "Database connection failed or unreachable."},
    },
)
async def get_database_health():
    db_status = await check_database_connection()

    if db_status["connected"]:
        return DatabaseHealthResponse(
            status="healthy",
            database="connected",
            dialect=db_status["dialect"],
            latency_ms=db_status["latency_ms"],
            error=None,
        )

    # Return 503 Service Unavailable if database is unreachable
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "unhealthy",
            "database": "disconnected",
            "dialect": db_status["dialect"],
            "latency_ms": db_status["latency_ms"],
            "error": db_status["error"],
        },
    )
