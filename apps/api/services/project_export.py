from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import asc, select
from sqlalchemy.orm import Session, selectinload

from apps.api.models.analytics_snapshot import AnalyticsSnapshot
from apps.api.models.approval import Approval
from apps.api.models.asset import Asset
from apps.api.models.background_job import BackgroundJob
from apps.api.models.content_idea import ContentIdea
from apps.api.models.idea_research_snapshot import IdeaResearchSnapshot
from apps.api.models.insight import Insight
from apps.api.models.project import Project
from apps.api.models.project_event import ProjectEvent
from apps.api.models.project_script import ProjectScript
from apps.api.models.publish_job import PublishJob


def build_project_export_bundle(db: Session, project: Project) -> dict[str, Any]:
    scripts = list(
        db.scalars(
            select(ProjectScript)
            .options(selectinload(ProjectScript.scenes))
            .where(ProjectScript.project_id == project.id)
            .order_by(asc(ProjectScript.version_number))
        )
    )
    jobs = list(
        db.scalars(
            select(BackgroundJob)
            .options(selectinload(BackgroundJob.job_logs))
            .where(BackgroundJob.project_id == project.id)
            .order_by(asc(BackgroundJob.created_at))
        )
    )

    return {
        "exported_at": datetime.now(UTC),
        "project": project,
        "brand_profile": project.brand_profile,
        "idea_research_snapshots": _list_by_project(db, IdeaResearchSnapshot, project),
        "ideas": _list_by_project(db, ContentIdea, project),
        "scripts": scripts,
        "approvals": _list_by_project(db, Approval, project),
        "assets": _list_by_project(db, Asset, project),
        "background_jobs": jobs,
        "publish_jobs": _list_by_project(db, PublishJob, project),
        "analytics_snapshots": _list_by_project(db, AnalyticsSnapshot, project),
        "insights": _list_by_project(db, Insight, project),
        "project_events": _list_by_project(db, ProjectEvent, project),
    }


def encode_project_export_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    return jsonable_encoder(bundle)


def _list_by_project(db: Session, model, project: Project) -> list:
    timestamp_column = getattr(model, "created_at", None)
    if timestamp_column is None:
        timestamp_column = getattr(model, "fetched_at", None)
    order_by = (
        [asc(model.id)]
        if timestamp_column is None
        else [asc(timestamp_column), asc(model.id)]
    )
    return list(
        db.scalars(
            select(model)
            .where(model.project_id == project.id)
            .order_by(*order_by)
        )
    )
