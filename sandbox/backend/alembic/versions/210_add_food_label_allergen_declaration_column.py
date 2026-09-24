"""add food label allergen declaration column

Revision ID: 210
Revises: 209

What a label says about allergens is three states, not two, and the table said
two. Measured 2026-09-13 over both live feeds: 7,815 labels declare at least one
substance, 41 say 없음 in so many words, and 9,084 say nothing a reader may act
on - 8,479 HACCP rows read 알수없음 and 576 푸드QR labels are absent from the
알레르기 feed entirely.

The screen showed the third as the second. 새우탕큰사발면 (1972015400112) has a
푸드QR label declaring twelve substances and a HACCP label reading 알수없음, and
the HACCP card said "표시된 알레르기 유발물질이 없습니다" - it told a reader the
package was allergen-free because its publisher did not know.

The rows are rebuilt by the derive job, so the column arrives with the default
the model states and the next pass fills it.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "210"
down_revision: str | Sequence[str] | None = "209"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "food_label",
        sa.Column(
            "allergen_declaration",
            sa.String(length=120),
            nullable=False,
            server_default="unknown",
        ),
    )
    # The default is the migration's, not the table's: the derive job writes the
    # real state on its next pass, and a column that kept a default would hide a
    # pass that never ran.
    op.alter_column("food_label", "allergen_declaration", server_default=None)


def downgrade() -> None:
    op.drop_column("food_label", "allergen_declaration")
