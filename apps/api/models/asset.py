from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.schemas.enums import AssetStatus, AssetType, ProviderName


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"

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
    scene_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("scenes.id"),
        index=True,
        nullable=True,
    )
    generation_attempt_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("generation_attempts.id"),
        index=True,
        nullable=True,
    )
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(
            AssetType,
            name="asset_type",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        nullable=False,
    )
    status: Mapped[AssetStatus] = mapped_column(
        Enum(
            AssetStatus,
            name="asset_status",
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
        ),
        default=AssetStatus.PLANNED,
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
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)

    user = relationship("User", back_populates="assets")
    project = relationship("Project", back_populates="assets")
    script = relationship("ProjectScript", back_populates="assets")
    scene = relationship("Scene", back_populates="assets")
    generation_attempt = relationship("GenerationAttempt", back_populates="assets")
