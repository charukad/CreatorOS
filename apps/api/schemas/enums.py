from enum import StrEnum


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    IDEA_PENDING_APPROVAL = "idea_pending_approval"
    SCRIPT_PENDING_APPROVAL = "script_pending_approval"
    ASSET_GENERATION = "asset_generation"
    ASSET_PENDING_APPROVAL = "asset_pending_approval"
    ROUGH_CUT_READY = "rough_cut_ready"
    FINAL_PENDING_APPROVAL = "final_pending_approval"
    READY_TO_PUBLISH = "ready_to_publish"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    ARCHIVED = "archived"


class ApprovalStage(StrEnum):
    IDEA = "idea"
    SCRIPT = "script"
    ASSETS = "assets"
    FINAL_VIDEO = "final_video"
    PUBLISH = "publish"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalTargetType(StrEnum):
    CONTENT_IDEA = "content_idea"
    SCRIPT = "script"
    ASSET = "asset"
    PUBLISH_JOB = "publish_job"


class ContentIdeaStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class ScriptStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class AssetType(StrEnum):
    SCRIPT_DOC = "script_doc"
    NARRATION_AUDIO = "narration_audio"
    SCENE_IMAGE = "scene_image"
    SCENE_VIDEO = "scene_video"
    ROUGH_CUT = "rough_cut"
    FINAL_VIDEO = "final_video"
    SUBTITLE_FILE = "subtitle_file"
    THUMBNAIL = "thumbnail"


class AssetStatus(StrEnum):
    PLANNED = "planned"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    REJECTED = "rejected"


class ProviderName(StrEnum):
    ELEVENLABS_WEB = "elevenlabs_web"
    FLOW_WEB = "flow_web"
    LOCAL_MEDIA = "local_media"


class BackgroundJobType(StrEnum):
    GENERATE_IDEAS = "generate_ideas"
    GENERATE_SCRIPT = "generate_script"
    GENERATE_AUDIO_BROWSER = "generate_audio_browser"
    GENERATE_VISUALS_BROWSER = "generate_visuals_browser"
    COMPOSE_ROUGH_CUT = "compose_rough_cut"


class BackgroundJobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PublishJobStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"
