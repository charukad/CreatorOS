from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from apps.api.core.config import get_settings
from apps.api.db.session import get_db
from apps.api.schemas.approvals import ApprovalDecisionRequest, ApprovalResponse
from apps.api.schemas.content_workflow import (
    AnalyticsSnapshotRequest,
    AnalyticsSnapshotResponse,
    AssetResponse,
    AudioGenerationRequest,
    BackgroundJobDetailResponse,
    BackgroundJobResponse,
    ContentIdeaResponse,
    GenerationAttemptResponse,
    IdeaApprovalRequest,
    IdeaGenerateRequest,
    InsightResponse,
    JobLogResponse,
    ManualInterventionRequest,
    ManualPublishCompleteRequest,
    ProjectActivityResponse,
    ProjectAnalyticsResponse,
    ProjectExportResponse,
    ProjectScriptResponse,
    PublishJobMetadataUpdateRequest,
    PublishJobPrepareRequest,
    PublishJobResponse,
    PublishJobScheduleRequest,
    SceneReorderRequest,
    SceneResponse,
    SceneUpdate,
    ScriptGenerateRequest,
    ScriptPromptPackResponse,
    VisualGenerationRequest,
)
from apps.api.schemas.enums import AssetType
from apps.api.services.analytics import list_project_analytics, sync_publish_job_analytics
from apps.api.services.approvals import list_project_approvals
from apps.api.services.assets import (
    approve_asset,
    approve_current_script_assets,
    get_asset,
    reject_asset,
    reject_current_script_assets,
    resolve_asset_file_path,
    stage_asset_rejection,
)
from apps.api.services.background_jobs import (
    cancel_background_job,
    get_owned_background_job,
    list_job_logs,
    list_job_related_assets,
    list_project_job_logs,
    mark_job_manual_intervention_required,
    retry_background_job,
)
from apps.api.services.content_workflow import (
    approve_content_idea,
    approve_project_script,
    build_script_prompt_pack,
    get_approved_content_idea,
    get_content_idea,
    get_current_script,
    get_project_script,
    get_scene,
    list_project_ideas,
    reject_content_idea,
    reject_project_script,
    reorder_script_scenes,
    update_scene,
)
from apps.api.services.generation_pipeline import (
    list_project_assets,
    list_project_background_jobs,
    queue_audio_generation_job,
    queue_visual_generation_job,
    submit_idea_generation_job,
    submit_script_generation_job,
)
from apps.api.services.media_pipeline import queue_rough_cut_job
from apps.api.services.project_events import create_project_event, list_project_events
from apps.api.services.project_export import (
    build_project_export_bundle,
    encode_project_export_bundle,
)
from apps.api.services.projects import get_owned_brand_profile, get_project
from apps.api.services.publishing import (
    approve_final_video,
    approve_publish_job,
    get_owned_publish_job,
    list_project_publish_jobs,
    mark_publish_job_published,
    prepare_publish_job,
    queue_publish_content_job,
    reject_final_video,
    schedule_publish_job,
    update_publish_job_metadata,
)
from apps.api.services.users import get_or_create_default_user

