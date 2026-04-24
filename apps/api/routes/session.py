from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.core.config import Settings, get_settings
from apps.api.db.session import get_db
from apps.api.schemas.session import ViewerSessionResponse, ViewerSessionUserResponse
from apps.api.services.users import get_or_create_default_user

router = APIRouter(prefix="/session", tags=["session"])

DbSession = Annotated[Session, Depends(get_db)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=ViewerSessionResponse)
def get_viewer_session_route(
    db: DbSession,
    settings: SettingsDependency,
) -> ViewerSessionResponse:
    user = get_or_create_default_user(db)
    return ViewerSessionResponse(
        auth_mode="single_user_local",
        environment=settings.app_env,
        requires_approval_checkpoints=True,
        user=ViewerSessionUserResponse.model_validate(user),
    )
