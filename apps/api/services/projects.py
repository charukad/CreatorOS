from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.brand_profile import BrandProfile
from apps.api.models.project import Project
from apps.api.models.user import User
from apps.api.schemas.enums import ProjectStatus
from apps.api.schemas.projects import ProjectCreate, ProjectUpdate
from apps.api.services.content_workflow import validate_project_transition_prerequisites
from apps.api.services.project_events import create_project_event

project_status_transitions: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.DRAFT: {ProjectStatus.IDEA_PENDING_APPROVAL, ProjectStatus.ARCHIVED},
    ProjectStatus.IDEA_PENDING_APPROVAL: {
        ProjectStatus.DRAFT,
        ProjectStatus.SCRIPT_PENDING_APPROVAL,
        ProjectStatus.ARCHIVED,
    },
    ProjectStatus.SCRIPT_PENDING_APPROVAL: {
        ProjectStatus.IDEA_PENDING_APPROVAL,
        ProjectStatus.ASSET_GENERATION,
        ProjectStatus.ARCHIVED,
    },
    ProjectStatus.ASSET_GENERATION: {
        ProjectStatus.SCRIPT_PENDING_APPROVAL,
        ProjectStatus.ASSET_PENDING_APPROVAL,
        ProjectStatus.FAILED,
        ProjectStatus.ARCHIVED,
    },
    ProjectStatus.ASSET_PENDING_APPROVAL: {
        ProjectStatus.ASSET_GENERATION,
        ProjectStatus.ROUGH_CUT_READY,
        ProjectStatus.ARCHIVED,
    },
    ProjectStatus.ROUGH_CUT_READY: {
        ProjectStatus.ASSET_PENDING_APPROVAL,
        ProjectStatus.FINAL_PENDING_APPROVAL,
        ProjectStatus.ARCHIVED,
    },
    ProjectStatus.FINAL_PENDING_APPROVAL: {
        ProjectStatus.ROUGH_CUT_READY,
        ProjectStatus.READY_TO_PUBLISH,
        ProjectStatus.ARCHIVED,
    },
    ProjectStatus.READY_TO_PUBLISH: {
        ProjectStatus.FINAL_PENDING_APPROVAL,
        ProjectStatus.SCHEDULED,
        ProjectStatus.PUBLISHED,
        ProjectStatus.ARCHIVED,
    },
    ProjectStatus.SCHEDULED: {
        ProjectStatus.READY_TO_PUBLISH,
        ProjectStatus.PUBLISHED,
        ProjectStatus.ARCHIVED,
    },
    ProjectStatus.PUBLISHED: {ProjectStatus.ARCHIVED},
    ProjectStatus.FAILED: {
        ProjectStatus.DRAFT,
        ProjectStatus.ASSET_GENERATION,
        ProjectStatus.ARCHIVED,
    },
    ProjectStatus.ARCHIVED: set(),
}


def create_project(
    db: Session,
    user: User,
    brand_profile: BrandProfile,
    payload: ProjectCreate,
) -> Project:
    project = Project(
        user_id=user.id,
        brand_profile_id=brand_profile.id,
        title=payload.title,
        target_platform=payload.target_platform,
        objective=payload.objective,
        notes=payload.notes,
    )
    db.add(project)
    db.flush()
    create_project_event(
        db,
        project,
        event_type="project_created",
        title="Project created",
        description=payload.objective,
        metadata={
            "brand_profile_id": str(brand_profile.id),
            "target_platform": payload.target_platform,
        },
    )
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session, user: User) -> list[Project]:
    statement = (
        select(Project)
        .where(Project.user_id == user.id)
        .order_by(desc(Project.updated_at), desc(Project.created_at))
    )
    return list(db.scalars(statement))


def get_project(db: Session, user: User, project_id: UUID) -> Project | None:
    statement = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    return db.scalar(statement)


def get_owned_brand_profile(db: Session, user: User, brand_profile_id: UUID) -> BrandProfile | None:
    statement = select(BrandProfile).where(
        BrandProfile.id == brand_profile_id,
        BrandProfile.user_id == user.id,
    )
    return db.scalar(statement)


def update_project(
    db: Session,
    project: Project,
    payload: ProjectUpdate,
    brand_profile: BrandProfile | None = None,
) -> Project:
    previous_values = {
        "brand_profile_id": str(project.brand_profile_id),
        "title": project.title,
        "target_platform": project.target_platform,
        "objective": project.objective,
        "notes": project.notes,
    }
    update_data = payload.model_dump(exclude_unset=True)
    if brand_profile is not None:
        update_data["brand_profile_id"] = brand_profile.id

    for field, value in update_data.items():
        setattr(project, field, value)

    db.add(project)
    if update_data:
        create_project_event(
            db,
            project,
            event_type="project_updated",
            title="Project settings updated",
            metadata={
                "changed_fields": sorted(update_data),
                "previous_values": previous_values,
                "new_values": {
                    key: str(value) if key == "brand_profile_id" else value
                    for key, value in update_data.items()
                },
            },
        )
    db.commit()
    db.refresh(project)
    return project


def transition_project_status(
    db: Session,
    project: Project,
    target_status: ProjectStatus,
) -> Project:
    previous_status = project.status
    allowed_transitions = project_status_transitions[project.status]
    if target_status not in allowed_transitions:
        allowed_values = ", ".join(sorted(status.value for status in allowed_transitions)) or "none"
        raise ValueError(
            f"Project cannot transition from '{project.status.value}' to '{target_status.value}'. "
            f"Allowed transitions: {allowed_values}."
        )

    validate_project_transition_prerequisites(db, project, target_status)

    project.status = target_status
    db.add(project)
    create_project_event(
        db,
        project,
        event_type="project_status_changed",
        title=f"Project moved to {target_status.value.replace('_', ' ')}",
        metadata={
            "previous_status": previous_status.value,
            "target_status": target_status.value,
            "transition_type": "guarded",
        },
    )
    db.commit()
    db.refresh(project)
    return project


def archive_project(db: Session, project: Project, *, reason: str | None = None) -> Project:
    if project.status == ProjectStatus.ARCHIVED:
        raise ValueError("Project is already archived.")

    previous_status = project.status
    project.status = ProjectStatus.ARCHIVED
    db.add(project)
    create_project_event(
        db,
        project,
        event_type="project_archived",
        title="Project archived",
        description=reason,
        level="warning",
        metadata={
            "previous_status": previous_status.value,
            "target_status": ProjectStatus.ARCHIVED.value,
        },
    )
    db.commit()
    db.refresh(project)
    return project


def manual_override_project_status(
    db: Session,
    project: Project,
    *,
    target_status: ProjectStatus,
    reason: str,
) -> Project:
    if project.status == ProjectStatus.ARCHIVED:
        raise ValueError("Archived projects cannot be manually overridden.")

    previous_status = project.status
    project.status = target_status
    db.add(project)
    create_project_event(
        db,
        project,
        event_type="manual_status_override",
        title=f"Manual override to {target_status.value.replace('_', ' ')}",
        description=reason,
        level="warning",
        metadata={
            "previous_status": previous_status.value,
            "target_status": target_status.value,
            "transition_type": "manual_override",
        },
    )
    db.commit()
    db.refresh(project)
    return project
