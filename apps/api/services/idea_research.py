from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.brand_profile import BrandProfile
from apps.api.models.idea_research_snapshot import IdeaResearchSnapshot
from apps.api.models.project import Project
from apps.api.models.user import User
from apps.api.schemas.content_workflow import IdeaResearchGenerateRequest
from apps.api.schemas.enums import ProjectStatus
from apps.api.services.learning_context import summarize_analytics_learning_context


def list_project_idea_research_snapshots(
    db: Session,
    project: Project,
) -> list[IdeaResearchSnapshot]:
    statement = (
        select(IdeaResearchSnapshot)
        .where(IdeaResearchSnapshot.project_id == project.id)
        .order_by(desc(IdeaResearchSnapshot.created_at), desc(IdeaResearchSnapshot.id))
    )
    return list(db.scalars(statement))


def get_latest_project_idea_research_snapshot(
    db: Session,
    project: Project,
) -> IdeaResearchSnapshot | None:
    statement = (
        select(IdeaResearchSnapshot)
        .where(IdeaResearchSnapshot.project_id == project.id)
        .order_by(desc(IdeaResearchSnapshot.created_at), desc(IdeaResearchSnapshot.id))
    )
    return db.scalar(statement)


def build_idea_research_context(
    snapshot: IdeaResearchSnapshot | None,
) -> dict[str, object] | None:
    if snapshot is None:
        return None

    return {
        "research_snapshot_id": str(snapshot.id),
        "focus_topic": snapshot.focus_topic,
        "summary": snapshot.summary,
        "trend_observations": snapshot.trend_observations_json,
        "competitor_angles": snapshot.competitor_angles_json,
        "posting_strategies": snapshot.posting_strategies_json,
        "recommended_topics": snapshot.recommended_topics_json,
    }


def generate_idea_research_snapshot(
    db: Session,
    user: User,
    project: Project,
    brand_profile: BrandProfile,
    payload: IdeaResearchGenerateRequest,
    *,
    analytics_learning_context: dict[str, object] | None = None,
) -> IdeaResearchSnapshot:
    if project.status not in {ProjectStatus.DRAFT, ProjectStatus.IDEA_PENDING_APPROVAL}:
        raise ValueError(
            "Idea research can only be generated while the project is in draft or idea approval."
        )

    focus_topic = _normalize_phrase(payload.focus_topic or project.title)
    objective = _normalize_phrase(project.objective)
    audience = _normalize_phrase(brand_profile.target_audience)
    tone = _normalize_phrase(brand_profile.tone)
    niche = _normalize_phrase(brand_profile.niche)
    platform = _normalize_phrase(project.target_platform)
    notes = _normalize_phrase(
        payload.source_feedback_notes
        or project.notes
        or "Bias the research toward practical short-form execution."
    )
    audience_short = audience.split(",")[0]
    learning_focus = summarize_analytics_learning_context(analytics_learning_context)
    learning_suffix = (
        f" Recent analytics learning reinforces {learning_focus.lower()}."
        if learning_focus
        else ""
    )

    snapshot = IdeaResearchSnapshot(
        user_id=user.id,
        project_id=project.id,
        focus_topic=payload.focus_topic,
        source_feedback_notes=payload.source_feedback_notes,
        summary=(
            f"For {audience_short.lower()} on {platform}, the strongest {niche.lower()} ideas "
            f"around {focus_topic.lower()} should promise one quick win, show visible proof, and "
            f"end with a {tone.lower()} invitation to act. Keep the framing aligned to "
            f"{objective.lower()}."
            f"{learning_suffix}"
        ),
        trend_observations_json=_build_trend_observations(
            focus_topic=focus_topic,
            audience=audience_short,
            objective=objective,
            platform=platform,
            notes=notes,
            learning_focus=learning_focus,
        ),
        competitor_angles_json=_build_competitor_angles(
            focus_topic=focus_topic,
            audience=audience_short,
            tone=tone,
            notes=notes,
        ),
        posting_strategies_json=_build_posting_strategies(
            focus_topic=focus_topic,
            platform=platform,
            tone=tone,
            notes=notes,
        ),
        recommended_topics_json=_build_recommended_topics(
            focus_topic=focus_topic,
            audience=audience_short,
            objective=objective,
            notes=notes,
        ),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def _build_trend_observations(
    *,
    focus_topic: str,
    audience: str,
    objective: str,
    platform: str,
    notes: str,
    learning_focus: str | None,
) -> list[str]:
    return [
        (
            f"{platform.title()} viewers respond best when {focus_topic.lower()} is framed as one "
            f"clear before-and-after win for {audience.lower()}."
        ),
        (
            f"The strongest hooks tie {focus_topic.lower()} to a visible result inside "
            f"{objective.lower()} rather than broad motivation."
        ),
        (
            f"Use concrete execution details from this note: {notes}."
            + (f" Apply the proven learning focus: {learning_focus}." if learning_focus else "")
        ),
    ]


def _build_competitor_angles(
    *,
    focus_topic: str,
    audience: str,
    tone: str,
    notes: str,
) -> list[str]:
    return [
        (
            f"Counter overproduced advice with a {tone.lower()} teardown of the one "
            f"{focus_topic.lower()} "
            f"step {audience.lower()} can copy today."
        ),
        (
            f"Replace vague inspiration with a proof-led walkthrough showing how "
            f"{focus_topic.lower()} "
            "works in a real creator workflow."
        ),
        (
            f"Differentiate by translating {focus_topic.lower()} into repeatable weekly actions "
            "instead of one-off hacks. "
            f"Keep this nuance in view: {notes}."
        ),
    ]


def _build_posting_strategies(
    *,
    focus_topic: str,
    platform: str,
    tone: str,
    notes: str,
) -> list[str]:
    return [
        (
            f"Open with the visible pain point in the first two seconds, then move into a "
            f"{tone.lower()} "
            f"three-step explanation of {focus_topic.lower()}."
        ),
        (
            f"Pair each claim with proof-friendly visuals so the {platform} edit feels earned "
            "rather than generic."
        ),
        (
            f"Reserve the final beat for a practical CTA that extends the lesson. Supporting "
            f"note: {notes}."
        ),
    ]


def _build_recommended_topics(
    *,
    focus_topic: str,
    audience: str,
    objective: str,
    notes: str,
) -> list[str]:
    root_topic = focus_topic.strip() or "Creator workflow"
    return [
        root_topic,
        f"{root_topic} mistakes {audience.lower()} can fix this week",
        f"{root_topic} proof points that make {objective.lower()} believable",
        f"{root_topic} workflows with concrete examples from: {notes}",
    ]


def _normalize_phrase(value: str) -> str:
    compact = " ".join(part for part in value.strip().split())
    return compact or "Creator workflow"
