from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


class Settings(BaseSettings):
    PROJECT_NAME: str = "CargoLens AI API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    ALLOW_DEMO_SEEDING: bool = True

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    return json.loads(v_stripped)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            return list(v)
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Security & Authentication Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "cargolens-api"
    JWT_AUDIENCE: str = "cargolens-client"
    BOOTSTRAP_SECRET: str

    # Storage Configuration (Provider-neutral abstraction)
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_DIR: str = "storage/documents"
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB per file
    MAX_PDF_PAGES: int = 50
    MAX_IMAGE_DIMENSION: int = 10000

    # Supabase Storage Configuration
    SUPABASE_URL: Union[str, None] = None
    SUPABASE_SERVICE_ROLE_KEY: Union[str, None] = None
    SUPABASE_STORAGE_BUCKET: str = "cargolens-documents"

    # Background Processing Configuration
    WORKER_MAX_ATTEMPTS: int = 3
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    WORKER_LEASE_SECONDS: int = 60
    WORKER_LEASE_RENEW_INTERVAL_SECONDS: float = 15.0
    STALE_JOB_TIMEOUT_SECONDS: int = 60

    # OCR & Tesseract Configuration
    TESSERACT_CMD: str = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    TESSDATA_PREFIX: Union[str, None] = None
    OCR_LANGUAGE: str = "eng"
    OCR_DPI: int = 300
    OCR_MIN_CONFIDENCE: float = 60.0
    OCR_MIN_TEXT_LENGTH: int = 15
    OCR_MAX_PAGE_PROCESSING_TIME: int = 30
    OCR_MAX_DOCUMENT_PROCESSING_TIME: int = 300

    # AI Provider Configuration (Claude Vision / Anthropic)
    ANTHROPIC_API_KEY: Union[str, None] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5-5"
    ANTHROPIC_TIMEOUT_SECONDS: float = 60.0
    ANTHROPIC_MAX_RETRIES: int = 2
    STRUCTURED_EXTRACTION_MAX_IMAGE_PAGES: int = 5

    # Cross-Document Validation Settings
    VALIDATION_WEIGHT_TOLERANCE_KG: float = 1.0
    VALIDATION_CURRENCY_TOLERANCE: float = 0.01

    # PostgreSQL Database Settings
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "cargolens_user"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "cargolens_db"
    DATABASE_URL: Union[str, None] = None

    @property
    def async_database_url(self) -> str:
        """Returns the PostgreSQL asyncpg connection string."""
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """Returns the synchronous PostgreSQL connection string for Alembic migrations."""
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()