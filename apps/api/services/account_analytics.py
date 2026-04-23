from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.analytics_snapshot import AnalyticsSnapshot
from apps.api.models.background_job import BackgroundJob
from apps.api.models.insight import Insight
from apps.api.models.project import Project
from apps.api.models.project_script import ProjectScript
from apps.api.models.publish_job import PublishJob
from apps.api.models.user import User
from apps.api.schemas.enums import BackgroundJobType

SummaryBuckets = dict[str, list[dict[str, object]]]


def build_account_analytics_summary(db: Session, user: User) -> dict[str, object]:
    rows = _latest_snapshot_rows(db, user)
    voice_labels = _latest_voice_labels_by_script(db, user)

    overview = _build_overview(rows)
    top_posts = [_post_response(row) for row in _sort_rows_by_engagement(rows)[:5]]
    grouped_rows = _build_summary_buckets(rows, voice_labels)
    recommendations = _latest_recommendations(db, user)

    return {
        "overview": overview,
        "top_posts": top_posts,
        "hook_patterns": _summarize_group(grouped_rows["hook_patterns"]),
        "duration_buckets": _summarize_group(grouped_rows["duration_buckets"]),
        "posting_windows": _summarize_group(grouped_rows["posting_windows"]),
        "voice_labels": _summarize_group(grouped_rows["voice_labels"]),
        "content_types": _summarize_group(grouped_rows["content_types"]),
        "recommendations": recommendations,
    }


def _latest_snapshot_rows(db: Session, user: User) -> list[dict[str, object]]:
    statement = (
        select(AnalyticsSnapshot, PublishJob, Project, ProjectScript)
        .join(PublishJob, AnalyticsSnapshot.publish_job_id == PublishJob.id)
        .join(Project, AnalyticsSnapshot.project_id == Project.id)
        .join(ProjectScript, PublishJob.script_id == ProjectScript.id)
        .where(AnalyticsSnapshot.user_id == user.id)
        .order_by(desc(AnalyticsSnapshot.fetched_at), desc(AnalyticsSnapshot.id))
    )

    rows: list[dict[str, object]] = []
    seen_publish_jobs: set[UUID] = set()
    for snapshot, publish_job, project, script in db.execute(statement).all():
        if publish_job.id in seen_publish_jobs:
            continue

        seen_publish_jobs.add(publish_job.id)
        rows.append(
            {
                "snapshot": snapshot,
                "publish_job": publish_job,
                "project": project,
                "script": script,
            }
        )

    return rows


def _latest_voice_labels_by_script(db: Session, user: User) -> dict[UUID, str]:
    statement = (
        select(BackgroundJob)
        .where(
            BackgroundJob.user_id == user.id,
            BackgroundJob.job_type == BackgroundJobType.GENERATE_AUDIO_BROWSER,
            BackgroundJob.script_id.is_not(None),
        )
        .order_by(desc(BackgroundJob.created_at), desc(BackgroundJob.id))
    )
    labels: dict[UUID, str] = {}
    for job in db.scalars(statement):
        if job.script_id is None or job.script_id in labels:
            continue

        voice_label = job.payload_json.get("voice_label") or "Default voice"
        labels[job.script_id] = str(voice_label)

    return labels


def _build_overview(rows: list[dict[str, object]]) -> dict[str, object]:
    published_posts = len(rows)
    total_views = sum(_snapshot(row).views for row in rows)
    total_engagements = sum(_engagement_actions(_snapshot(row)) for row in rows)
    average_engagement_rate = total_engagements / max(total_views, 1)
    average_view_duration = _average(
        [
            _snapshot(row).avg_view_duration
            for row in rows
            if _snapshot(row).avg_view_duration is not None
        ]
    )
    platform_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        platform_counts[_publish_job(row).platform] += 1

    top_platform = (
        max(platform_counts.items(), key=lambda item: (item[1], item[0]))[0]
        if platform_counts
        else None
    )

    return {
        "published_posts": published_posts,
        "total_views": total_views,
        "total_engagements": total_engagements,
        "average_engagement_rate": round(average_engagement_rate, 4),
        "average_view_duration": average_view_duration,
        "top_platform": top_platform,
    }


def _build_summary_buckets(
    rows: list[dict[str, object]],
    voice_labels: dict[UUID, str],
) -> SummaryBuckets:
    grouped_rows: SummaryBuckets = {
        "hook_patterns": [],
        "duration_buckets": [],
        "posting_windows": [],
        "voice_labels": [],
        "content_types": [],
    }

    for row in rows:
        publish_job = _publish_job(row)
        script = _script(row)
        posted_at = _posted_at(publish_job)

        grouped_rows["hook_patterns"].append(
            {"key": script.hook, "label": _truncate_label(script.hook), "row": row}
        )
        grouped_rows["duration_buckets"].append(
            {
                "key": _duration_bucket_key(script.estimated_duration_seconds),
                "label": _duration_bucket_label(script.estimated_duration_seconds),
                "row": row,
            }
        )
        grouped_rows["posting_windows"].append(
            {
                "key": f"{posted_at.strftime('%a').lower()}-{posted_at.hour:02d}",
                "label": f"{posted_at.strftime('%a')} around {posted_at.hour:02d}:00",
                "row": row,
            }
        )
        grouped_rows["voice_labels"].append(
            {
                "key": voice_labels.get(script.id, "Default voice"),
                "label": voice_labels.get(script.id, "Default voice"),
                "row": row,
            }
        )
        grouped_rows["content_types"].append(
            {
                "key": publish_job.platform,
                "label": publish_job.platform.replace("_", " ").title(),
                "row": row,
            }
        )

    return grouped_rows


