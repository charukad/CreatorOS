import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.brand_profile import BrandProfile
from apps.api.models.content_idea import ContentIdea
from apps.api.models.generation_attempt import GenerationAttempt
from apps.api.models.idea_research_snapshot import IdeaResearchSnapshot
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.user import User
from apps.api.schemas.content_workflow import (
    AudioGenerationRequest,
    IdeaGenerateRequest,
    IdeaResearchGenerateRequest,
    ScenePromptPackResponse,
    ScriptGenerateRequest,
    ScriptPromptPackResponse,
    VisualGenerationRequest,
)
from apps.api.schemas.enums import (
    AssetStatus,
    AssetType,
    BackgroundJobState,
    BackgroundJobType,
    ProjectStatus,
    ProviderName,
    ScriptStatus,
)
from apps.api.services.background_jobs import create_job_log, mark_job_completed, mark_job_failed
from apps.api.services.content_workflow import generate_content_ideas, generate_project_script
from apps.api.services.idea_research import (
    build_idea_research_context,
    generate_idea_research_snapshot,
    get_latest_project_idea_research_snapshot,
)
from apps.api.services.learning_context import build_analytics_learning_context
from apps.api.services.project_events import create_project_event
from apps.api.services.storage_paths import build_project_storage_path

ACTIVE_JOB_STATES = {
    BackgroundJobState.QUEUED,
    BackgroundJobState.RUNNING,
    BackgroundJobState.WAITING_EXTERNAL,
}


def list_project_background_jobs(db: Session, project: Project) -> list[BackgroundJob]:
    statement = (
        select(BackgroundJob)
        .where(BackgroundJob.project_id == project.id)
        .order_by(desc(BackgroundJob.created_at))
    )
    return list(db.scalars(statement))


def list_project_assets(db: Session, project: Project) -> list[Asset]:
    statement = select(Asset).where(Asset.project_id == project.id).order_by(desc(Asset.created_at))
    return list(db.scalars(statement))


def submit_idea_research_job(
    db: Session,
    *,
    user: User,
    project: Project,
    brand_profile: BrandProfile,
    payload: IdeaResearchGenerateRequest,
) -> IdeaResearchSnapshot:
    _ensure_no_active_project_level_job(db, project, BackgroundJobType.GENERATE_IDEA_RESEARCH)
    analytics_learning_context = build_analytics_learning_context(
        db,
        user=user,
        project=project,
        brand_profile=brand_profile,
    )
    job = _create_inline_generation_job(
        db,
        user=user,
        project=project,
        script=None,
        job_type=BackgroundJobType.GENERATE_IDEA_RESEARCH,
        payload={
            "brand_profile_id": str(brand_profile.id),
            "target_platform": project.target_platform,
            "objective": project.objective,
            "focus_topic": payload.focus_topic,
            "source_feedback_notes": payload.source_feedback_notes,
            "analytics_learning_context": analytics_learning_context,
        },
        queued_message="Idea research job was submitted.",
    )

    try:
        _mark_inline_generation_job_running(
            db,
            job,
            message="Local idea research generation started.",
        )
        snapshot = generate_idea_research_snapshot(
            db,
            user,
            project,
            brand_profile,
            payload,
            analytics_learning_context=analytics_learning_context,
        )
        completed_job = _reload_job(db, job)
        completed_job.payload_json = {
            **completed_job.payload_json,
            "research_snapshot_id": str(snapshot.id),
        }
        db.add(completed_job)
        create_job_log(
            db,
            completed_job,
            event_type="idea_research_generated",
            message="Generated a persisted idea research snapshot.",
            metadata={
                "research_snapshot_id": str(snapshot.id),
                "focus_topic": snapshot.focus_topic,
            },
        )
        create_project_event(
            db,
            project,
            event_type="idea_research_generated",
            title="Idea research refreshed",
            description=snapshot.summary,
            metadata={
                "research_snapshot_id": str(snapshot.id),
                "focus_topic": snapshot.focus_topic,
            },
        )
        mark_job_completed(db, completed_job)
        return snapshot
    except Exception as error:
        mark_job_failed(db, _reload_job(db, job), str(error))
        raise


