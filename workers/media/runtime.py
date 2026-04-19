import hashlib
import json
import logging
from pathlib import Path
from uuid import UUID

from apps.api.db.session import SessionLocal
from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.schemas.enums import AssetStatus, AssetType, BackgroundJobType
from apps.api.services.background_jobs import (
    claim_next_media_job,
    mark_job_completed,
    mark_job_failed,
    mark_job_progress,
)
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from workers.media.config import MediaWorkerSettings
from workers.media.exporters.preview import build_rough_cut_preview_html
from workers.media.timeline.manifest import build_timeline_manifest

logger = logging.getLogger(__name__)

VISUAL_ASSET_TYPES = (AssetType.SCENE_IMAGE, AssetType.SCENE_VIDEO)


def run_pending_jobs(
    *,
    settings: MediaWorkerSettings,
    session_factory: sessionmaker[Session] = SessionLocal,
    max_jobs: int | None = None,
) -> int:
    processed_jobs = 0

    while max_jobs is None or processed_jobs < max_jobs:
        with session_factory() as session:
            job = claim_next_media_job(session)
            if job is None:
                return processed_jobs

            logger.info("Processing media job %s (%s)", job.id, job.job_type.value)

            try:
                _process_job(session, settings, job)
            except Exception as error:  # pragma: no cover - defensive logging path
                logger.exception("Media job %s failed", job.id)
                failed_job = session.get(BackgroundJob, job.id)
                if failed_job is not None:
                    mark_job_failed(session, failed_job, str(error))
                processed_jobs += 1
                continue

        processed_jobs += 1

    return processed_jobs


def _process_job(session: Session, settings: MediaWorkerSettings, job: BackgroundJob) -> None:
    if job.job_type != BackgroundJobType.COMPOSE_ROUGH_CUT:
        raise ValueError(f"Unsupported media job type: {job.job_type.value}")

    project = session.get(Project, job.project_id)
    if project is None:
        raise ValueError("Project not found for media job.")

    script = _get_script(session, job)
    output_asset = _get_output_asset(session, job)

    output_asset.status = AssetStatus.GENERATING
    session.add(output_asset)
    session.commit()
    mark_job_progress(session, job, 15)

    narration_asset = _select_latest_ready_asset(
        session,
        script=script,
        asset_types=(AssetType.NARRATION_AUDIO,),
    )
    if narration_asset is None:
        raise ValueError("A ready narration asset is required for rough-cut composition.")

    scene_assets = _select_scene_visual_assets(session, script)
    manifest = build_timeline_manifest(
        project=project,
        script=script,
        job=job,
        narration_asset=narration_asset,
        scene_assets=scene_assets,
    )
    mark_job_progress(session, job, 45)

    manifest_path = Path(str(job.payload_json["manifest_path"]))
    preview_path = Path(output_asset.file_path or str(job.payload_json["preview_path"]))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    preview_path.write_text(build_rough_cut_preview_html(manifest), encoding="utf-8")
    mark_job_progress(session, job, 80)

    output_asset.status = AssetStatus.READY
    output_asset.file_path = str(preview_path)
    output_asset.mime_type = "text/html"
    output_asset.duration_seconds = int(manifest["total_duration_seconds"])
    output_asset.width = 1080
    output_asset.height = 1920
    output_asset.checksum = _file_sha256(preview_path)

    job.payload_json = {
        **job.payload_json,
        "manifest_path": str(manifest_path),
        "preview_path": str(preview_path),
        "output_asset_id": str(output_asset.id),
        "total_duration_seconds": manifest["total_duration_seconds"],
    }
    session.add(output_asset)
    session.add(job)
    session.commit()
    session.refresh(job)

    mark_job_progress(session, job, 95)
    mark_job_completed(session, job)


def _get_script(session: Session, job: BackgroundJob) -> ProjectScript:
    statement = (
        select(ProjectScript)
        .options(selectinload(ProjectScript.scenes))
        .where(ProjectScript.id == job.script_id)
    )
    script = session.scalar(statement)
    if script is None:
        raise ValueError("Script not found for media job.")
    return script


def _get_output_asset(session: Session, job: BackgroundJob) -> Asset:
    output_asset_id = job.payload_json.get("output_asset_id")
    if output_asset_id is None:
        raise ValueError("Rough-cut job payload is missing output_asset_id.")

    output_asset = session.get(Asset, UUID(str(output_asset_id)))
    if output_asset is None:
        raise ValueError("Planned rough-cut asset not found for media job.")

    return output_asset


def _select_latest_ready_asset(
    session: Session,
    *,
    script: ProjectScript,
    asset_types: tuple[AssetType, ...],
) -> Asset | None:
    statement = (
        select(Asset)
        .where(
            Asset.script_id == script.id,
            Asset.status == AssetStatus.READY,
            Asset.asset_type.in_(asset_types),
        )
        .order_by(desc(Asset.updated_at), desc(Asset.created_at))
    )
    return session.scalar(statement)


def _select_scene_visual_assets(
    session: Session,
    script: ProjectScript,
) -> dict[str, Asset]:
    selected_assets: dict[str, Asset] = {}

    for scene in script.scenes:
        statement = (
            select(Asset)
            .where(
                Asset.script_id == script.id,
                Asset.scene_id == scene.id,
                Asset.status == AssetStatus.READY,
                Asset.asset_type.in_(VISUAL_ASSET_TYPES),
            )
            .order_by(desc(Asset.updated_at), desc(Asset.created_at))
        )
        scene_asset = session.scalar(statement)
        if scene_asset is None:
            raise ValueError(f"Scene {scene.scene_order} does not have a ready visual asset.")
        selected_assets[str(scene.id)] = scene_asset

    return selected_assets


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
