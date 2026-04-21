from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, UUIDPrimaryKeyMixin


class AnalyticsSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analytics_snapshots"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id"),
        index=True,
        nullable=False,
    )
    publish_job_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("publish_jobs.id"),
        index=True,
        nullable=False,
    )
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watch_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_view_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    retention_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="analytics_snapshots")
    project = relationship("Project", back_populates="analytics_snapshots")
    publish_job = relationship("PublishJob", back_populates="analytics_snapshots")
    insights = relationship(
        "Insight",
        back_populates="analytics_snapshot",
        cascade="all, delete-orphan",
    )
