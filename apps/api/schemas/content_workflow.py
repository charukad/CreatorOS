from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.schemas.enums import ContentIdeaStatus, ScriptStatus


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
