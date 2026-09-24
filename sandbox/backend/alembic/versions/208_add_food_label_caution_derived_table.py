"""add food label caution derived table

Revision ID: 208
Revises: 207

One 주의사항 문구 per row: 8,134 over 2,154 라벨 (2026-09-13), of which 1,198 are
the 교차오염 sentence (`…과 같은 제조시설에서 제조하였습니다`) - a different fact
from the allergens a product contains, and one `food_item_report` has no column
for.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "208"
down_revision: str | Sequence[str] | None = "207"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_label_caution",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("label_key", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("caution_text", sa.Text(), nullable=True),
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
            "source", "label_key", "position", name="uq_food_label_caution_natural_key"
        ),
    )
    op.create_index(
        op.f("ix_food_label_caution_label_key"), "food_label_caution", ["label_key"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_food_label_caution_label_key"), table_name="food_label_caution")
    op.drop_table("food_label_caution")
