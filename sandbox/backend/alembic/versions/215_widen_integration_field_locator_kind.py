"""widen integration field locator kind

Revision ID: 215
Revises: 214

`SECTION` joins the three HTML locators: a heading's text, then a selector
inside the block that heading introduces. The first screen that needed it is
수입제품 상세 (2026-09-13) - its repeating groups are four tables sharing one
class inside anonymous divs, so a positional selector reads a different group
per record kind, and the `h3` above each is the only stable anchor the screen
offers.

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "215"
down_revision: str | Sequence[str] | None = "214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_integration_field_locator_kind", "integration_field", type_="check")
    op.create_check_constraint(
        "ck_integration_field_locator_kind",
        "integration_field",
        "locator_kind IN ('POINTER', 'CSS', 'LABEL', 'REGEX', 'SECTION')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_integration_field_locator_kind", "integration_field", type_="check")
    op.create_check_constraint(
        "ck_integration_field_locator_kind",
        "integration_field",
        "locator_kind IN ('POINTER', 'CSS', 'LABEL', 'REGEX')",
    )
