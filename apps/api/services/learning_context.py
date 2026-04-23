from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.brand_profile import BrandProfile
from apps.api.models.insight import Insight
from apps.api.models.project import Project
from apps.api.models.user import User

MAX_LEARNING_CONTEXT_ITEMS = 5


def build_analytics_learning_context(
    db: Session,
    *,
    user: User,
    project: Project,
    brand_profile: BrandProfile,
    limit: int = MAX_LEARNING_CONTEXT_ITEMS,
) -> dict[str, object]:
    statement = (
        select(Insight, Project)
        .join(Project, Insight.project_id == Project.id)
        .where(
            Insight.user_id == user.id,
            Project.brand_profile_id == brand_profile.id,
        )
        .order_by(desc(Insight.created_at), desc(Insight.confidence_score))
        .limit(limit)
    )

    items = [
        {
            "insight_id": str(insight.id),
            "source_project_id": str(source_project.id),
            "source_project_title": source_project.title,
            "is_current_project": source_project.id == project.id,
            "publish_job_id": str(insight.publish_job_id),
            "analytics_snapshot_id": str(insight.analytics_snapshot_id),
            "insight_type": insight.insight_type,
            "summary": insight.summary,
            "evidence": insight.evidence_json,
            "confidence_score": insight.confidence_score,
            "created_at": insight.created_at.isoformat(),
        }
        for insight, source_project in db.execute(statement).all()
    ]
    guidance = [_format_learning_guidance(item) for item in items]

    return {
        "available": bool(items),
        "brand_profile_id": str(brand_profile.id),
        "target_project_id": str(project.id),
        "source_count": len(items),
        "guidance": guidance,
        "items": items,
    }


def summarize_analytics_learning_context(
    learning_context: dict[str, object] | None,
    *,
    max_items: int = 2,
) -> str | None:
    if not learning_context or not learning_context.get("available"):
        return None

    guidance = learning_context.get("guidance")
    if not isinstance(guidance, list):
        return None

    selected_guidance = [str(item) for item in guidance[:max_items] if item]
    if not selected_guidance:
        return None

    return " ".join(selected_guidance)


def _format_learning_guidance(item: dict[str, object]) -> str:
    insight_type = str(item["insight_type"]).replace("_", " ")
    source_project_title = str(item["source_project_title"])
    confidence_score = float(item["confidence_score"])
    summary = str(item["summary"])
    confidence_percent = round(confidence_score * 100)
    return (
        f"{insight_type} from {source_project_title}: {summary} (confidence {confidence_percent}%)."
    )
