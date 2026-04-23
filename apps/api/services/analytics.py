from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.analytics_snapshot import AnalyticsSnapshot
from apps.api.models.background_job import BackgroundJob
from apps.api.models.insight import Insight
from apps.api.models.project import Project
from apps.api.models.publish_job import PublishJob
from apps.api.schemas.content_workflow import AnalyticsSnapshotRequest
from apps.api.schemas.enums import BackgroundJobState, BackgroundJobType, PublishJobStatus
from apps.api.services.background_jobs import create_job_log
from apps.api.services.project_events import create_project_event

ACTIVE_ANALYTICS_SYNC_STATES = {
    BackgroundJobState.QUEUED,
    BackgroundJobState.RUNNING,
    BackgroundJobState.WAITING_EXTERNAL,
}


def list_project_analytics(
    db: Session,
    project: Project,
) -> tuple[list[AnalyticsSnapshot], list[Insight]]:
    snapshots_statement = (
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.project_id == project.id)
        .order_by(desc(AnalyticsSnapshot.fetched_at))
    )
    insights_statement = (
        select(Insight).where(Insight.project_id == project.id).order_by(desc(Insight.created_at))
    )
    return list(db.scalars(snapshots_statement)), list(db.scalars(insights_statement))


def sync_publish_job_analytics(
    db: Session,
    *,
    publish_job: PublishJob,
    payload: AnalyticsSnapshotRequest,
    commit: bool = True,
) -> AnalyticsSnapshot:
    if publish_job.status != PublishJobStatus.PUBLISHED:
        raise ValueError("Analytics can only be synced after a publish job is marked published.")

    snapshot = AnalyticsSnapshot(
        user_id=publish_job.user_id,
        project_id=publish_job.project_id,
        publish_job_id=publish_job.id,
        views=payload.views,
        likes=payload.likes,
        comments=payload.comments,
        shares=payload.shares,
        saves=payload.saves,
        watch_time_seconds=payload.watch_time_seconds,
        ctr=payload.ctr,
        avg_view_duration=payload.avg_view_duration,
        retention_json=payload.retention_json,
    )
    db.add(snapshot)
    db.flush()

    for insight in _build_insights(publish_job, snapshot):
        db.add(insight)

    db.flush()
    if commit:
        db.commit()
        db.refresh(snapshot)
    return snapshot


def queue_publish_job_analytics_sync(
    db: Session,
    *,
    project: Project,
    publish_job: PublishJob,
    payload: AnalyticsSnapshotRequest,
) -> BackgroundJob:
    if publish_job.project_id != project.id:
        raise ValueError("The selected publish job does not belong to this project.")

    if publish_job.status != PublishJobStatus.PUBLISHED:
        raise ValueError("Analytics can only be synced after a publish job is marked published.")

    _ensure_no_active_analytics_sync_job(db, publish_job)

    correlation_id = str(uuid4())
    metrics_payload = payload.model_dump(mode="json")
    job = BackgroundJob(
        user_id=publish_job.user_id,
        project_id=publish_job.project_id,
        script_id=publish_job.script_id,
        job_type=BackgroundJobType.SYNC_ANALYTICS,
        provider_name=None,
        state=BackgroundJobState.QUEUED,
        payload_json={
            "job_type": BackgroundJobType.SYNC_ANALYTICS.value,
            "project_id": str(project.id),
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "metrics": metrics_payload,
            "correlation_id": correlation_id,
        },
    )
    db.add(job)
    db.flush()
    create_job_log(
        db,
        job,
        event_type="job_queued",
        message="Analytics sync job was queued.",
        metadata={
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "correlation_id": correlation_id,
            "views": payload.views,
        },
    )
    create_project_event(
        db,
        project,
        event_type="analytics_sync_queued",
        title="Analytics sync queued",
        description=publish_job.title,
        metadata={
            "background_job_id": str(job.id),
            "publish_job_id": str(publish_job.id),
            "platform": publish_job.platform,
            "correlation_id": correlation_id,
        },
    )
    db.commit()
    db.refresh(job)
    return job


def _build_insights(publish_job: PublishJob, snapshot: AnalyticsSnapshot) -> list[Insight]:
    insights: list[Insight] = []
    engagement_actions = (
        snapshot.likes + snapshot.comments + snapshot.shares + (snapshot.saves or 0)
    )
    engagement_rate = engagement_actions / max(snapshot.views, 1)

    if snapshot.views == 0:
        insights.append(
            _make_insight(
                publish_job,
                snapshot,
                insight_type="analytics_waiting_for_data",
                summary=(
                    "No views have been recorded yet, so CreatorOS should wait before "
                    "changing strategy."
                ),
                evidence={"views": snapshot.views},
                confidence_score=0.4,
            )
        )
        return insights

    if engagement_rate >= 0.08:
        summary = (
            "Engagement is strong for this post. Reuse the hook and topic framing in the next "
            "idea-generation pass."
        )
        confidence = 0.78
    elif engagement_rate <= 0.02:
        summary = (
            "Engagement is weak relative to views. The next script should strengthen the hook, "
            "proof point, or call to action."
        )
        confidence = 0.72
    else:
        summary = (
            "Engagement is moderate. Keep the topic direction, but test a sharper opening line "
            "or clearer visual contrast next time."
        )
        confidence = 0.62

    insights.append(
        _make_insight(
            publish_job,
            snapshot,
            insight_type="engagement_rate",
            summary=summary,
            evidence={
                "comments": snapshot.comments,
                "engagement_actions": engagement_actions,
                "engagement_rate": round(engagement_rate, 4),
                "likes": snapshot.likes,
                "saves": snapshot.saves,
                "shares": snapshot.shares,
                "views": snapshot.views,
            },
            confidence_score=confidence,
        )
    )

    if snapshot.avg_view_duration is not None:
        insights.append(
            _make_insight(
                publish_job,
                snapshot,
                insight_type="average_view_duration",
                summary=(
                    "Average view duration is now available. Use it to tune scene pacing and "
                    "rough-cut timing in future exports."
                ),
                evidence={"avg_view_duration": snapshot.avg_view_duration},
                confidence_score=0.58,
            )
        )

    return insights


def _make_insight(
    publish_job: PublishJob,
    snapshot: AnalyticsSnapshot,
    *,
    insight_type: str,
    summary: str,
    evidence: dict[str, object],
    confidence_score: float,
) -> Insight:
    return Insight(
        user_id=publish_job.user_id,
        project_id=publish_job.project_id,
        publish_job_id=publish_job.id,
        analytics_snapshot_id=snapshot.id,
        insight_type=insight_type,
        summary=summary,
        evidence_json=evidence,
        confidence_score=confidence_score,
    )


def _ensure_no_active_analytics_sync_job(db: Session, publish_job: PublishJob) -> None:
    statement = select(BackgroundJob).where(
        BackgroundJob.project_id == publish_job.project_id,
        BackgroundJob.script_id == publish_job.script_id,
        BackgroundJob.job_type == BackgroundJobType.SYNC_ANALYTICS,
        BackgroundJob.state.in_(ACTIVE_ANALYTICS_SYNC_STATES),
        BackgroundJob.payload_json["publish_job_id"].as_string() == str(publish_job.id),
    )
    existing_job = db.scalar(statement)
    if existing_job is not None:
        raise ValueError("An active analytics sync job already exists for this publish job.")
