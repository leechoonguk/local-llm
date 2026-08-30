"""Seed migration 57 — the account every api/*.http file logs in as.

The .http suite is only runnable from an editor because this row exists after
`make db-init`. Two things must therefore hold, and neither is visible from the
migration alone: the seeded hash must verify against the password the .http files
declare, and production must not receive the account.
"""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.core.security import verify_password
from app.models.base import Base
from app.models.user import User  # noqa: F401 — register the table on metadata


SEED_MIGRATION = Path(__file__).parents[2] / "alembic" / "versions" / "57_seed_api_actor_user.py"
ACTOR_USERNAME = "api-actor"


def _load_migration():
    spec = importlib.util.spec_from_file_location(SEED_MIGRATION.stem, SEED_MIGRATION)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _run_upgrade() -> list[sa.RowMapping]:
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            Base.metadata.create_all(connection)
            namespace = vars(migration)
            original_op = namespace["op"]
            namespace["op"] = Operations(MigrationContext.configure(connection))
            try:
                namespace["upgrade"]()
            finally:
                namespace["op"] = original_op
            return list(
                connection.execute(
                    sa.text('SELECT username, email, hashed_password, created_by FROM "user"')
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()


def test_seed_creates_the_api_actor_with_a_usable_password() -> None:
    """The seeded account must exist and its declared password must work.

    Unconditional by design: a migration is a deterministic step, so the same
    chain produces the same rows everywhere.
    """
    rows = _run_upgrade()

    assert len(rows) == 1
    actor = rows[0]
    assert actor["username"] == "api-actor"
    assert actor["email"] == "api-actor@example.com"
    assert actor["created_by"] == "migration"
    # The credentials api/*.http declares must actually authenticate; a hash
    # regenerated with a different password would make every file fail at login.
    assert verify_password("api-actor-secret", actor["hashed_password"])



def test_http_files_send_the_seeded_credentials_verbatim() -> None:
    """The .http files and the migration must name the same account.

    The credentials are written out rather than referenced through a variable: an
    unresolved `{{actorUsername}}` is sent literally and login answers 401, which
    is indistinguishable from a broken file.
    """
    api_dir = Path(__file__).parents[3] / "api"
    login_line = f"username={ACTOR_USERNAME}&password=api-actor-secret"
    domain_files = [
        path
        for path in sorted(api_dir.glob("*.http"))
        if login_line in path.read_text(encoding="utf-8")
    ]
    assert [path.name for path in domain_files] == [
        "batch.http",
        "integration.http",
        "integration.search-food-item-report.http",
        "integration.search-food-nutrition.http",
        "integration.search-food-raw-material.http",
        "integration.search-product-classification.http",
        "user.http",
    ]
    for path in domain_files:
        content = path.read_text(encoding="utf-8")
        assert "{{actorUsername}}" not in content
        assert "{{actorPassword}}" not in content
