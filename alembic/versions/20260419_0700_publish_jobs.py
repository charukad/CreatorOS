"""add publish jobs

Revision ID: 20260419_0700
Revises: 20260419_0600
Create Date: 2026-04-19 07:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260419_0700"
down_revision = "20260419_0600"
branch_labels = None
depends_on = None


publish_job_status_enum = sa.Enum(
    "pending_approval",
    "approved",
    "scheduled",
    "published",
    "failed",
    "cancelled",
    name="publish_job_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "publish_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("script_id", sa.Uuid(), nullable=False),
        sa.Column("final_asset_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("hashtags_json", sa.JSON(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", publish_job_status_enum, nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("external_post_id", sa.String(length=255), nullable=True),
        sa.Column("manual_publish_notes", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(["final_asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_publish_jobs_final_asset_id"),
        "publish_jobs",
        ["final_asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_publish_jobs_idempotency_key"),
        "publish_jobs",
        ["idempotency_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_publish_jobs_project_id"),
        "publish_jobs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_publish_jobs_script_id"),
        "publish_jobs",
        ["script_id"],
        unique=False,
    )
    op.create_index(op.f("ix_publish_jobs_user_id"), "publish_jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_publish_jobs_user_id"), table_name="publish_jobs")
    op.drop_index(op.f("ix_publish_jobs_script_id"), table_name="publish_jobs")
    op.drop_index(op.f("ix_publish_jobs_project_id"), table_name="publish_jobs")
    op.drop_index(op.f("ix_publish_jobs_idempotency_key"), table_name="publish_jobs")
    op.drop_index(op.f("ix_publish_jobs_final_asset_id"), table_name="publish_jobs")
    op.drop_table("publish_jobs")
