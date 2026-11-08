import time
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_executive_or_manager, require_manager
from app.config import settings
from app.models.user import User, UserRole
from app.models.shipment import Shipment
from app.models.document import Document
from app.models.validation import ShipmentValidationResult, ValidationOutcome
from app.models.export import ShipmentExportRecord
from app.schemas.simulation import (
    SimulationScenarioItem,
    SimulationScenarioListResponse,
    SimulationRunRequest,
    SimulationRunResponse,
    SimulationStatusResponse,
)
from app.services.ai.base import ProviderConfigurationError
from app.services.simulation.engine import SimulationEngine, SCENARIOS_CATALOG

router = APIRouter(prefix="/simulation", tags=["Demo Simulation Center"])


def _check_production_safety():
    """Guards against executing demonstration simulations in production environments."""
    if settings.ENVIRONMENT.lower() == "production" and not settings.ALLOW_DEMO_SEEDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demonstration simulation generation is disabled in production environments.",
        )


@router.get(
    "/scenarios",
    response_model=SimulationScenarioListResponse,
    summary="List Demonstration Scenarios",
    description="Returns available customs demonstration scenarios, capabilities, and active configuration.",
)
async def list_scenarios(
    current_user: User = Depends(require_executive_or_manager),
) -> SimulationScenarioListResponse:
    anthropic_configured = bool(settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY.strip())
    scenarios = [SimulationScenarioItem(**s) for s in SCENARIOS_CATALOG]

    return SimulationScenarioListResponse(
        scenarios=scenarios,
        environment=settings.ENVIRONMENT,
        allow_simulation=settings.ALLOW_DEMO_SEEDING,
        anthropic_configured=anthropic_configured,
        anthropic_model=settings.ANTHROPIC_MODEL,
        default_provider="fixture",
    )


@router.get(
    "/status",
    response_model=SimulationStatusResponse,
    summary="Get Simulation Center Status",
    description="Returns current simulation status and lists active demonstration shipments persisted in the database.",
)
async def get_simulation_status(
    current_user: User = Depends(require_executive_or_manager),
    session: AsyncSession = Depends(get_db),
) -> SimulationStatusResponse:
    anthropic_configured = bool(settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY.strip())

    # Query active demo shipments
    stmt = (
        select(Shipment)
        .where(Shipment.is_demo.is_(True))
        .order_by(Shipment.created_at.desc())
    )
    res = await session.execute(stmt)
    demo_shipments = res.scalars().all()

    demo_list = []
    for s in demo_shipments:
        # Count documents
        docs_cnt = (
            await session.execute(
                select(func.count(Document.id)).where(
                    Document.shipment_id == s.id, Document.is_active == True
                )
            )
        ).scalar() or 0

        # Check export
        exp_res = (
            await session.execute(
                select(ShipmentExportRecord).where(
                    ShipmentExportRecord.shipment_id == s.id
                )
            )
        ).scalar_one_or_none()

        demo_list.append(
            {
                "id": str(s.id),
                "shipment_number": s.shipment_number,
                "client_name": s.client_name,
                "status": s.status.value,
                "origin_country": s.origin_country,
                "product_description": s.product_description,
                "gross_weight_kg": float(s.gross_weight_kg) if s.gross_weight_kg is not None else None,
                "currency": s.currency,
                "documents_count": docs_cnt,
                "exported": exp_res is not None,
                "export_sha256": exp_res.sha256_checksum if exp_res else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
        )

    return SimulationStatusResponse(
        environment=settings.ENVIRONMENT,
        allow_simulation=settings.ALLOW_DEMO_SEEDING,
        anthropic_configured=anthropic_configured,
        anthropic_model=settings.ANTHROPIC_MODEL,
        total_demo_shipments=len(demo_list),
        demo_shipments=demo_list,
    )


@router.post(
    "/run",
    response_model=SimulationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Demonstration Simulation",
    description="Generates synthetic documents, runs OCR jobs, structured extractions, cross-document validations, human reviews, and exports through real backend services. Protected to Documentation Managers.",
)
async def run_simulation(
    request: SimulationRunRequest,
    current_user: User = Depends(require_manager),
    session: AsyncSession = Depends(get_db),
) -> SimulationRunResponse:
    _check_production_safety()
    start_time = time.monotonic()

    # Get executive user for creator role if current user is manager
    stmt_exec = select(User).where(User.role == UserRole.DOCUMENTATION_EXECUTIVE)
    exec_res = await session.execute(stmt_exec)
    exec_user = exec_res.scalars().first() or current_user

    try:
        provider = SimulationEngine.get_provider(request.provider_type)
    except ProviderConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    try:
        if request.scenario_type.upper() == "ALL":
            raw_results = await SimulationEngine.simulate_all(
                session=session,
                creator_user=exec_user,
                manager_user=current_user,
                provider_type=request.provider_type,
            )
        else:
            single_res = await SimulationEngine.simulate_scenario(
                session=session,
                scenario_code=request.scenario_type,
                creator_user=exec_user,
                manager_user=current_user,
                provider_type=request.provider_type,
            )
            raw_results = [single_res]
    except Exception as exc:
        logger.error(f"Demonstration simulation execution failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed during execution: {str(exc)}",
        )

    duration = round(time.monotonic() - start_time, 2)
    return SimulationRunResponse(
        success=True,
        message=f"Successfully executed demonstration simulation ({len(raw_results)} scenario(s) processed in {duration}s).",
        provider_used=provider.provider_name,
        model_used=provider.model_name,
        results=raw_results,
        duration_seconds=duration,
    )


@router.delete(
    "/reset",
    status_code=status.HTTP_200_OK,
    summary="Reset Demonstration Shipments",
    description="Cleanly deletes demonstration shipments and cascaded data without affecting real user records.",
)
async def reset_simulation(
    current_user: User = Depends(require_manager),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    _check_production_safety()
    cleaned_count = await SimulationEngine.clean_all_demo(session)
    return {
        "success": True,
        "cleaned_count": cleaned_count,
        "message": f"Successfully cleaned {cleaned_count} demonstration consignment record(s).",
    }
