from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.schemas.enums import ProjectStatus


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=False)
    brand_profile_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("brand_profiles.id"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_platform: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            name="project_status",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        default=ProjectStatus.DRAFT,
        nullable=False,
    )
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="projects")
    brand_profile = relationship("BrandProfile", back_populates="projects")
    content_ideas = relationship(
        "ContentIdea",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    scripts = relationship(
        "ProjectScript",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    approvals = relationship(
        "Approval",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    background_jobs = relationship(
        "BackgroundJob",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    generation_attempts = relationship(
        "GenerationAttempt",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    assets = relationship(
        "Asset",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    analytics_snapshots = relationship(
        "AnalyticsSnapshot",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    insights = relationship(
        "Insight",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    job_logs = relationship(
        "JobLog",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    project_events = relationship(
        "ProjectEvent",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    publish_jobs = relationship(
        "PublishJob",
        back_populates="project",
        cascade="all, delete-orphan",
    )
