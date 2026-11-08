from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["healthy"])
    service: str = Field(..., examples=["CargoLens AI API"])
    environment: str = Field(..., examples=["development"])
    version: str = Field(..., examples=["0.1.0"])


class DatabaseHealthResponse(BaseModel):
    status: str = Field(..., examples=["healthy"])
    database: str = Field(..., examples=["connected"])
    dialect: Optional[str] = Field(None, examples=["postgresql"])
    latency_ms: Optional[float] = Field(None, examples=[2.45])
    error: Optional[str] = Field(None, examples=[None])
