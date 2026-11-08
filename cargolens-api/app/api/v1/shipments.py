import math
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager
from app.models.user import User, UserRole
from app.models.shipment import Shipment, ShipmentStatus
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentUpdate,
    ShipmentResponse,
    ShipmentListResponse,
)

router = APIRouter(prefix="/shipments", tags=["Shipment Management"])


@router.post(
    "",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Shipment",
    description="Creates a new import consignment record. Accessible to Documentation Executives and Managers.",
)
async def create_shipment(
    shipment_in: ShipmentCreate,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ShipmentResponse:
    # Check duplicate shipment number
    stmt = select(Shipment).where(Shipment.shipment_number == shipment_in.shipment_number)
    existing = await session.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Shipment with number '{shipment_in.shipment_number}' already exists",
        )

    new_shipment = Shipment(
        shipment_number=shipment_in.shipment_number,
        client_name=shipment_in.client_name,
        origin_country=shipment_in.origin_country,
        product_description=shipment_in.product_description,
        quantity=shipment_in.quantity,
        unit_price=shipment_in.unit_price,
        currency=shipment_in.currency.strip().upper() if shipment_in.currency else None,
        gross_weight_kg=shipment_in.gross_weight_kg,
        status=ShipmentStatus.CREATED,
        created_by=current_user.id,
        is_demo=False,
    )
    session.add(new_shipment)
    await session.commit()
    await session.refresh(new_shipment)

    return ShipmentResponse.model_validate(new_shipment)


@router.get(
    "",
    response_model=ShipmentListResponse,
    summary="List Shipments",
    description="Retrieves paginated shipments from the permanent shared customs operations workspace. Accessible to all authorized Documentation Executives and Managers.",
)
async def list_shipments(
    status_filter: Optional[ShipmentStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None, description="Search by shipment number or client name"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ShipmentListResponse:
    # Base query (Shared Workspace: all authenticated executives and managers access the consignment registry)
    base_query = select(Shipment)
    count_query = select(func.count(Shipment.id))

    # Status filter
    if status_filter:
        base_query = base_query.where(Shipment.status == status_filter)
        count_query = count_query.where(Shipment.status == status_filter)

    # Search filter
    if search:
        search_pattern = f"%{search.strip()}%"
        search_clause = or_(
            Shipment.shipment_number.ilike(search_pattern),
            Shipment.client_name.ilike(search_pattern),
            Shipment.origin_country.ilike(search_pattern),
        )
        base_query = base_query.where(search_clause)
        count_query = count_query.where(search_clause)

    # Total count
    total_res = await session.execute(count_query)
    total = total_res.scalar() or 0

    # Pagination & sorting
    offset = (page - 1) * limit
    paginated_query = base_query.order_by(Shipment.created_at.desc()).offset(offset).limit(limit)
    items_res = await session.execute(paginated_query)
    items = items_res.scalars().all()

    # Status breakdown summary for workspace
    summary_stmt = select(Shipment.status, func.count(Shipment.id)).group_by(Shipment.status)
    summary_res = await session.execute(summary_stmt)
    status_summary = {row[0].value: row[1] for row in summary_res.all()}

    total_pages = math.ceil(total / limit) if total > 0 else 1

    return ShipmentListResponse(
        items=[ShipmentResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        status_summary=status_summary,
    )


@router.get(
    "/{shipment_id}",
    response_model=ShipmentResponse,
    summary="Get Shipment Details",
    description="Retrieves a single shipment by UUID for authorized workspace users.",
)
async def get_shipment(
    shipment_id: UUID,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ShipmentResponse:
    stmt = select(Shipment).where(Shipment.id == shipment_id)
    res = await session.execute(stmt)
    shipment = res.scalar_one_or_none()

    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID '{shipment_id}' not found",
        )

    return ShipmentResponse.model_validate(shipment)


@router.patch(
    "/{shipment_id}",
    response_model=ShipmentResponse,
    summary="Update Shipment",
    description="Updates permitted shipment attributes in the shared workspace.",
)
async def update_shipment(
    shipment_id: UUID,
    update_data: ShipmentUpdate,
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> ShipmentResponse:
    stmt = select(Shipment).where(Shipment.id == shipment_id)
    res = await session.execute(stmt)
    shipment = res.scalar_one_or_none()

    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipment with ID '{shipment_id}' not found",
        )

    # Workflow lifecycle protection: Neither Executives nor Managers may manually set workflow-controlled statuses
    WORKFLOW_CONTROLLED_STATUSES = {ShipmentStatus.VERIFIED, ShipmentStatus.EXPORTED}
    if update_data.status is not None and update_data.status in WORKFLOW_CONTROLLED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Manual transition to workflow-controlled status '{update_data.status.value}' is prohibited. These statuses are reserved for automated verification and export workflows.",
        )

    # Apply partial updates
    update_dict = update_data.model_dump(exclude_unset=True)
    update_dict.pop("is_demo", None)
    for field, value in update_dict.items():
        if field == "currency" and value is not None:
            value = value.strip().upper() if value.strip() else None
        setattr(shipment, field, value)

    await session.commit()
    await session.refresh(shipment)

    return ShipmentResponse.model_validate(shipment)
