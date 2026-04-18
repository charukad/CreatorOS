from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.enums import ProjectStatus


class ProjectBase(BaseModel):
    brand_profile_id: UUID
    title: str = Field(min_length=1, max_length=255)
    target_platform: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=1)
    notes: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    brand_profile_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    target_platform: str | None = Field(default=None, min_length=1, max_length=100)
    objective: str | None = Field(default=None, min_length=1)
    notes: str | None = None


class ProjectTransitionRequest(BaseModel):
    target_status: ProjectStatus


class ProjectResponse(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
