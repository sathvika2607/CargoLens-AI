from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import dispose_engine
from app.api.v1.health import router as health_router
from app.api.v1 import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    yield
    # Shutdown tasks: ensure database connections are cleanly disposed
    await dispose_engine()


def create_application() -> FastAPI:
    """Application factory for CargoLens AI FastAPI service."""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="CargoLens AI — Intelligent Import Documentation & Verification Platform",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root informational endpoint
    @application.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
            "health": "/health",
        }

    # Mount top-level health routes (/health, /health/db)
    application.include_router(health_router)

    # Mount versioned API routes (/api/v1/...)
    application.include_router(api_v1_router, prefix="/api/v1")

    return application


app = create_application()
