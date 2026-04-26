from fastapi import APIRouter

from apps.api.routes.brand_profiles import router as brand_profile_router
from apps.api.routes.content_workflow import router as content_workflow_router
from apps.api.routes.health import router as health_router
from apps.api.routes.job_events import router as job_events_router
from apps.api.routes.operations import router as operations_router
from apps.api.routes.projects import router as project_router
from apps.api.routes.session import router as session_router

api_router = APIRouter()
api_router.include_router(brand_profile_router)
api_router.include_router(content_workflow_router)
api_router.include_router(health_router)
api_router.include_router(job_events_router)
api_router.include_router(operations_router)
api_router.include_router(project_router)
api_router.include_router(session_router)
