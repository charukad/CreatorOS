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
    PublishJobStatus,
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


class PublishJobPrepareRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    hashtags: list[str] = Field(default_factory=list)
    scheduled_for: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class PublishJobScheduleRequest(BaseModel):
    scheduled_for: datetime


class ManualPublishCompleteRequest(BaseModel):
    external_post_id: str | None = Field(default=None, max_length=255)
    manual_publish_notes: str | None = Field(default=None, max_length=5000)


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


class GenerationAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    script_id: UUID
    background_job_id: UUID
    scene_id: UUID | None
    provider_name: ProviderName
    state: BackgroundJobState
    input_payload_json: dict[str, Any]
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


class PublishJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    script_id: UUID
    final_asset_id: UUID
    platform: str
    title: str
    description: str
    hashtags_json: list[str]
    scheduled_for: datetime | None
    status: PublishJobStatus
    idempotency_key: str | None
    external_post_id: str | None
    manual_publish_notes: str | None
    error_message: str | None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class JobLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    script_id: UUID
    background_job_id: UUID
    generation_attempt_id: UUID | None
    level: str
    event_type: str
    message: str
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class BackgroundJobDetailResponse(BaseModel):
    job: BackgroundJobResponse
    generation_attempts: list[GenerationAttemptResponse]
    related_assets: list[AssetResponse]
    job_logs: list[JobLogResponse]


class ProjectActivityResponse(BaseModel):
    source_id: UUID
    source_type: str
    activity_type: str
    title: str
    description: str | None
    level: str
    metadata_json: dict[str, Any]
    created_at: datetime
