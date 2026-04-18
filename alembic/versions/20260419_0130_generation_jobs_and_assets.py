"""add generation jobs and assets

Revision ID: 20260419_0130
Revises: 20260419_0015
Create Date: 2026-04-19 01:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260419_0130"
down_revision = "20260419_0015"
branch_labels = None
depends_on = None


provider_name_enum = sa.Enum(
    "elevenlabs_web",
    "flow_web",
    name="provider_name",
    native_enum=False,
)

background_job_type_enum = sa.Enum(
    "generate_audio_browser",
    "generate_visuals_browser",
    name="background_job_type",
    native_enum=False,
)

background_job_state_enum = sa.Enum(
    "queued",
    "running",
    "waiting_external",
    "completed",
    "failed",
    "cancelled",
    name="background_job_state",
    native_enum=False,
)

asset_type_enum = sa.Enum(
    "script_doc",
    "narration_audio",
    "scene_image",
    "scene_video",
    "rough_cut",
    "final_video",
    "subtitle_file",
    "thumbnail",
    name="asset_type",
    native_enum=False,
)

asset_status_enum = sa.Enum(
    "planned",
    "generating",
    "ready",
    "failed",
    "rejected",
    name="asset_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("script_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", background_job_type_enum, nullable=False),
        sa.Column("provider_name", provider_name_enum, nullable=True),
        sa.Column("state", background_job_state_enum, nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_background_jobs_project_id"),
        "background_jobs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_background_jobs_script_id"),
        "background_jobs",
        ["script_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_background_jobs_user_id"),
        "background_jobs",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "generation_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("script_id", sa.Uuid(), nullable=False),
        sa.Column("background_job_id", sa.Uuid(), nullable=False),
        sa.Column("scene_id", sa.Uuid(), nullable=True),
        sa.Column("provider_name", provider_name_enum, nullable=False),
        sa.Column("state", background_job_state_enum, nullable=False),
        sa.Column("input_payload_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["background_job_id"], ["background_jobs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.id"]),
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generation_attempts_background_job_id"),
        "generation_attempts",
        ["background_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generation_attempts_project_id"),
        "generation_attempts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generation_attempts_scene_id"),
        "generation_attempts",
        ["scene_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generation_attempts_script_id"),
        "generation_attempts",
        ["script_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generation_attempts_user_id"),
        "generation_attempts",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("script_id", sa.Uuid(), nullable=False),
        sa.Column("scene_id", sa.Uuid(), nullable=True),
        sa.Column("generation_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("asset_type", asset_type_enum, nullable=False),
        sa.Column("status", asset_status_enum, nullable=False),
        sa.Column("provider_name", provider_name_enum, nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["generation_attempt_id"], ["generation_attempts.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.id"]),
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assets_generation_attempt_id"),
        "assets",
        ["generation_attempt_id"],
        unique=False,
    )
    op.create_index(op.f("ix_assets_project_id"), "assets", ["project_id"], unique=False)
    op.create_index(op.f("ix_assets_scene_id"), "assets", ["scene_id"], unique=False)
    op.create_index(op.f("ix_assets_script_id"), "assets", ["script_id"], unique=False)
    op.create_index(op.f("ix_assets_user_id"), "assets", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_assets_user_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_script_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_scene_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_project_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_generation_attempt_id"), table_name="assets")
    op.drop_table("assets")

    op.drop_index(op.f("ix_generation_attempts_user_id"), table_name="generation_attempts")
    op.drop_index(op.f("ix_generation_attempts_script_id"), table_name="generation_attempts")
    op.drop_index(op.f("ix_generation_attempts_scene_id"), table_name="generation_attempts")
    op.drop_index(op.f("ix_generation_attempts_project_id"), table_name="generation_attempts")
    op.drop_index(
        op.f("ix_generation_attempts_background_job_id"),
        table_name="generation_attempts",
    )
    op.drop_table("generation_attempts")

    op.drop_index(op.f("ix_background_jobs_user_id"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_script_id"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_project_id"), table_name="background_jobs")
    op.drop_table("background_jobs")
