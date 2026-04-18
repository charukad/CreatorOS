from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrandProfileBase(BaseModel):
    channel_name: str = Field(min_length=1, max_length=255)
    niche: str = Field(min_length=1, max_length=255)
    target_audience: str = Field(min_length=1)
    tone: str = Field(min_length=1, max_length=255)
    hook_style: str = Field(min_length=1, max_length=255)
    cta_style: str = Field(min_length=1, max_length=255)
    visual_style: str = Field(min_length=1, max_length=255)
    posting_preferences_json: dict = Field(default_factory=dict)


class BrandProfileCreate(BrandProfileBase):
    pass


class BrandProfileUpdate(BaseModel):
    channel_name: str | None = Field(default=None, min_length=1, max_length=255)
    niche: str | None = Field(default=None, min_length=1, max_length=255)
    target_audience: str | None = Field(default=None, min_length=1)
    tone: str | None = Field(default=None, min_length=1, max_length=255)
    hook_style: str | None = Field(default=None, min_length=1, max_length=255)
    cta_style: str | None = Field(default=None, min_length=1, max_length=255)
    visual_style: str | None = Field(default=None, min_length=1, max_length=255)
    posting_preferences_json: dict | None = None


class BrandProfileResponse(BrandProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
