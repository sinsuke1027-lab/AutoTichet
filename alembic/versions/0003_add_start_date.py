"""add start_date to tasks

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # start_date column already exists in the database
    # This migration is a no-op to record the schema alignment
    pass


def downgrade() -> None:
    # No downgrade action needed since this is a no-op
    pass
