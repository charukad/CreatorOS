from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from apps.api.core.config import get_settings
from apps.api.db.session import get_db
from apps.api.schemas.approvals import ApprovalDecisionRequest, ApprovalResponse
from apps.api.schemas.content_workflow import (
    AssetResponse,
    AudioGenerationRequest,
    BackgroundJobDetailResponse,
    BackgroundJobResponse,
    ContentIdeaResponse,
    GenerationAttemptResponse,
    IdeaApprovalRequest,
    JobLogResponse,
    ProjectActivityResponse,
    ProjectScriptResponse,
    SceneResponse,
    SceneUpdate,
    ScriptGenerateRequest,
    ScriptPromptPackResponse,
    VisualGenerationRequest,
)
from apps.api.services.approvals import list_project_approvals
from apps.api.services.assets import (
    approve_current_script_assets,
    get_asset,
    reject_current_script_assets,
    resolve_asset_file_path,
)
from apps.api.services.background_jobs import (
    cancel_background_job,
    get_owned_background_job,
    list_job_logs,
    list_job_related_assets,
    list_project_job_logs,
    retry_background_job,
)
from apps.api.services.content_workflow import (
    approve_content_idea,
    approve_project_script,
    build_script_prompt_pack,
    generate_content_ideas,
    generate_project_script,
    get_approved_content_idea,
    get_content_idea,
    get_current_script,
    get_project_script,
    get_scene,
    list_project_ideas,
    reject_content_idea,
    reject_project_script,
    update_scene,
)
from apps.api.services.generation_pipeline import (
    list_project_assets,
    list_project_background_jobs,
    queue_audio_generation_job,
    queue_visual_generation_job,
)
from apps.api.services.media_pipeline import queue_rough_cut_job
from apps.api.services.projects import get_owned_brand_profile, get_project
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

    activity = [*approval_entries, *job_log_entries]
    return sorted(activity, key=lambda entry: entry.created_at, reverse=True)[:80]


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


@router.get("/projects/{project_id}/assets", response_model=list[AssetResponse])
def list_project_assets_route(project_id: UUID, db: DbSession) -> list[AssetResponse]:
    user = get_or_create_default_user(db)
    project = get_project(db, user, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    assets = list_project_assets(db, project)
    return [AssetResponse.model_validate(asset) for asset in assets]


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


@router.post(
    "/projects/{project_id}/ideas/generate",
    response_model=list[ContentIdeaResponse],
    status_code=status.HTTP_201_CREATED,
)
def generate_project_ideas_route(project_id: UUID, db: DbSession) -> list[ContentIdeaResponse]:
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
        ideas = generate_content_ideas(db, user, project, brand_profile)
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

    return build_script_prompt_pack(
        project=project,
        brand_profile=brand_profile,
        approved_idea=source_idea,
        script=script,
    )


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

    prompt_pack = build_script_prompt_pack(
        project=project,
        brand_profile=brand_profile,
        approved_idea=source_idea,
        script=current_script,
    )

    try:
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

    prompt_pack = build_script_prompt_pack(
        project=project,
        brand_profile=brand_profile,
        approved_idea=source_idea,
        script=current_script,
    )

    try:
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
        script = generate_project_script(db, user, project, approved_idea, brand_profile, payload)
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


def _job_detail_response(db: Session, job) -> BackgroundJobDetailResponse:
    return BackgroundJobDetailResponse(
        job=BackgroundJobResponse.model_validate(job),
        generation_attempts=[
            GenerationAttemptResponse.model_validate(attempt)
            for attempt in job.generation_attempts
        ],
        related_assets=[
            AssetResponse.model_validate(asset)
            for asset in list_job_related_assets(db, job)
        ],
        job_logs=[JobLogResponse.model_validate(job_log) for job_log in list_job_logs(db, job)],
    )


def _format_activity_label(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()
