from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.db.session import get_db
from apps.api.schemas.content_workflow import OperationsRecoveryResponse
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
