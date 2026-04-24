from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ViewerSessionUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str


class ViewerSessionResponse(BaseModel):
    auth_mode: Literal["single_user_local"]
    environment: str
    requires_approval_checkpoints: bool
    user: ViewerSessionUserResponse
