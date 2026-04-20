from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    approvals = relationship("Approval", back_populates="user")
    analytics_snapshots = relationship("AnalyticsSnapshot", back_populates="user")
    assets = relationship("Asset", back_populates="user")
    background_jobs = relationship("BackgroundJob", back_populates="user")
    brand_profiles = relationship("BrandProfile", back_populates="user")
    content_ideas = relationship("ContentIdea", back_populates="user")
    generation_attempts = relationship("GenerationAttempt", back_populates="user")
    insights = relationship("Insight", back_populates="user")
    job_logs = relationship("JobLog", back_populates="user")
    projects = relationship("Project", back_populates="user")
    publish_jobs = relationship("PublishJob", back_populates="user")
    scripts = relationship("ProjectScript", back_populates="user")