def _summarize_group(items: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for item in items:
        key = str(item["key"])
        row = item["row"]
        assert isinstance(row, dict)
        snapshot = _snapshot(row)

        if key not in grouped:
            grouped[key] = {
                "key": key,
                "label": str(item["label"]),
                "publish_count": 0,
                "total_views": 0,
                "total_engagements": 0,
                "duration_values": [],
                "sample_project_id": str(_project(row).id),
                "sample_project_title": _project(row).title,
            }

        grouped_item = grouped[key]
        grouped_item["publish_count"] = int(grouped_item["publish_count"]) + 1
        grouped_item["total_views"] = int(grouped_item["total_views"]) + snapshot.views
        grouped_item["total_engagements"] = int(grouped_item["total_engagements"]) + (
            _engagement_actions(snapshot)
        )
        if snapshot.avg_view_duration is not None:
            duration_values = grouped_item["duration_values"]
            assert isinstance(duration_values, list)
            duration_values.append(snapshot.avg_view_duration)

    summaries: list[dict[str, object]] = []
    for grouped_item in grouped.values():
        total_views = int(grouped_item["total_views"])
        total_engagements = int(grouped_item["total_engagements"])
        duration_values = grouped_item.pop("duration_values")
        assert isinstance(duration_values, list)
        summaries.append(
            {
                **grouped_item,
                "average_engagement_rate": round(total_engagements / max(total_views, 1), 4),
                "average_view_duration": _average(
                    [float(value) for value in duration_values if value is not None]
                ),
            }
        )

    return sorted(
        summaries,
        key=lambda item: (
            int(item["publish_count"]),
            int(item["total_views"]),
            float(item["average_engagement_rate"]),
        ),
        reverse=True,
    )[:5]


def _latest_recommendations(db: Session, user: User) -> list[dict[str, object]]:
    statement = (
        select(Insight, Project)
        .join(Project, Insight.project_id == Project.id)
        .where(Insight.user_id == user.id)
        .order_by(desc(Insight.created_at), desc(Insight.confidence_score))
        .limit(5)
    )
    return [
        {
            "insight_id": str(insight.id),
            "project_id": str(project.id),
            "project_title": project.title,
            "insight_type": insight.insight_type,
            "summary": insight.summary,
            "confidence_score": insight.confidence_score,
            "created_at": insight.created_at.isoformat(),
        }
        for insight, project in db.execute(statement).all()
    ]


def _sort_rows_by_engagement(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            _engagement_rate(_snapshot(row)),
            _snapshot(row).views,
            _posted_at(_publish_job(row)),
        ),
        reverse=True,
    )


def _post_response(row: dict[str, object]) -> dict[str, object]:
    snapshot = _snapshot(row)
    publish_job = _publish_job(row)
    project = _project(row)
    script = _script(row)
    return {
        "project_id": str(project.id),
        "project_title": project.title,
        "publish_job_id": str(publish_job.id),
        "platform": publish_job.platform,
        "title": publish_job.title,
        "hook": script.hook,
        "duration_seconds": script.estimated_duration_seconds,
        "views": snapshot.views,
        "engagement_rate": round(_engagement_rate(snapshot), 4),
        "avg_view_duration": snapshot.avg_view_duration,
        "published_at": _posted_at(publish_job).isoformat(),
    }


def _snapshot(row: dict[str, object]) -> AnalyticsSnapshot:
    snapshot = row["snapshot"]
    assert isinstance(snapshot, AnalyticsSnapshot)
    return snapshot


def _publish_job(row: dict[str, object]) -> PublishJob:
    publish_job = row["publish_job"]
    assert isinstance(publish_job, PublishJob)
    return publish_job


def _project(row: dict[str, object]) -> Project:
    project = row["project"]
    assert isinstance(project, Project)
    return project


def _script(row: dict[str, object]) -> ProjectScript:
    script = row["script"]
    assert isinstance(script, ProjectScript)
    return script


def _engagement_actions(snapshot: AnalyticsSnapshot) -> int:
    return snapshot.likes + snapshot.comments + snapshot.shares + (snapshot.saves or 0)


def _engagement_rate(snapshot: AnalyticsSnapshot) -> float:
    return _engagement_actions(snapshot) / max(snapshot.views, 1)


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _duration_bucket_key(duration_seconds: int) -> str:
    if duration_seconds < 20:
        return "under_20s"
    if duration_seconds <= 34:
        return "20_to_34s"
    return "35s_plus"


def _duration_bucket_label(duration_seconds: int) -> str:
    if duration_seconds < 20:
        return "Under 20 seconds"
    if duration_seconds <= 34:
        return "20-34 seconds"
    return "35+ seconds"


def _posted_at(publish_job: PublishJob) -> datetime:
    return publish_job.scheduled_for or publish_job.updated_at or publish_job.created_at


def _truncate_label(value: str, *, limit: int = 90) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}..."