def submit_idea_generation_job(
    db: Session,
    *,
    user: User,
    project: Project,
    brand_profile: BrandProfile,
    payload: IdeaGenerateRequest,
) -> list[ContentIdea]:
    _ensure_no_active_project_level_job(db, project, BackgroundJobType.GENERATE_IDEAS)
    analytics_learning_context = build_analytics_learning_context(
        db,
        user=user,
        project=project,
        brand_profile=brand_profile,
    )
    latest_research_snapshot = get_latest_project_idea_research_snapshot(db, project)
    idea_research_context = build_idea_research_context(latest_research_snapshot)
    job = _create_inline_generation_job(
        db,
        user=user,
        project=project,
        script=None,
        job_type=BackgroundJobType.GENERATE_IDEAS,
        payload={
            "brand_profile_id": str(brand_profile.id),
            "target_platform": project.target_platform,
            "objective": project.objective,
            "research_snapshot_id": (
                str(latest_research_snapshot.id) if latest_research_snapshot is not None else None
            ),
            "source_feedback_notes": payload.source_feedback_notes,
            "idea_research_context": idea_research_context,
            "analytics_learning_context": analytics_learning_context,
        },
        queued_message="Idea generation job was submitted.",
    )

    try:
        _mark_inline_generation_job_running(
            db,
            job,
            message="Local idea generation started.",
        )
        ideas = generate_content_ideas(
            db,
            user,
            project,
            brand_profile,
            idea_research_context=idea_research_context,
            source_feedback_notes=payload.source_feedback_notes,
            analytics_learning_context=analytics_learning_context,
        )
        completed_job = _reload_job(db, job)
        completed_job.payload_json = {
            **completed_job.payload_json,
            "idea_count": len(ideas),
            "idea_ids": [str(idea.id) for idea in ideas],
        }
        db.add(completed_job)
        create_job_log(
            db,
            completed_job,
            event_type="content_ideas_generated",
            message=f"Generated {len(ideas)} content ideas for review.",
            metadata={"idea_count": len(ideas)},
        )
        mark_job_completed(db, completed_job)
        return ideas
    except Exception as error:
        mark_job_failed(db, _reload_job(db, job), str(error))
        raise


def submit_script_generation_job(
    db: Session,
    *,
    user: User,
    project: Project,
    approved_idea: ContentIdea,
    brand_profile: BrandProfile,
    payload: ScriptGenerateRequest,
) -> ProjectScript:
    _ensure_no_active_project_level_job(db, project, BackgroundJobType.GENERATE_SCRIPT)
    analytics_learning_context = build_analytics_learning_context(
        db,
        user=user,
        project=project,
        brand_profile=brand_profile,
    )
    job = _create_inline_generation_job(
        db,
        user=user,
        project=project,
        script=None,
        job_type=BackgroundJobType.GENERATE_SCRIPT,
        payload={
            "approved_idea_id": str(approved_idea.id),
            "brand_profile_id": str(brand_profile.id),
            "source_feedback_notes": payload.source_feedback_notes,
            "analytics_learning_context": analytics_learning_context,
        },
        queued_message="Script generation job was submitted.",
    )

    try:
        _mark_inline_generation_job_running(
            db,
            job,
            message="Local script and scene-plan generation started.",
        )
        script = generate_project_script(
            db,
            user,
            project,
            approved_idea,
            brand_profile,
            payload,
            analytics_learning_context=analytics_learning_context,
        )
        completed_job = _reload_job(db, job)
        completed_job.script_id = script.id
        completed_job.payload_json = {
            **completed_job.payload_json,
            "script_id": str(script.id),
            "script_version": script.version_number,
            "scene_count": len(script.scenes),
        }
        db.add(completed_job)
        create_job_log(
            db,
            completed_job,
            event_type="script_generated",
            message=(
                f"Generated script version {script.version_number} with "
                f"{len(script.scenes)} scenes."
            ),
            metadata={
                "script_id": str(script.id),
                "script_version": script.version_number,
                "scene_count": len(script.scenes),
            },
        )
        mark_job_completed(db, completed_job)
        return script
    except Exception as error:
        mark_job_failed(db, _reload_job(db, job), str(error))
        raise


