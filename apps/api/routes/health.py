from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.core.config import Settings, get_settings
from apps.api.core.redaction import redact_sensitive_value
from apps.api.core.redis import get_redis_connection_status
from apps.api.db.session import get_db
from apps.api.schemas.health import HealthResponse
from apps.api.services.storage_safety import check_directory_private_enough

router = APIRouter(prefix="/health", tags=["health"])


SettingsDependency = Annotated[Settings, Depends(get_settings)]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/live", response_model=HealthResponse)
def live_health(settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="api",
        environment=settings.app_env,
        dependencies={"database": "configured", "redis": "configured"},
    )


@router.get("/ready", response_model=HealthResponse)
def ready_health(settings: SettingsDependency, db: DbSession) -> HealthResponse:
    dependencies = {
        "database": _check_database_connection_status(db, settings.database_url),
        "redis": get_redis_connection_status(settings.redis_url),
    }

    try:
        dependencies["storage_root"] = check_directory_private_enough(settings.storage_root)
    except OSError as error:
        dependencies["storage_root"] = f"not_writable: {error.__class__.__name__}"

    try:
        dependencies["downloads_root"] = check_directory_private_enough(settings.downloads_root)
    except OSError as error:
        dependencies["downloads_root"] = f"not_writable: {error.__class__.__name__}"

    status_value = (
        "ok"
        if all(_dependency_is_healthy(value) for value in dependencies.values())
        else "degraded"
    )

    return HealthResponse(
        status=status_value,
        service="api",
        environment=settings.app_env,
        dependencies=dependencies,
    )


def _check_database_connection_status(db: Session, database_url: str) -> str:
    safe_url = redact_sensitive_value(database_url)
    try:
        db.execute(text("SELECT 1"))
    except Exception as error:
        return f"unavailable: {error.__class__.__name__} ({safe_url})"
    return f"reachable ({safe_url})"


def _dependency_is_healthy(value: str) -> bool:
    return value.startswith("reachable") or value == "writable"
