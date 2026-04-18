from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.config import Settings, get_settings
from apps.api.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/live", response_model=HealthResponse)
def live_health(settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="api",
        environment=settings.app_env,
        dependencies={"database": "configured", "redis": "configured"},
    )


@router.get("/ready", response_model=HealthResponse)
def ready_health(settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="api",
        environment=settings.app_env,
        dependencies={
            "database": settings.database_url,
            "redis": settings.redis_url,
        },
    )