router = APIRouter(tags=["content-workflow"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/projects/{project_id}/ideas", response_model=list[ContentIdeaResponse])
def list_project_ideas_route(project_id: UUID, db: DbSession) -> list[ContentIdeaResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    ideas = list_project_ideas(db, project)
    return [ContentIdeaResponse.model_validate(idea) for idea in ideas]


@router.get("/projects/{project_id}/approvals", response_model=list[ApprovalResponse])
def list_project_approvals_route(project_id: UUID, db: DbSession) -> list[ApprovalResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    approvals = list_project_approvals(db, project)
    return [ApprovalResponse.model_validate(approval) for approval in approvals]


@router.get("/projects/{project_id}/activity", response_model=list[ProjectActivityResponse])
def list_project_activity_route(project_id: UUID, db: DbSession) -> list[ProjectActivityResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    approval_entries = [
        ProjectActivityResponse(
            source_id=approval.id,
            source_type="approval",
            activity_type=f"approval_{approval.decision.value}",
            title=(
                f"{_format_activity_label(approval.stage.value)} "
                f"{_format_activity_label(approval.decision.value)}"
            ),
            description=approval.feedback_notes,
            level="warning" if approval.decision.value == "rejected" else "info",
            metadata_json={
                "stage": approval.stage.value,
                "target_id": str(approval.target_id),
                "target_type": approval.target_type.value,
            },
            created_at=approval.created_at,
        )
        for approval in list_project_approvals(db, project)
    ]
    job_log_entries = [
        ProjectActivityResponse(
            source_id=job_log.id,
            source_type="job_log",
            activity_type=job_log.event_type,
            title=_format_activity_label(job_log.event_type),
            description=job_log.message,
            level=job_log.level,
            metadata_json={
                **job_log.metadata_json,
                "background_job_id": str(job_log.background_job_id),
                "generation_attempt_id": (
                    str(job_log.generation_attempt_id)
                    if job_log.generation_attempt_id is not None
                    else None
                ),
            },
            created_at=job_log.created_at,
        )
        for job_log in list_project_job_logs(db, project)
    ]
    project_event_entries = [
        ProjectActivityResponse(
            source_id=project_event.id,
            source_type="project_event",
            activity_type=project_event.event_type,
            title=project_event.title,
            description=project_event.description,
            level=project_event.level,
            metadata_json=project_event.metadata_json,
            created_at=project_event.created_at,
        )
        for project_event in list_project_events(db, project)
    ]

    activity = [*approval_entries, *job_log_entries, *project_event_entries]
    return sorted(activity, key=lambda entry: entry.created_at, reverse=True)[:80]


@router.get("/projects/{project_id}/export", response_model=ProjectExportResponse)
def export_project_route(project_id: UUID, db: DbSession) -> ProjectExportResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    bundle = encode_project_export_bundle(build_project_export_bundle(db, project))
    return ProjectExportResponse.model_validate(bundle)


@router.get("/projects/{project_id}/analytics", response_model=ProjectAnalyticsResponse)
def get_project_analytics_route(project_id: UUID, db: DbSession) -> ProjectAnalyticsResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    snapshots, insights = list_project_analytics(db, project)
    return ProjectAnalyticsResponse(
        snapshots=[AnalyticsSnapshotResponse.model_validate(snapshot) for snapshot in snapshots],
        insights=[InsightResponse.model_validate(insight) for insight in insights],
    )


@router.get("/projects/{project_id}/jobs", response_model=list[BackgroundJobResponse])
def list_project_jobs_route(project_id: UUID, db: DbSession) -> list[BackgroundJobResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    jobs = list_project_background_jobs(db, project)
    return [BackgroundJobResponse.model_validate(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=BackgroundJobDetailResponse)
def get_job_route(job_id: UUID, db: DbSession) -> BackgroundJobDetailResponse:
    user = get_or_create_default_user(db)
    job = get_owned_background_job(db, user, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return _job_detail_response(db, job)


@router.post("/jobs/{job_id}/cancel", response_model=BackgroundJobDetailResponse)
def cancel_job_route(job_id: UUID, db: DbSession) -> BackgroundJobDetailResponse:
    user = get_or_create_default_user(db)
    job = get_owned_background_job(db, user, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    try:
        cancelled_job = cancel_background_job(db, job)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return _job_detail_response(db, cancelled_job)


@router.post("/jobs/{job_id}/retry", response_model=BackgroundJobDetailResponse)
def retry_job_route(job_id: UUID, db: DbSession) -> BackgroundJobDetailResponse:
    user = get_or_create_default_user(db)
    job = get_owned_background_job(db, user, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    try:
        retried_job = retry_background_job(db, job)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return _job_detail_response(db, retried_job)


@router.post("/jobs/{job_id}/manual-intervention", response_model=BackgroundJobDetailResponse)
def mark_job_manual_intervention_route(
    job_id: UUID,
    payload: ManualInterventionRequest,
    db: DbSession,
) -> BackgroundJobDetailResponse:
    user = get_or_create_default_user(db)
    job = get_owned_background_job(db, user, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    try:
        updated_job = mark_job_manual_intervention_required(db, job, reason=payload.reason)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return _job_detail_response(db, updated_job)


@router.get("/projects/{project_id}/assets", response_model=list[AssetResponse])
def list_project_assets_route(project_id: UUID, db: DbSession) -> list[AssetResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    assets = list_project_assets(db, project)
    return [AssetResponse.model_validate(asset) for asset in assets]


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset_route(asset_id: UUID, db: DbSession) -> AssetResponse:
    user = get_or_create_default_user(db)
    asset = get_asset(db, user, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    return AssetResponse.model_validate(asset)


@router.post("/assets/{asset_id}/approve", response_model=ApprovalResponse)
def approve_asset_route(
    asset_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ApprovalResponse:
    user = get_or_create_default_user(db)
    asset = get_asset(db, user, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    project = get_project(db, user, asset.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        approval = approve_asset(
            db,
            user=user,
            project=project,
            asset=asset,
            feedback_notes=payload.feedback_notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ApprovalResponse.model_validate(approval)


@router.post("/assets/{asset_id}/reject", response_model=ApprovalResponse)
def reject_asset_route(
    asset_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ApprovalResponse:
    user = get_or_create_default_user(db)
    asset = get_asset(db, user, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    project = get_project(db, user, asset.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        approval = reject_asset(
            db,
            user=user,
            project=project,
            asset=asset,
            feedback_notes=payload.feedback_notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ApprovalResponse.model_validate(approval)


@router.post(
    "/assets/{asset_id}/regenerate",
    response_model=BackgroundJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def regenerate_asset_route(
    asset_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> BackgroundJobResponse:
    user = get_or_create_default_user(db)
    asset = get_asset(db, user, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    project = get_project(db, user, asset.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    script = get_project_script(db, user, asset.script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    current_script = get_current_script(db, project)
    if current_script is None or current_script.id != script.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only assets from the current script can be regenerated.",
        )

    if asset.asset_type not in {
        AssetType.NARRATION_AUDIO,
        AssetType.SCENE_IMAGE,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only narration and scene image assets can be regenerated.",
        )

    try:
        stage_asset_rejection(
            db,
            user=user,
            project=project,
            asset=asset,
            feedback_notes=payload.feedback_notes,
            allow_already_rejected=True,
        )
        create_project_event(
            db,
            project,
            event_type="asset_regeneration_requested",
            title="Asset regeneration requested",
            description=payload.feedback_notes,
            level="warning",
            metadata={
                "asset_id": str(asset.id),
                "asset_type": asset.asset_type.value,
                "scene_id": str(asset.scene_id) if asset.scene_id is not None else None,
            },
        )
        prompt_pack = _build_script_prompt_pack_for_route(
            db,
            user=user,
            project=project,
            script=script,
        )
        if asset.asset_type == AssetType.NARRATION_AUDIO:
            job = queue_audio_generation_job(
                db,
                user=user,
                project=project,
                script=script,
                prompt_pack=prompt_pack,
                payload=AudioGenerationRequest(),
            )
        else:
            if asset.scene_id is None:
                raise ValueError("Scene visual assets must include a scene id before regeneration.")

            job = queue_visual_generation_job(
                db,
                user=user,
                project=project,
                script=script,
                prompt_pack=prompt_pack,
                payload=VisualGenerationRequest(scene_ids=[asset.scene_id]),
            )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return BackgroundJobResponse.model_validate(job)


@router.get("/projects/{project_id}/publish-jobs", response_model=list[PublishJobResponse])
def list_project_publish_jobs_route(
    project_id: UUID,
    db: DbSession,
) -> list[PublishJobResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    publish_jobs = list_project_publish_jobs(db, project)
    return [PublishJobResponse.model_validate(publish_job) for publish_job in publish_jobs]


@router.get("/assets/{asset_id}/content")
def get_asset_content_route(asset_id: UUID, db: DbSession):
    user = get_or_create_default_user(db)
    asset = get_asset(db, user, asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    settings = get_settings()
    try:
        asset_path = resolve_asset_file_path(asset, settings.storage_root)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return FileResponse(asset_path, media_type=asset.mime_type)


@router.post("/projects/{project_id}/final-video/approve", response_model=ApprovalResponse)
def approve_final_video_route(
    project_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ApprovalResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    current_script = get_current_script(db, project)
    if current_script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    try:
        approval = approve_final_video(
            db,
            user=user,
            project=project,
            script=current_script,
            feedback_notes=payload.feedback_notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ApprovalResponse.model_validate(approval)


@router.post("/projects/{project_id}/final-video/reject", response_model=ApprovalResponse)
def reject_final_video_route(
    project_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ApprovalResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    current_script = get_current_script(db, project)
    if current_script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    try:
        approval = reject_final_video(
            db,
            user=user,
            project=project,
            script=current_script,
            feedback_notes=payload.feedback_notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ApprovalResponse.model_validate(approval)


@router.post(
    "/projects/{project_id}/ideas/generate",
    response_model=list[ContentIdeaResponse],
    status_code=status.HTTP_201_CREATED,
)
def generate_project_ideas_route(
    project_id: UUID,
    db: DbSession,
    payload: Annotated[IdeaGenerateRequest | None, Body()] = None,
) -> list[ContentIdeaResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    brand_profile = get_owned_brand_profile(db, user, project.brand_profile_id)
    if brand_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )

    try:
        ideas = submit_idea_generation_job(
            db,
            user=user,
            project=project,
            brand_profile=brand_profile,
            payload=payload or IdeaGenerateRequest(),
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return [ContentIdeaResponse.model_validate(idea) for idea in ideas]


@router.post("/ideas/{idea_id}/approve", response_model=ContentIdeaResponse)
def approve_idea_route(
    idea_id: UUID,
    payload: IdeaApprovalRequest,
    db: DbSession,
) -> ContentIdeaResponse:
    user = get_or_create_default_user(db)
    idea = get_content_idea(db, user, idea_id)
    if idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Idea not found")

    project = get_project(db, user, idea.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        approved_idea = approve_content_idea(db, user, project, idea, payload.feedback_notes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ContentIdeaResponse.model_validate(approved_idea)


@router.post("/ideas/{idea_id}/reject", response_model=ContentIdeaResponse)
def reject_idea_route(
    idea_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ContentIdeaResponse:
    user = get_or_create_default_user(db)
    idea = get_content_idea(db, user, idea_id)
    if idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Idea not found")

    project = get_project(db, user, idea.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        rejected_idea = reject_content_idea(db, user, project, idea, payload.feedback_notes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ContentIdeaResponse.model_validate(rejected_idea)


@router.get(
    "/projects/{project_id}/scripts/current",
    response_model=ProjectScriptResponse | None,
)
def get_current_project_script_route(
    project_id: UUID,
    db: DbSession,
) -> ProjectScriptResponse | None:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    script = get_current_script(db, project)
    return ProjectScriptResponse.model_validate(script) if script is not None else None


@router.get("/scripts/{script_id}/scenes", response_model=list[SceneResponse])
def list_script_scenes_route(script_id: UUID, db: DbSession) -> list[SceneResponse]:
    user = get_or_create_default_user(db)
    script = get_project_script(db, user, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    return [SceneResponse.model_validate(scene) for scene in script.scenes]


@router.get("/scripts/{script_id}/prompt-pack", response_model=ScriptPromptPackResponse)
def get_script_prompt_pack_route(script_id: UUID, db: DbSession) -> ScriptPromptPackResponse:
    user = get_or_create_default_user(db)
    script = get_project_script(db, user, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    project = get_project(db, user, script.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    brand_profile = get_owned_brand_profile(db, user, project.brand_profile_id)
    if brand_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )

    source_idea = get_content_idea(db, user, script.content_idea_id)
    if source_idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source idea not found")

    try:
        return build_script_prompt_pack(
            project=project,
            brand_profile=brand_profile,
            approved_idea=source_idea,
            script=script,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post(
    "/projects/{project_id}/generate/audio",
    response_model=BackgroundJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def queue_audio_generation_route(
    project_id: UUID,
    payload: AudioGenerationRequest,
    db: DbSession,
) -> BackgroundJobResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    current_script = get_current_script(db, project)
    if current_script is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate and approve a script before queueing narration.",
        )

    brand_profile = get_owned_brand_profile(db, user, project.brand_profile_id)
    if brand_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )

    source_idea = get_content_idea(db, user, current_script.content_idea_id)
    if source_idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source idea not found")

    try:
        prompt_pack = build_script_prompt_pack(
            project=project,
            brand_profile=brand_profile,
            approved_idea=source_idea,
            script=current_script,
        )
        job = queue_audio_generation_job(
            db,
            user=user,
            project=project,
            script=current_script,
            prompt_pack=prompt_pack,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return BackgroundJobResponse.model_validate(job)


@router.post(
    "/projects/{project_id}/generate/visuals",
    response_model=BackgroundJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def queue_visual_generation_route(
    project_id: UUID,
    payload: VisualGenerationRequest,
    db: DbSession,
) -> BackgroundJobResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    current_script = get_current_script(db, project)
    if current_script is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate and approve a script before queueing visual generation.",
        )

    brand_profile = get_owned_brand_profile(db, user, project.brand_profile_id)
    if brand_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )

    source_idea = get_content_idea(db, user, current_script.content_idea_id)
    if source_idea is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source idea not found")

    try:
        prompt_pack = build_script_prompt_pack(
            project=project,
            brand_profile=brand_profile,
            approved_idea=source_idea,
            script=current_script,
        )
        job = queue_visual_generation_job(
            db,
            user=user,
            project=project,
            script=current_script,
            prompt_pack=prompt_pack,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return BackgroundJobResponse.model_validate(job)


@router.post("/projects/{project_id}/assets/approve", response_model=ApprovalResponse)
def approve_project_assets_route(
    project_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ApprovalResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    current_script = get_current_script(db, project)
    if current_script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    try:
        approval = approve_current_script_assets(
            db,
            user=user,
            project=project,
            script=current_script,
            feedback_notes=payload.feedback_notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ApprovalResponse.model_validate(approval)


@router.post("/projects/{project_id}/assets/reject", response_model=ApprovalResponse)
def reject_project_assets_route(
    project_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ApprovalResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    current_script = get_current_script(db, project)
    if current_script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    try:
        approval = reject_current_script_assets(
            db,
            user=user,
            project=project,
            script=current_script,
            feedback_notes=payload.feedback_notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ApprovalResponse.model_validate(approval)


@router.post(
    "/projects/{project_id}/compose/rough-cut",
    response_model=BackgroundJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def queue_rough_cut_route(project_id: UUID, db: DbSession) -> BackgroundJobResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    current_script = get_current_script(db, project)
    if current_script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    try:
        job = queue_rough_cut_job(
            db,
            user=user,
            project=project,
            script=current_script,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return BackgroundJobResponse.model_validate(job)


@router.post(
    "/projects/{project_id}/publish-jobs/prepare",
    response_model=PublishJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def prepare_publish_job_route(
    project_id: UUID,
    payload: PublishJobPrepareRequest,
    db: DbSession,
) -> PublishJobResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    current_script = get_current_script(db, project)
    if current_script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    try:
        publish_job = prepare_publish_job(
            db,
            user=user,
            project=project,
            script=current_script,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return PublishJobResponse.model_validate(publish_job)


@router.post("/publish-jobs/{publish_job_id}/approve", response_model=PublishJobResponse)
def approve_publish_job_route(
    publish_job_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> PublishJobResponse:
    user = get_or_create_default_user(db)
    publish_job = get_owned_publish_job(db, user, publish_job_id)
    if publish_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publish job not found")

    project = get_project(db, user, publish_job.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        approved_job = approve_publish_job(
            db,
            user=user,
            project=project,
            publish_job=publish_job,
            feedback_notes=payload.feedback_notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return PublishJobResponse.model_validate(approved_job)


@router.patch("/publish-jobs/{publish_job_id}/metadata", response_model=PublishJobResponse)
def update_publish_job_metadata_route(
    publish_job_id: UUID,
    payload: PublishJobMetadataUpdateRequest,
    db: DbSession,
) -> PublishJobResponse:
    user = get_or_create_default_user(db)
    publish_job = get_owned_publish_job(db, user, publish_job_id)
    if publish_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publish job not found")

    project = get_project(db, user, publish_job.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        updated_job = update_publish_job_metadata(
            db,
            user=user,
            project=project,
            publish_job=publish_job,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return PublishJobResponse.model_validate(updated_job)


@router.post("/publish-jobs/{publish_job_id}/queue", response_model=BackgroundJobResponse)
def queue_publish_content_job_route(
    publish_job_id: UUID,
    db: DbSession,
) -> BackgroundJobResponse:
    user = get_or_create_default_user(db)
    publish_job = get_owned_publish_job(db, user, publish_job_id)
    if publish_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publish job not found")

    project = get_project(db, user, publish_job.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        job = queue_publish_content_job(db, project=project, publish_job=publish_job)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return BackgroundJobResponse.model_validate(job)


@router.post("/publish-jobs/{publish_job_id}/schedule", response_model=PublishJobResponse)
def schedule_publish_job_route(
    publish_job_id: UUID,
    payload: PublishJobScheduleRequest,
    db: DbSession,
) -> PublishJobResponse:
    user = get_or_create_default_user(db)
    publish_job = get_owned_publish_job(db, user, publish_job_id)
    if publish_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publish job not found")

    project = get_project(db, user, publish_job.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        scheduled_job = schedule_publish_job(
            db,
            project=project,
            publish_job=publish_job,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return PublishJobResponse.model_validate(scheduled_job)


@router.post("/publish-jobs/{publish_job_id}/mark-published", response_model=PublishJobResponse)
def mark_publish_job_published_route(
    publish_job_id: UUID,
    payload: ManualPublishCompleteRequest,
    db: DbSession,
) -> PublishJobResponse:
    user = get_or_create_default_user(db)
    publish_job = get_owned_publish_job(db, user, publish_job_id)
    if publish_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publish job not found")

    project = get_project(db, user, publish_job.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        published_job = mark_publish_job_published(
            db,
            project=project,
            publish_job=publish_job,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return PublishJobResponse.model_validate(published_job)


@router.post(
    "/publish-jobs/{publish_job_id}/sync-analytics",
    response_model=AnalyticsSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
def sync_publish_job_analytics_route(
    publish_job_id: UUID,
    payload: AnalyticsSnapshotRequest,
    db: DbSession,
) -> AnalyticsSnapshotResponse:
    user = get_or_create_default_user(db)
    publish_job = get_owned_publish_job(db, user, publish_job_id)
    if publish_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publish job not found")

    try:
        snapshot = sync_publish_job_analytics(db, publish_job=publish_job, payload=payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return AnalyticsSnapshotResponse.model_validate(snapshot)


@router.post(
    "/projects/{project_id}/scripts/generate",
    response_model=ProjectScriptResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_project_script_route(
    project_id: UUID,
    payload: ScriptGenerateRequest,
    db: DbSession,
) -> ProjectScriptResponse:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    brand_profile = get_owned_brand_profile(db, user, project.brand_profile_id)
    if brand_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand profile not found",
        )

    approved_idea = get_approved_content_idea(db, project)
    if approved_idea is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve an idea before generating a script.",
        )

    try:
        script = submit_script_generation_job(
            db,
            user=user,
            project=project,
            approved_idea=approved_idea,
            brand_profile=brand_profile,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ProjectScriptResponse.model_validate(script)


@router.post("/scripts/{script_id}/approve", response_model=ProjectScriptResponse)
def approve_script_route(
    script_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ProjectScriptResponse:
    user = get_or_create_default_user(db)
    script = get_project_script(db, user, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    project = get_project(db, user, script.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        approved_script = approve_project_script(db, user, project, script, payload.feedback_notes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ProjectScriptResponse.model_validate(approved_script)


@router.post("/scripts/{script_id}/reject", response_model=ProjectScriptResponse)
def reject_script_route(
    script_id: UUID,
    payload: ApprovalDecisionRequest,
    db: DbSession,
) -> ProjectScriptResponse:
    user = get_or_create_default_user(db)
    script = get_project_script(db, user, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    project = get_project(db, user, script.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        rejected_script = reject_project_script(db, user, project, script, payload.feedback_notes)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ProjectScriptResponse.model_validate(rejected_script)


@router.patch("/scenes/{scene_id}", response_model=SceneResponse)
def update_scene_route(
    scene_id: UUID,
    payload: SceneUpdate,
    db: DbSession,
) -> SceneResponse:
    user = get_or_create_default_user(db)
    scene = get_scene(db, user, scene_id)
    if scene is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")

    script = get_project_script(db, user, scene.script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    project = get_project(db, user, script.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        updated_scene = update_scene(
            db,
            project=project,
            script=script,
            scene=scene,
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return SceneResponse.model_validate(updated_scene)


@router.post("/scripts/{script_id}/scenes/reorder", response_model=ProjectScriptResponse)
def reorder_script_scenes_route(
    script_id: UUID,
    payload: SceneReorderRequest,
    db: DbSession,
) -> ProjectScriptResponse:
    user = get_or_create_default_user(db)
    script = get_project_script(db, user, script_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found")

    project = get_project(db, user, script.project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        reordered_script = reorder_script_scenes(
            db,
            project=project,
            script=script,
            scene_ids=payload.scene_ids,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    return ProjectScriptResponse.model_validate(reordered_script)


def _build_script_prompt_pack_for_route(
    db: Session,
    *,
    user,
    project,
    script,
) -> ScriptPromptPackResponse:
    brand_profile = get_owned_brand_profile(db, user, project.brand_profile_id)
    if brand_profile is None:
        raise ValueError("Brand profile not found.")

    source_idea = get_content_idea(db, user, script.content_idea_id)
    if source_idea is None:
        raise ValueError("Source idea not found.")

    return build_script_prompt_pack(
        project=project,
        brand_profile=brand_profile,
        approved_idea=source_idea,
        script=script,
    )


def _job_detail_response(db: Session, job) -> BackgroundJobDetailResponse:
    return BackgroundJobDetailResponse(
        job=BackgroundJobResponse.model_validate(job),
        generation_attempts=[
            GenerationAttemptResponse.model_validate(attempt) for attempt in job.generation_attempts
        ],
        related_assets=[
            AssetResponse.model_validate(asset) for asset in list_job_related_assets(db, job)
        ],
        job_logs=[JobLogResponse.model_validate(job_log) for job_log in list_job_logs(db, job)],
    )


def _format_activity_label(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()
