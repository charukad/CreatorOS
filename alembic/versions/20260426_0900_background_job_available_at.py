"""add background job available_at scheduling column

Revision ID: 20260426_0900
Revises: 20260424_1400
Create Date: 2026-04-26 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260426_0900"
down_revision: str | Sequence[str] | None = "20260424_1400"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "background_jobs",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_background_jobs_available_at",
        "background_jobs",
        ["available_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_background_jobs_available_at", table_name="background_jobs")
    op.drop_column("background_jobs", "available_at")
