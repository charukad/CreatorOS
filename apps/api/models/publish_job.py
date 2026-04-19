from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.schemas.enums import PublishJobStatus


class PublishJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "publish_jobs"

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
    final_asset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("assets.id"),
        index=True,
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[PublishJobStatus] = mapped_column(
        Enum(
            PublishJobStatus,
            name="publish_job_status",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        default=PublishJobStatus.PENDING_APPROVAL,
        nullable=False,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manual_publish_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="publish_jobs")
    project = relationship("Project", back_populates="publish_jobs")
    script = relationship("ProjectScript", back_populates="publish_jobs")
    final_asset = relationship("Asset", back_populates="publish_jobs")
