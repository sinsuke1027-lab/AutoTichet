"""milestone complete columns

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "milestones",
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "milestones",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("milestones", "completed_at")
    op.drop_column("milestones", "completed")
