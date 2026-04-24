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
    ProjectStatus,
    ProviderName,
    PublishJobStatus,
    ScriptStatus,
)


class ContentIdeaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    topic: str
    suggested_title: str
    hook: str
    angle: str
    rationale: str
    score: int
    source_feedback_notes: str | None
    status: ContentIdeaStatus
    feedback_notes: str | None
    created_at: datetime
    updated_at: datetime


class IdeaGenerateRequest(BaseModel):
    source_feedback_notes: str | None = Field(default=None, max_length=5000)


class IdeaResearchGenerateRequest(BaseModel):
    focus_topic: str | None = Field(default=None, min_length=1, max_length=255)
    source_feedback_notes: str | None = Field(default=None, max_length=5000)


class IdeaResearchSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    focus_topic: str | None
    source_feedback_notes: str | None
    summary: str
    trend_observations_json: list[str]
    competitor_angles_json: list[str]
    posting_strategies_json: list[str]
    recommended_topics_json: list[str]
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


class SceneReorderRequest(BaseModel):
    scene_ids: list[UUID] = Field(min_length=1)


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
    brand_context: dict[str, Any]
    analytics_learning_context: dict[str, Any]
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


class PublishJobMetadataUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    hashtags: list[str] | None = None
    scheduled_for: datetime | None = None
    thumbnail_asset_id: UUID | None = None
    platform_settings: dict[str, Any] | None = None
    change_notes: str | None = Field(default=None, max_length=5000)


class ManualPublishCompleteRequest(BaseModel):
    external_post_id: str | None = Field(default=None, max_length=255)
    manual_publish_notes: str | None = Field(default=None, max_length=5000)


class ManualInterventionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class AnalyticsSnapshotRequest(BaseModel):
    views: int = Field(ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    saves: int | None = Field(default=None, ge=0)
    watch_time_seconds: int | None = Field(default=None, ge=0)
    ctr: float | None = Field(default=None, ge=0)
    avg_view_duration: float | None = Field(default=None, ge=0)
    retention_json: dict[str, Any] | None = None


class BackgroundJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    script_id: UUID | None
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


class RecoveryJobResponse(BaseModel):
    job: BackgroundJobResponse
    project_title: str
    project_status: ProjectStatus
    latest_log_event_type: str | None
    latest_log_message: str | None
    latest_log_created_at: datetime | None


class RecoveryLogResponse(BaseModel):
    id: UUID
    project_id: UUID
    project_title: str
    background_job_id: UUID
    generation_attempt_id: UUID | None
    event_type: str
    level: str
    message: str
    metadata_json: dict[str, Any]
    created_at: datetime


class OperationsRecoveryResponse(BaseModel):
    failed_jobs: list[RecoveryJobResponse]
    waiting_jobs: list[RecoveryJobResponse]
    stale_running_jobs: list[RecoveryJobResponse]
    quarantined_downloads: list[RecoveryLogResponse]
    duplicate_asset_warnings: list[RecoveryLogResponse]
    summary: dict[str, int]


class ArtifactRetentionCandidateResponse(BaseModel):
    asset_id: UUID
    project_id: UUID
    project_title: str
    script_id: UUID
    asset_type: AssetType
    status: AssetStatus
    file_path: str
    file_exists: bool
    size_bytes: int | None
    created_at: datetime
    updated_at: datetime
    reason: str
    recommended_action: str
    safe_to_cleanup: bool
    retention_manifest_path: str | None


class ArtifactRetentionSummaryResponse(BaseModel):
    candidate_count: int
    safe_candidate_count: int
    total_reclaimable_bytes: int


class ArtifactRetentionPlanResponse(BaseModel):
    candidates: list[ArtifactRetentionCandidateResponse]
    summary: ArtifactRetentionSummaryResponse


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


class AnalyticsSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    publish_job_id: UUID
    views: int
    likes: int
    comments: int
    shares: int
    saves: int | None
    watch_time_seconds: int | None
    ctr: float | None
    avg_view_duration: float | None
    retention_json: dict[str, Any] | None
    fetched_at: datetime


class InsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    publish_job_id: UUID
    analytics_snapshot_id: UUID
    insight_type: str
    summary: str
    evidence_json: dict[str, Any]
    confidence_score: float
    created_at: datetime


class ProjectAnalyticsResponse(BaseModel):
    snapshots: list[AnalyticsSnapshotResponse]
    insights: list[InsightResponse]


class AccountAnalyticsOverviewResponse(BaseModel):
    published_posts: int
    total_views: int
    total_engagements: int
    average_engagement_rate: float
    average_view_duration: float | None
    top_platform: str | None


class AccountAnalyticsPostResponse(BaseModel):
    project_id: UUID
    project_title: str
    publish_job_id: UUID
    platform: str
    title: str
    hook: str
    duration_seconds: int
    views: int
    engagement_rate: float
    avg_view_duration: float | None
    published_at: datetime


class AccountAnalyticsSummaryItemResponse(BaseModel):
    key: str
    label: str
    publish_count: int
    total_views: int
    total_engagements: int
    average_engagement_rate: float
    average_view_duration: float | None
    sample_project_id: UUID
    sample_project_title: str


class AccountAnalyticsRecommendationResponse(BaseModel):
    insight_id: UUID
    project_id: UUID
    project_title: str
    insight_type: str
    summary: str
    confidence_score: float
    created_at: datetime


class AccountAnalyticsResponse(BaseModel):
    overview: AccountAnalyticsOverviewResponse
    top_posts: list[AccountAnalyticsPostResponse]
    hook_patterns: list[AccountAnalyticsSummaryItemResponse]
    duration_buckets: list[AccountAnalyticsSummaryItemResponse]
    posting_windows: list[AccountAnalyticsSummaryItemResponse]
    voice_labels: list[AccountAnalyticsSummaryItemResponse]
    content_types: list[AccountAnalyticsSummaryItemResponse]
    recommendations: list[AccountAnalyticsRecommendationResponse]


class JobLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    script_id: UUID | None
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


class ProjectExportResponse(BaseModel):
    exported_at: datetime
    project: dict[str, Any]
    brand_profile: dict[str, Any]
    idea_research_snapshots: list[dict[str, Any]]
    ideas: list[dict[str, Any]]
    scripts: list[dict[str, Any]]
    approvals: list[dict[str, Any]]
    assets: list[dict[str, Any]]
    background_jobs: list[dict[str, Any]]
    publish_jobs: list[dict[str, Any]]
    analytics_snapshots: list[dict[str, Any]]
    insights: list[dict[str, Any]]
    project_events: list[dict[str, Any]]
