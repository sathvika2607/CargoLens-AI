from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.shipments import router as shipments_router
from app.api.v1.documents import router as documents_router
from app.api.v1.extractions import router as extractions_router
from app.api.v1.structured_extractions import router as structured_extractions_router
from app.api.v1.validations import router as validations_router
from app.api.v1.field_reviews import router as field_reviews_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.workflow import router as workflow_router
from app.api.v1.exports import router as exports_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.simulation import router as simulation_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(shipments_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(extractions_router)
api_v1_router.include_router(structured_extractions_router)
api_v1_router.include_router(validations_router)
api_v1_router.include_router(field_reviews_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(workflow_router)
api_v1_router.include_router(exports_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(simulation_router)
