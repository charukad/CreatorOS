from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.brand_profile import BrandProfile
from apps.api.models.project import Project
from apps.api.models.user import User
from apps.api.schemas.enums import ProjectStatus
from apps.api.schemas.projects import ProjectCreate, ProjectUpdate
from apps.api.services.content_workflow import validate_project_transition_prerequisites

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
    update_data = payload.model_dump(exclude_unset=True)
    if brand_profile is not None:
        update_data["brand_profile_id"] = brand_profile.id

    for field, value in update_data.items():
        setattr(project, field, value)

    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def transition_project_status(
    db: Session,
    project: Project,
    target_status: ProjectStatus,
) -> Project:
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
    db.commit()
    db.refresh(project)
    return project
