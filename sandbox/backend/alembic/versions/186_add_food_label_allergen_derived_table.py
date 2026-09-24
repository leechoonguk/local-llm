"""add food label allergen derived table

Revision ID: 186
Revises: 185

Table three: one declared allergen per row, 8,580 of them over 1,746 라벨
(2026-09-12), 74 distinct names kept as the publisher typed them. A label that
declares nothing has no row - where the retired HACCP split answered `알수없음`
on 8,507 of its 28,324 values (revision 171).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "186"
down_revision: str | Sequence[str] | None = "185"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_label_allergen",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("label_no", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("serial", sa.String(length=32), nullable=True),
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
        sa.UniqueConstraint("label_no", "position", name="uq_food_label_allergen_natural_key"),
    )
    op.create_index(
        op.f("ix_food_label_allergen_label_no"), "food_label_allergen", ["label_no"], unique=False
    )
    op.create_index("ix_food_label_allergen_name", "food_label_allergen", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_food_label_allergen_name", table_name="food_label_allergen")
    op.drop_index(op.f("ix_food_label_allergen_label_no"), table_name="food_label_allergen")
    op.drop_table("food_label_allergen")
