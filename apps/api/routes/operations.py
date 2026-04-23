from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.core.config import get_settings
from apps.api.db.session import get_db
from apps.api.schemas.content_workflow import (
    ArtifactRetentionPlanResponse,
    OperationsRecoveryResponse,
)
from apps.api.services.artifact_retention import build_artifact_retention_plan
from apps.api.services.operations import get_operations_recovery_snapshot
from apps.api.services.users import get_or_create_default_user

router = APIRouter(prefix="/operations", tags=["operations"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/recovery", response_model=OperationsRecoveryResponse)
def get_operations_recovery_route(
    db: DbSession,
    stale_after_minutes: Annotated[int, Query(ge=1, le=1440)] = 30,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OperationsRecoveryResponse:
    user = get_or_create_default_user(db)
    return get_operations_recovery_snapshot(
        db,
        user,
        stale_after_minutes=stale_after_minutes,
        limit=limit,
    )


@router.get("/artifacts/retention-plan", response_model=ArtifactRetentionPlanResponse)
def get_artifact_retention_plan_route(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ArtifactRetentionPlanResponse:
    user = get_or_create_default_user(db)
    settings = get_settings()
    return build_artifact_retention_plan(
        db,
        user,
        storage_root=settings.storage_root,
        limit=limit,
    )
