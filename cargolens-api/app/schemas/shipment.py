from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.shipment import ShipmentStatus


class ShipmentBase(BaseModel):
    shipment_number: str = Field(..., min_length=2, max_length=100)
    client_name: str = Field(..., min_length=2, max_length=255)
    origin_country: str = Field(..., min_length=2, max_length=100)
    product_description: Optional[str] = None
    quantity: Optional[Decimal] = Field(None, ge=Decimal("0.0"))
    unit_price: Optional[Decimal] = Field(None, ge=Decimal("0.0"))
    currency: Optional[str] = Field(None, max_length=10)
    gross_weight_kg: Optional[Decimal] = Field(None, ge=Decimal("0.0"))  # 0.001 kg (one gram) precision

    @field_validator("shipment_number", mode="before")
    @classmethod
    def clean_shipment_number(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().upper()
        return v


class ShipmentCreate(ShipmentBase):
    model_config = ConfigDict(extra="forbid")


class ShipmentUpdate(BaseModel):
    client_name: Optional[str] = Field(None, min_length=2, max_length=255)
    origin_country: Optional[str] = Field(None, min_length=2, max_length=100)
    product_description: Optional[str] = None
    quantity: Optional[Decimal] = Field(None, ge=Decimal("0.0"))
    unit_price: Optional[Decimal] = Field(None, ge=Decimal("0.0"))
    currency: Optional[str] = Field(None, max_length=10)
    gross_weight_kg: Optional[Decimal] = Field(None, ge=Decimal("0.0"))
    status: Optional[ShipmentStatus] = None

    model_config = ConfigDict(extra="forbid")


class ShipmentResponse(ShipmentBase):
    id: UUID
    status: ShipmentStatus
    is_demo: bool = False
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShipmentListResponse(BaseModel):
    items: List[ShipmentResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    status_summary: Optional[Dict[str, int]] = None
