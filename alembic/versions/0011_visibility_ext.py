"""tasks テーブルに visibility_tag / visibility_project_id 列追加

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("visibility_tag", sa.Text, nullable=True))
    op.add_column(
        "tasks",
        sa.Column(
            "visibility_project_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "visibility_project_id")
    op.drop_column("tasks", "visibility_tag")
