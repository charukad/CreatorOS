"""add analytics snapshots and insights

Revision ID: 20260419_0800
Revises: 20260419_0700
Create Date: 2026-04-19 08:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260419_0800"
down_revision = "20260419_0700"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("publish_job_id", sa.Uuid(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=False),
        sa.Column("comments", sa.Integer(), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("saves", sa.Integer(), nullable=True),
        sa.Column("watch_time_seconds", sa.Integer(), nullable=True),
        sa.Column("ctr", sa.Float(), nullable=True),
        sa.Column("avg_view_duration", sa.Float(), nullable=True),
        sa.Column("retention_json", sa.JSON(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["publish_job_id"], ["publish_jobs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analytics_snapshots_project_id"),
        "analytics_snapshots",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_snapshots_publish_job_id"),
        "analytics_snapshots",
        ["publish_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_snapshots_user_id"),
        "analytics_snapshots",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "insights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("publish_job_id", sa.Uuid(), nullable=False),
        sa.Column("analytics_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("insight_type", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["analytics_snapshot_id"], ["analytics_snapshots.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["publish_job_id"], ["publish_jobs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_insights_analytics_snapshot_id"),
        "insights",
        ["analytics_snapshot_id"],
        unique=False,
    )
    op.create_index(op.f("ix_insights_project_id"), "insights", ["project_id"], unique=False)
    op.create_index(
        op.f("ix_insights_publish_job_id"),
        "insights",
        ["publish_job_id"],
        unique=False,
    )
    op.create_index(op.f("ix_insights_user_id"), "insights", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_insights_user_id"), table_name="insights")
    op.drop_index(op.f("ix_insights_publish_job_id"), table_name="insights")
    op.drop_index(op.f("ix_insights_project_id"), table_name="insights")
    op.drop_index(op.f("ix_insights_analytics_snapshot_id"), table_name="insights")
    op.drop_table("insights")
    op.drop_index(op.f("ix_analytics_snapshots_user_id"), table_name="analytics_snapshots")
    op.drop_index(
        op.f("ix_analytics_snapshots_publish_job_id"),
        table_name="analytics_snapshots",
    )
    op.drop_index(op.f("ix_analytics_snapshots_project_id"), table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")