def queue_audio_generation_job(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript,
    prompt_pack: ScriptPromptPackResponse,
    payload: AudioGenerationRequest,
) -> BackgroundJob:
    _validate_generation_queue(project, script)
    _ensure_no_active_job(db, project, script, BackgroundJobType.GENERATE_AUDIO_BROWSER)
    correlation_id = str(uuid4())

    narration_segments = [
        {
            "scene_id": str(scene.scene_id),
            "scene_order": scene.scene_order,
            "title": scene.title,
            "narration_input": scene.narration_input,
            "narration_direction": scene.narration_direction,
            "estimated_duration_seconds": scene.estimated_duration_seconds,
        }
        for scene in prompt_pack.scenes
    ]

    job = BackgroundJob(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id,
        job_type=BackgroundJobType.GENERATE_AUDIO_BROWSER,
        provider_name=ProviderName.ELEVENLABS_WEB,
        state=BackgroundJobState.QUEUED,
        payload_json={
            "script_id": str(script.id),
            "script_version": script.version_number,
            "voice_label": payload.voice_label,
            "estimated_duration_seconds": script.estimated_duration_seconds,
            "scene_count": len(narration_segments),
            "correlation_id": correlation_id,
            "narration_segments": narration_segments,
        },
    )
    db.add(job)
    db.flush()
    create_job_log(
        db,
        job,
        event_type="job_queued",
        message="Narration browser generation job was queued.",
        metadata={
            "scene_count": len(narration_segments),
            "voice_label": payload.voice_label,
            "correlation_id": correlation_id,
        },
    )

    attempt = GenerationAttempt(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id,
        background_job_id=job.id,
        scene_id=None,
        provider_name=ProviderName.ELEVENLABS_WEB,
        state=BackgroundJobState.QUEUED,
        input_payload_json={
            "script_id": str(script.id),
            "voice_label": payload.voice_label,
            "full_script": script.full_script,
            "narration_segments": narration_segments,
        },
    )
    db.add(attempt)
    db.flush()

    db.add(
        Asset(
            user_id=user.id,
            project_id=project.id,
            script_id=script.id,
            scene_id=None,
            generation_attempt_id=attempt.id,
            asset_type=AssetType.NARRATION_AUDIO,
            status=AssetStatus.PLANNED,
            provider_name=ProviderName.ELEVENLABS_WEB,
            file_path=build_project_storage_path(
                project.id,
                "audio",
                f"script-v{script.version_number}-attempt-{attempt.id.hex[:8]}-narration.wav",
            ),
            mime_type="audio/wav",
            duration_seconds=script.estimated_duration_seconds,
        )
    )

    _promote_project_to_asset_generation(db, project)
    db.commit()
    db.refresh(job)
    return job


def queue_visual_generation_job(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript,
    prompt_pack: ScriptPromptPackResponse,
    payload: VisualGenerationRequest,
) -> BackgroundJob:
    _validate_generation_queue(project, script)
    _ensure_no_active_job(db, project, script, BackgroundJobType.GENERATE_VISUALS_BROWSER)
    correlation_id = str(uuid4())

    selected_scenes = _select_prompt_pack_scenes(prompt_pack.scenes, payload.scene_ids)
    if not selected_scenes:
        raise ValueError("Select at least one scene before queueing visual generation.")

    job = BackgroundJob(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id,
        job_type=BackgroundJobType.GENERATE_VISUALS_BROWSER,
        provider_name=ProviderName.FLOW_WEB,
        state=BackgroundJobState.QUEUED,
        payload_json={
            "script_id": str(script.id),
            "script_version": script.version_number,
            "scene_count": len(selected_scenes),
            "correlation_id": correlation_id,
            "scene_ids": [str(scene.scene_id) for scene in selected_scenes],
            "scenes": [
                {
                    "scene_id": str(scene.scene_id),
                    "scene_order": scene.scene_order,
                    "title": scene.title,
                    "estimated_duration_seconds": scene.estimated_duration_seconds,
                    "image_generation_prompt": scene.image_generation_prompt,
                    "video_generation_prompt": scene.video_generation_prompt,
                }
                for scene in selected_scenes
            ],
        },
    )
    db.add(job)
    db.flush()
    create_job_log(
        db,
        job,
        event_type="job_queued",
        message="Visual browser generation job was queued.",
        metadata={
            "scene_count": len(selected_scenes),
            "scene_ids": [str(scene.scene_id) for scene in selected_scenes],
            "correlation_id": correlation_id,
        },
    )

    for scene in selected_scenes:
        attempt = GenerationAttempt(
            user_id=user.id,
            project_id=project.id,
            script_id=script.id,
            background_job_id=job.id,
            scene_id=scene.scene_id,
            provider_name=ProviderName.FLOW_WEB,
            state=BackgroundJobState.QUEUED,
            input_payload_json={
                "scene_id": str(scene.scene_id),
                "scene_order": scene.scene_order,
                "title": scene.title,
                "image_generation_prompt": scene.image_generation_prompt,
                "video_generation_prompt": scene.video_generation_prompt,
                "estimated_duration_seconds": scene.estimated_duration_seconds,
            },
        )
        db.add(attempt)
        db.flush()

        db.add(
            Asset(
                user_id=user.id,
                project_id=project.id,
                script_id=script.id,
                scene_id=scene.scene_id,
                generation_attempt_id=attempt.id,
                asset_type=AssetType.SCENE_IMAGE,
                status=AssetStatus.PLANNED,
                provider_name=ProviderName.FLOW_WEB,
                file_path=build_project_storage_path(
                    project.id,
                    "scenes",
                    (
                        f"scene-{scene.scene_order:02d}-{_slugify(scene.title)}-"
                        f"attempt-{attempt.id.hex[:8]}.svg"
                    ),
                ),
                mime_type="image/svg+xml",
                duration_seconds=scene.estimated_duration_seconds,
                width=1080,
                height=1920,
            )
        )

    _promote_project_to_asset_generation(db, project)
    db.commit()
    db.refresh(job)
    return job


