from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.schemas.enums import BackgroundJobState, ProviderName


class GenerationAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_attempts"

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
    scene_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("scenes.id"),
        index=True,
        nullable=True,
    )
    provider_name: Mapped[ProviderName] = mapped_column(
        Enum(
            ProviderName,
            name="provider_name",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        nullable=False,
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
    input_payload_json: Mapped[dict[str, object]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="generation_attempts")
    project = relationship("Project", back_populates="generation_attempts")
    script = relationship("ProjectScript", back_populates="generation_attempts")
    background_job = relationship("BackgroundJob", back_populates="generation_attempts")
    scene = relationship("Scene", back_populates="generation_attempts")
    assets = relationship(
        "Asset",
        back_populates="generation_attempt",
        cascade="all, delete-orphan",
    )
