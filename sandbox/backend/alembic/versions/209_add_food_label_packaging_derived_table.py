"""add food label packaging derived table

Revision ID: 209
Revises: 208

One packaging part per row: 6,914 over 3,809 라벨 (2026-09-13), the widest label
set of the 푸드QR family. `food_item_report.packaging_material` keeps its own
one-string answer for 1,004,958 reports - measured on the 1,838 products both
cover, only 163 (8.9 %) are the same string, because this feed splits the parts.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "209"
down_revision: str | Sequence[str] | None = "208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_label_packaging",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("label_key", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("packaging_text", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=50), nullable=True),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
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
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source", "label_key", "position", name="uq_food_label_packaging_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_label_packaging_label_key"),
        "food_label_packaging",
        ["label_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_food_label_packaging_label_key"), table_name="food_label_packaging")
    op.drop_table("food_label_packaging")
