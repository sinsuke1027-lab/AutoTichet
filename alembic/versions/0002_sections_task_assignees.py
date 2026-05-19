"""sections and task_assignees

Revision ID: 0002
Revises: 15ed88e74315
Create Date: 2026-05-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "15ed88e74315"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "task_assignees",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False, server_default="sub"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "user_id"),
    )
    op.add_column("tasks", sa.Column("section_id", sa.UUID(), nullable=True))
    op.add_column("tasks", sa.Column("external_id", sa.String(length=100), nullable=True))
    op.add_column("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key(
        "fk_tasks_section_id", "tasks", "sections", ["section_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tasks_section_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "order_index")
    op.drop_column("tasks", "completed_at")
    op.drop_column("tasks", "external_id")
    op.drop_column("tasks", "section_id")
    op.drop_table("task_assignees")
    op.drop_table("sections")
