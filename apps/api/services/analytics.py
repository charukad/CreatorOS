from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.analytics_snapshot import AnalyticsSnapshot
from apps.api.models.insight import Insight
from apps.api.models.project import Project
from apps.api.models.publish_job import PublishJob
from apps.api.schemas.content_workflow import AnalyticsSnapshotRequest
from apps.api.schemas.enums import PublishJobStatus


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
        select(Insight)
        .where(Insight.project_id == project.id)
        .order_by(desc(Insight.created_at))
    )
    return list(db.scalars(snapshots_statement)), list(db.scalars(insights_statement))


def sync_publish_job_analytics(
    db: Session,
    *,
    publish_job: PublishJob,
    payload: AnalyticsSnapshotRequest,
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

    db.commit()
    db.refresh(snapshot)
    return snapshot


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
