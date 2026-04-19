from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JobLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_logs"

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
    background_job_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("background_jobs.id"),
        index=True,
        nullable=False,
    )
    generation_attempt_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("generation_attempts.id"),
        index=True,
        nullable=True,
    )
    level: Mapped[str] = mapped_column(String(24), default="info", nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="job_logs")
    project = relationship("Project", back_populates="job_logs")
    script = relationship("ProjectScript", back_populates="job_logs")
    background_job = relationship("BackgroundJob", back_populates="job_logs")
    generation_attempt = relationship("GenerationAttempt", back_populates="job_logs")
