import re
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.generation_attempt import GenerationAttempt
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.user import User
from apps.api.schemas.content_workflow import (
    AudioGenerationRequest,
    ScenePromptPackResponse,
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
    statement = (
        select(Asset)
        .where(Asset.project_id == project.id)
        .order_by(desc(Asset.created_at))
    )
    return list(db.scalars(statement))


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
            "narration_segments": narration_segments,
        },
    )
    db.add(job)
    db.flush()

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
                f"script-v{script.version_number}-narration.wav",
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
                    f"scene-{scene.scene_order:02d}-{_slugify(scene.title)}.svg",
                ),
                mime_type="image/svg+xml",
                duration_seconds=scene.estimated_duration_seconds,
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
    }
    if project.status not in allowed_project_statuses:
        raise ValueError(
            "Generation jobs can only be queued while the project is in script approval "
            "or asset generation."
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
    raise ValueError(
        f"An active {job_label} generation job already exists for the current script."
    )


def _select_prompt_pack_scenes(
    scenes: list[ScenePromptPackResponse],
    selected_scene_ids: list[UUID] | None,
) -> list[ScenePromptPackResponse]:
    if selected_scene_ids is None:
        return scenes

    selected_ids = {str(scene_id) for scene_id in selected_scene_ids}
    return [scene for scene in scenes if str(scene.scene_id) in selected_ids]


def _promote_project_to_asset_generation(db: Session, project: Project) -> None:
    if project.status == ProjectStatus.SCRIPT_PENDING_APPROVAL:
        project.status = ProjectStatus.ASSET_GENERATION
        db.add(project)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "scene"
