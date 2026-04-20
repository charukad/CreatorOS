"""allow project-level generation jobs

Revision ID: 20260420_1100
Revises: 20260420_0900
Create Date: 2026-04-20 11:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260420_1100"
down_revision = "20260420_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("content_ideas") as batch_op:
        batch_op.add_column(sa.Column("source_feedback_notes", sa.Text(), nullable=True))

    with op.batch_alter_table("background_jobs") as batch_op:
        batch_op.alter_column(
            "script_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )

    with op.batch_alter_table("job_logs") as batch_op:
        batch_op.alter_column(
            "script_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )


def downgrade() -> None:
    op.execute("DELETE FROM job_logs WHERE script_id IS NULL")
    op.execute("DELETE FROM background_jobs WHERE script_id IS NULL")

    with op.batch_alter_table("job_logs") as batch_op:
        batch_op.alter_column(
            "script_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )

    with op.batch_alter_table("background_jobs") as batch_op:
        batch_op.alter_column(
            "script_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )

    with op.batch_alter_table("content_ideas") as batch_op:
        batch_op.drop_column("source_feedback_notes")
