from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, UUIDPrimaryKeyMixin


class Insight(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "insights"

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
    analytics_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analytics_snapshots.id"),
        index=True,
        nullable=False,
    )
    insight_type: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="insights")
    project = relationship("Project", back_populates="insights")
    publish_job = relationship("PublishJob", back_populates="insights")
    analytics_snapshot = relationship("AnalyticsSnapshot", back_populates="insights")
