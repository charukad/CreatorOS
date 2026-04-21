from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.project import Project
from apps.api.models.project_event import ProjectEvent


def create_project_event(
    db: Session,
    project: Project,
    *,
    event_type: str,
    title: str,
    description: str | None = None,
    level: str = "info",
    metadata: dict[str, object] | None = None,
) -> ProjectEvent:
    event = ProjectEvent(
        user_id=project.user_id,
        project_id=project.id,
        event_type=event_type,
        title=title,
        description=description,
        level=level,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event


def list_project_events(db: Session, project: Project, *, limit: int = 80) -> list[ProjectEvent]:
    statement = (
        select(ProjectEvent)
        .where(ProjectEvent.project_id == project.id)
        .order_by(desc(ProjectEvent.created_at), desc(ProjectEvent.id))
        .limit(limit)
    )
    return list(db.scalars(statement))
