"""drop response_mode: mapping is the only response contract

Revision ID: 60
Revises: 59
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "60"
down_revision: str | Sequence[str] | None = "59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PASSTHROUGH returned the provider's node verbatim, so its columns had no key, type
# or description of ours: the field dictionary lived outside the database, and the
# mode existed because a mapped response could only ever describe one record —
# `wire_path` was an absolute pointer, so a paged answer had to pin an index.
#
# Reading the rows relative to each element of `response_root` removed that limit,
# and with it the reason for a second mode. What is left is a column with one legal
# value, and a knob nobody turns is a knob that lies about being a choice.
#
# `response_root` is now the whole response contract: absent maps one record through
# absolute pointers, present maps every element of the page it names. Paging APIs are
# the second shape, which is why the check keeps the pointer form and nothing else.
MODE_CHECK = "ck_integration_operation_response_mode"
ROOT_CHECK = "ck_integration_operation_response_root"
POINTER_SHAPE = "response_root IS NULL OR response_root LIKE '/%'"
PREVIOUS_MODE_RULE = "response_mode IN ('MAPPED', 'PASSTHROUGH')"
PREVIOUS_ROOT_RULE = (
    "(response_mode = 'MAPPED' AND response_root IS NULL) "
    "OR (response_mode = 'PASSTHROUGH' AND response_root IS NOT NULL)"
)


def upgrade() -> None:
    op.drop_constraint(ROOT_CHECK, "integration_operation", type_="check")
    op.drop_constraint(MODE_CHECK, "integration_operation", type_="check")
    op.drop_column("integration_operation", "response_mode")
    op.create_check_constraint(ROOT_CHECK, "integration_operation", POINTER_SHAPE)


def downgrade() -> None:
    op.drop_constraint(ROOT_CHECK, "integration_operation", type_="check")
    op.add_column(
        "integration_operation",
        sa.Column("response_mode", sa.String(length=16), server_default="MAPPED", nullable=False),
    )
    op.create_check_constraint(MODE_CHECK, "integration_operation", PREVIOUS_MODE_RULE)
    op.create_check_constraint(ROOT_CHECK, "integration_operation", PREVIOUS_ROOT_RULE)
