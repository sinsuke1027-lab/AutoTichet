"""department_tags table

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "department_tags",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # 既存ユーザーの department_tags 配列からバックフィル（重複は無視）
    op.execute(sa.text("""
        INSERT INTO department_tags (name)
        SELECT DISTINCT jsonb_array_elements_text(department_tags)
        FROM user_profiles
        WHERE department_tags IS NOT NULL AND department_tags != '[]'::jsonb
        ON CONFLICT (name) DO NOTHING
    """))


def downgrade() -> None:
    op.drop_table("department_tags")
