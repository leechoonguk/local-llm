"""widen integration operation response format to csv

`CSV` is a file: one request answers the whole feed as a gzip CSV, read in
chunks by `IntegrationClient.stream`. It exists because the paged API of
식품안전나라 I0460 cannot be walked whole - 2,047 windows against a daily
ceiling of ~500 calls a key (measured 2026-09-19: three keys, 498/496/497
successful calls each, then `INFO-300`; the pass died at 73 %) - while the
portal's own file door answers the same 2,046,504 rows in four seconds, on a
quota of its own (ten downloads a day, a key and a service).

Revision ID: 285
Revises: 284

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "285"
down_revision: str | Sequence[str] | None = "284"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_integration_operation_response_format"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT, "integration_operation", type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        "integration_operation",
        "response_format IN ('JSON', 'XML', 'HTML', 'CSV')",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "integration_operation", type_="check")
    op.create_check_constraint(
        CONSTRAINT,
        "integration_operation",
        "response_format IN ('JSON', 'XML', 'HTML')",
    )
