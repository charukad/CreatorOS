from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from apps.api.models.brand_profile import BrandProfile
from apps.api.models.project import Project
from apps.api.models.user import User
from apps.api.schemas.projects import ProjectCreate, ProjectUpdate


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
