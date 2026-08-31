"""drop todo table

Revision ID: 39
Revises: 38

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "39"
down_revision: str | Sequence[str] | None = "38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_todo_name"), table_name="todo")
    op.drop_table("todo")


def downgrade() -> None:
    op.create_table(
        "todo",
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
    op.create_index(op.f("ix_todo_name"), "todo", ["name"], unique=False)
