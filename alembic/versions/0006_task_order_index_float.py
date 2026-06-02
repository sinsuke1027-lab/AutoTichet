"""task order_index を Integer から Float に変更し初期採番

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tasks",
        "order_index",
        type_=sa.Float(),
        nullable=False,
        server_default="0.0",
        existing_nullable=False,
    )
    # セクション（またはプロジェクト）ごとに created_at 昇順で 1000.0 刻みに採番
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY COALESCE(section_id::text, project_id::text, 'no_group')
                       ORDER BY created_at
                   ) AS rn
            FROM tasks
        )
        UPDATE tasks
        SET order_index = ranked.rn * 1000.0
        FROM ranked
        WHERE tasks.id = ranked.id
    """)


def downgrade() -> None:
    op.alter_column(
        "tasks",
        "order_index",
        type_=sa.Integer(),
        nullable=False,
        server_default="0",
        existing_nullable=False,
    )
