from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel
from app.schemas.shipment import ShipmentResponse


class RecentActivityItem(BaseModel):
    id: str
    action_type: str
    description: str
    actor_name: Optional[str] = None
    shipment_id: Optional[UUID] = None
    shipment_number: Optional[str] = None
    created_at: str


class ExecutiveDashboardStats(BaseModel):
    my_shipments_count: int
    documents_uploaded_count: int
    processing_in_progress_count: int
    documents_awaiting_review_count: int
    validation_failures_count: int
    recent_shipments: List[ShipmentResponse]
    recent_activity: List[RecentActivityItem]


class ManagerDashboardStats(BaseModel):
    total_shipments_count: int
    shipments_by_status: Dict[str, int]
    documents_awaiting_review_count: int
    validation_failures_count: int
    processing_failures_count: int
    recent_shipments: List[ShipmentResponse]
    recent_activity: List[RecentActivityItem]


class DashboardStatsResponse(BaseModel):
    role: str
    executive: Optional[ExecutiveDashboardStats] = None
    manager: Optional[ManagerDashboardStats] = None
