from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.schemas.enums import BackgroundJobState, BackgroundJobType, ProviderName


class BackgroundJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "background_jobs"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id"),
        index=True,
        nullable=False,
    )
    script_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("scripts.id"),
        index=True,
        nullable=False,
    )
    job_type: Mapped[BackgroundJobType] = mapped_column(
        Enum(
            BackgroundJobType,
            name="background_job_type",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        nullable=False,
    )
    provider_name: Mapped[ProviderName | None] = mapped_column(
        Enum(
            ProviderName,
            name="provider_name",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        nullable=True,
    )
    state: Mapped[BackgroundJobState] = mapped_column(
        Enum(
            BackgroundJobState,
            name="background_job_state",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        default=BackgroundJobState.QUEUED,
        nullable=False,
    )
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="background_jobs")
    project = relationship("Project", back_populates="background_jobs")
    script = relationship("ProjectScript", back_populates="background_jobs")
    generation_attempts = relationship(
        "GenerationAttempt",
        back_populates="background_job",
        cascade="all, delete-orphan",
    )
    job_logs = relationship(
        "JobLog",
        back_populates="background_job",
        cascade="all, delete-orphan",
        order_by="JobLog.created_at",
    )