def _validate_generation_queue(project: Project, script: ProjectScript) -> None:
    allowed_project_statuses = {
        ProjectStatus.SCRIPT_PENDING_APPROVAL,
        ProjectStatus.ASSET_GENERATION,
        ProjectStatus.ASSET_PENDING_APPROVAL,
    }
    if project.status not in allowed_project_statuses:
        raise ValueError(
            "Generation jobs can only be queued while the project is in script approval "
            "asset generation, or asset review."
        )

    if script.project_id != project.id:
        raise ValueError("The selected script does not belong to this project.")

    if script.status != ScriptStatus.APPROVED:
        raise ValueError("Generation jobs require the current script to be approved.")


def _ensure_no_active_job(
    db: Session,
    project: Project,
    script: ProjectScript,
    job_type: BackgroundJobType,
) -> None:
    statement = select(BackgroundJob).where(
        BackgroundJob.project_id == project.id,
        BackgroundJob.script_id == script.id,
        BackgroundJob.job_type == job_type,
        BackgroundJob.state.in_(ACTIVE_JOB_STATES),
    )
    existing_job = db.scalar(statement)
    if existing_job is None:
        return

    job_label = "audio" if job_type == BackgroundJobType.GENERATE_AUDIO_BROWSER else "visual"
    raise ValueError(f"An active {job_label} generation job already exists for the current script.")


def _ensure_no_active_project_level_job(
    db: Session,
    project: Project,
    job_type: BackgroundJobType,
) -> None:
    statement = select(BackgroundJob).where(
        BackgroundJob.project_id == project.id,
        BackgroundJob.job_type == job_type,
        BackgroundJob.state.in_(ACTIVE_JOB_STATES),
    )
    existing_job = db.scalar(statement)
    if existing_job is None:
        return

    raise ValueError("An active project-level generation job already exists for this project.")


def _create_inline_generation_job(
    db: Session,
    *,
    user: User,
    project: Project,
    script: ProjectScript | None,
    job_type: BackgroundJobType,
    payload: dict[str, object],
    queued_message: str,
) -> BackgroundJob:
    correlation_id = str(uuid4())
    job = BackgroundJob(
        user_id=user.id,
        project_id=project.id,
        script_id=script.id if script is not None else None,
        job_type=job_type,
        provider_name=None,
        state=BackgroundJobState.QUEUED,
        payload_json={
            **payload,
            "job_type": job_type.value,
            "project_id": str(project.id),
            "execution_mode": "inline_local",
            "correlation_id": correlation_id,
        },
    )
    db.add(job)
    db.flush()
    create_job_log(
        db,
        job,
        event_type="job_queued",
        message=queued_message,
        metadata={
            "correlation_id": correlation_id,
            "execution_mode": "inline_local",
        },
    )
    db.commit()
    db.refresh(job)
    return job


def _mark_inline_generation_job_running(
    db: Session,
    job: BackgroundJob,
    *,
    message: str,
) -> None:
    now = datetime.now(UTC)
    job.state = BackgroundJobState.RUNNING
    job.attempts += 1
    job.progress_percent = max(job.progress_percent, 10)
    job.started_at = now
    job.error_message = None
    db.add(job)
    create_job_log(
        db,
        job,
        event_type="job_started",
        message=message,
        metadata={"execution_mode": "inline_local"},
    )
    db.commit()
    db.refresh(job)


def _reload_job(db: Session, job: BackgroundJob) -> BackgroundJob:
    refreshed_job = db.get(BackgroundJob, job.id)
    if refreshed_job is None:
        raise RuntimeError("Generation job disappeared before completion.")
    return refreshed_job


def _select_prompt_pack_scenes(
    scenes: list[ScenePromptPackResponse],
    selected_scene_ids: list[UUID] | None,
) -> list[ScenePromptPackResponse]:
    if selected_scene_ids is None:
        return scenes

    selected_ids = {str(scene_id) for scene_id in selected_scene_ids}
    return [scene for scene in scenes if str(scene.scene_id) in selected_ids]


def _promote_project_to_asset_generation(db: Session, project: Project) -> None:
    if project.status in {
        ProjectStatus.SCRIPT_PENDING_APPROVAL,
        ProjectStatus.ASSET_PENDING_APPROVAL,
    }:
        project.status = ProjectStatus.ASSET_GENERATION
        db.add(project)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "scene"
