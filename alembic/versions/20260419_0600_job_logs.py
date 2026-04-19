"""add job logs

Revision ID: 20260419_0600
Revises: 20260419_0130
Create Date: 2026-04-19 06:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260419_0600"
down_revision = "20260419_0130"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("script_id", sa.Uuid(), nullable=False),
        sa.Column("background_job_id", sa.Uuid(), nullable=False),
        sa.Column("generation_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("level", sa.String(length=24), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["background_job_id"], ["background_jobs.id"]),
        sa.ForeignKeyConstraint(["generation_attempt_id"], ["generation_attempts.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["script_id"], ["scripts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_job_logs_background_job_id"),
        "job_logs",
        ["background_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_job_logs_generation_attempt_id"),
        "job_logs",
        ["generation_attempt_id"],
        unique=False,
    )
    op.create_index(op.f("ix_job_logs_project_id"), "job_logs", ["project_id"], unique=False)
    op.create_index(op.f("ix_job_logs_script_id"), "job_logs", ["script_id"], unique=False)
    op.create_index(op.f("ix_job_logs_user_id"), "job_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_logs_user_id"), table_name="job_logs")
    op.drop_index(op.f("ix_job_logs_script_id"), table_name="job_logs")
    op.drop_index(op.f("ix_job_logs_project_id"), table_name="job_logs")
    op.drop_index(op.f("ix_job_logs_generation_attempt_id"), table_name="job_logs")
    op.drop_index(op.f("ix_job_logs_background_job_id"), table_name="job_logs")
    op.drop_table("job_logs")
