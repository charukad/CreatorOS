from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.config import Settings, get_settings
from apps.api.core.redaction import redact_sensitive_value
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
            "database": redact_sensitive_value(settings.database_url),
            "redis": redact_sensitive_value(settings.redis_url),
        },
    )
