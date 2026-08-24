"""widen field location: envelope status and path-carried filters

Revision ID: 63
Revises: 62
"""

from collections.abc import Sequence

from alembic import op

revision: str = "63"
down_revision: str | Sequence[str] | None = "62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Two shapes the four original locations could not express, both measured on
# openapi.foodsafetykorea.go.kr (service I1250):
#
# ENVELOPE — the provider answers HTTP 200 for every outcome and puts the verdict in
# the body wrapper: `RESULT.CODE` is INFO-000 on success, INFO-200 for "no data",
# INFO-100 for an invalid key and ERROR-334 for a bad window. With only page-relative
# RESPONSE rows an expired credential is indistinguishable from an empty page, so the
# wrapper needs rows of its own: absolute pointers, validated (or carried into
# metadata) before the page is mapped.
#
# PATH_QUERY — its filters are a query string relocated into the path
# (`/api/{key}/I1250/json/1/5/PRDLST_NM=김치&BSSH_NM=대상`). Sending them as a real
# query string is accepted and **silently ignored** — measured: `?PRDLST_NM=김치`
# answered `total_count 1069267`, the unfiltered count. A location that looks like it
# works and does nothing is the worst of the four, so the transport is named.
LOCATION_CHECK = "ck_integration_field_location"
MATCH_CHECK = "ck_integration_field_match_direction"
WIDENED_LOCATION = "location IN ('PATH', 'PATH_QUERY', 'QUERY', 'HEADER', 'BODY', 'ENVELOPE')"
PREVIOUS_LOCATION = "location IN ('PATH', 'QUERY', 'HEADER', 'BODY')"

# `match_mode` was a response-header concern; an envelope verdict is the same kind of
# claim about a value the provider sends, so the two locations that may carry one are
# named together.
WIDENED_MATCH = (
    "(match_mode IS NULL AND expected_values IS NULL) "
    "OR (direction = 'RESPONSE' AND location IN ('HEADER', 'ENVELOPE'))"
)
PREVIOUS_MATCH = (
    "(match_mode IS NULL AND expected_values IS NULL) "
    "OR (direction = 'RESPONSE' AND location = 'HEADER')"
)


def upgrade() -> None:
    op.drop_constraint(LOCATION_CHECK, "integration_field", type_="check")
    op.create_check_constraint(LOCATION_CHECK, "integration_field", WIDENED_LOCATION)
    op.drop_constraint(MATCH_CHECK, "integration_field", type_="check")
    op.create_check_constraint(MATCH_CHECK, "integration_field", WIDENED_MATCH)


def downgrade() -> None:
    op.drop_constraint(MATCH_CHECK, "integration_field", type_="check")
    op.create_check_constraint(MATCH_CHECK, "integration_field", PREVIOUS_MATCH)
    op.drop_constraint(LOCATION_CHECK, "integration_field", type_="check")
    op.create_check_constraint(LOCATION_CHECK, "integration_field", PREVIOUS_LOCATION)
