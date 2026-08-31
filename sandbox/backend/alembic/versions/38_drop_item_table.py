"""drop item table

Revision ID: 38
Revises: 37

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "38"
down_revision: str | Sequence[str] | None = "37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_item_name"), table_name="item")
    op.drop_table("item")


def downgrade() -> None:
    op.create_table(
        "item",
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
    op.create_index(op.f("ix_item_name"), "item", ["name"], unique=False)
