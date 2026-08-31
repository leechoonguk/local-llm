"""drop task table

Revision ID: 40
Revises: 39

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "40"
down_revision: str | Sequence[str] | None = "39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_task_name"), table_name="task")
    op.drop_table("task")


def downgrade() -> None:
    op.create_table(
        "task",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_name"), "task", ["name"], unique=False)
