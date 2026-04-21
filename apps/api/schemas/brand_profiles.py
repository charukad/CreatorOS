from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

BRAND_TEXT_FIELDS = (
    "channel_name",
    "niche",
    "target_audience",
    "tone",
    "hook_style",
    "cta_style",
    "visual_style",
)


class BrandProfileValidationMixin(BaseModel):
    @field_validator(*BRAND_TEXT_FIELDS, mode="before", check_fields=False)
    @classmethod
    def strip_brand_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("posting_preferences_json", check_fields=False)
    @classmethod
    def validate_posting_preferences(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("Posting preferences must be a JSON object.")

        platforms = value.get("platforms")
        if platforms is not None:
            if not isinstance(platforms, list) or not all(
                isinstance(platform, str) and platform.strip() for platform in platforms
            ):
                raise ValueError("posting_preferences_json.platforms must be a list of strings.")
            value["platforms"] = [platform.strip() for platform in platforms]

        default_platform = value.get("default_platform")
        if default_platform is not None and (
            not isinstance(default_platform, str) or not default_platform.strip()
        ):
            raise ValueError("posting_preferences_json.default_platform must be a string.")
        if isinstance(default_platform, str):
            value["default_platform"] = default_platform.strip()

        output_defaults = value.get("output_defaults")
        if output_defaults is not None and not isinstance(output_defaults, dict):
            raise ValueError("posting_preferences_json.output_defaults must be an object.")

        return value


class BrandProfileBase(BrandProfileValidationMixin):
    channel_name: str = Field(min_length=1, max_length=255)
    niche: str = Field(min_length=1, max_length=255)
    target_audience: str = Field(min_length=1)
    tone: str = Field(min_length=1, max_length=255)
    hook_style: str = Field(min_length=1, max_length=255)
    cta_style: str = Field(min_length=1, max_length=255)
    visual_style: str = Field(min_length=1, max_length=255)
    posting_preferences_json: dict[str, Any] = Field(default_factory=dict)


class BrandProfileCreate(BrandProfileBase):
    pass


class BrandProfileUpdate(BrandProfileValidationMixin):
    channel_name: str | None = Field(default=None, min_length=1, max_length=255)
    niche: str | None = Field(default=None, min_length=1, max_length=255)
    target_audience: str | None = Field(default=None, min_length=1)
    tone: str | None = Field(default=None, min_length=1, max_length=255)
    hook_style: str | None = Field(default=None, min_length=1, max_length=255)
    cta_style: str | None = Field(default=None, min_length=1, max_length=255)
    visual_style: str | None = Field(default=None, min_length=1, max_length=255)
    posting_preferences_json: dict[str, Any] | None = None


class BrandProfileResponse(BrandProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class BrandProfileReadinessResponse(BaseModel):
    brand_profile_id: UUID
    is_ready: bool
    missing_fields: list[str]
    warnings: list[str]
    recommended_next_steps: list[str]


class BrandPromptContextResponse(BaseModel):
    brand_profile_id: UUID
    readiness: BrandProfileReadinessResponse
    context_markdown: str
    context_json: dict[str, Any]
