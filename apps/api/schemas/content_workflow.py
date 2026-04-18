from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.enums import (
    AssetStatus,
    AssetType,
    BackgroundJobState,
    BackgroundJobType,
    ContentIdeaStatus,
    ProviderName,
    ScriptStatus,
)


class ContentIdeaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    suggested_title: str
    hook: str
    angle: str
    rationale: str
    score: int
    status: ContentIdeaStatus
    feedback_notes: str | None
    created_at: datetime
    updated_at: datetime


class IdeaApprovalRequest(BaseModel):
    feedback_notes: str | None = None


class SceneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    script_id: UUID
    scene_order: int
    title: str
    narration_text: str
    overlay_text: str
    image_prompt: str
    video_prompt: str
    estimated_duration_seconds: int
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SceneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    narration_text: str | None = Field(default=None, min_length=1)
    overlay_text: str | None = Field(default=None, min_length=1)
    image_prompt: str | None = Field(default=None, min_length=1)
    video_prompt: str | None = Field(default=None, min_length=1)
    estimated_duration_seconds: int | None = Field(default=None, ge=1, le=120)
    notes: str | None = None


class ScriptGenerateRequest(BaseModel):
    source_feedback_notes: str | None = Field(default=None, max_length=5000)


class ProjectScriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    content_idea_id: UUID
    version_number: int
    status: ScriptStatus
    hook: str
    body: str
    cta: str
    full_script: str
    caption: str
    title_options: list[str]
    hashtags: list[str]
    estimated_duration_seconds: int
    source_feedback_notes: str | None
    created_at: datetime
    updated_at: datetime
    scenes: list[SceneResponse]


class ScenePromptPackResponse(BaseModel):
    scene_id: UUID
    scene_order: int
    title: str
    estimated_duration_seconds: int
    overlay_text: str
    narration_input: str
    narration_direction: str
    image_generation_prompt: str
    video_generation_prompt: str
    notes: str | None


class ScriptPromptPackResponse(BaseModel):
    script_id: UUID
    project_id: UUID
    brand_profile_id: UUID
    channel_name: str
    target_platform: str
    objective: str
    script_status: ScriptStatus
    version_number: int
    source_idea_title: str
    caption: str
    hashtags: list[str]
    title_options: list[str]
    scenes: list[ScenePromptPackResponse]


class AudioGenerationRequest(BaseModel):
    voice_label: str | None = Field(default=None, min_length=1, max_length=255)


class VisualGenerationRequest(BaseModel):
    scene_ids: list[UUID] | None = None


class BackgroundJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    script_id: UUID
    job_type: BackgroundJobType
    provider_name: ProviderName | None
    state: BackgroundJobState
    payload_json: dict[str, Any]
    attempts: int
    progress_percent: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    script_id: UUID
    scene_id: UUID | None
    generation_attempt_id: UUID | None
    asset_type: AssetType
    status: AssetStatus
    provider_name: ProviderName | None
    file_path: str | None
    mime_type: str | None
    duration_seconds: int | None
    width: int | None
    height: int | None
    checksum: str | None
    created_at: datetime
    updated_at: datetime
