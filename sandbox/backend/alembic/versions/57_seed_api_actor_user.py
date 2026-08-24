"""seed api actor user

Revision ID: 57
Revises: 56

The account every `api/*.http` file authenticates as. Seeding it here — rather
than having each file create one — is what makes the files runnable from an
editor: `make db-init` leaves the account in place, so the first block is a
login, not a signup.

No condition guards this insert. A migration is a deterministic step: the same
chain must produce the same rows everywhere, or "it works on my machine" becomes
a schema question. This repository therefore ships a test account with known
credentials; a deployment that must not have it removes or rotates the row as
part of its own procedure, outside the migration chain.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

revision: str = "57"
down_revision: str | Sequence[str] | None = "56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTOR_ID = uuid5(NAMESPACE_URL, "fast-api-standard/api-actor")
ACTOR_USERNAME = "api-actor"
ACTOR_EMAIL = "api-actor@example.com"
# argon2id hash of "api-actor-secret" — the credentials api/*.http declares.
ACTOR_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$kkOm8fWbs9aTitCTrYqgRQ$"
    "DSwkfGQjpBHHkfE+NPcTa5Fz5ZoIvMEnu8W5AWmma90"
)


def upgrade() -> None:
    user = table(
        "user",
        column("id", sa.Uuid()),
        column("username", sa.String()),
        column("email", sa.String()),
        column("hashed_password", sa.String()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )
    op.bulk_insert(
        user,
        [
            {
                "id": ACTOR_ID,
                "username": ACTOR_USERNAME,
                "email": ACTOR_EMAIL,
                "hashed_password": ACTOR_PASSWORD_HASH,
                "created_by": "migration",
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    user = table("user", column("id", sa.Uuid()))
    op.get_bind().execute(user.delete().where(user.c.id == ACTOR_ID))
