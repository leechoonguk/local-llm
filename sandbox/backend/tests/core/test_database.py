"""Engine construction, and the registry the running app depends on."""

import subprocess
import sys
from pathlib import Path

from app.core.database import engine
from app.core.settings import settings


def test_database_engine_uses_configured_url_and_pre_ping() -> None:
    """A hardcoded driver or a missing pre-ping only surfaces in production.

    Without `pool_pre_ping` a pooled connection killed by the database (restart,
    idle timeout) is handed to a request and fails it.
    """
    assert engine.url.drivername == settings.database_url.split(":", 1)[0]
    assert engine.pool._pre_ping is True


def test_app_import_graph_registers_every_mapper() -> None:
    """The running app must configure its mappers, not just the test suite.

    A `relationship("IntegrationCall")` is resolved by name against the registry
    when mappers configure, so a mapped class whose module nobody imported is
    missing. `IntegrationCall` was reachable only from `alembic/env.py` and
    `tests/conftest.py` — both outside the app's import graph — so `make verify`
    stayed green while the deployed app answered 500 to its first query, which
    is every request.

    Run in a subprocess with only `app.main` imported: this suite's `conftest`
    imports every model, which is exactly what hid the gap.
    """
    probe = "import app.main; from sqlalchemy.orm import configure_mappers; configure_mappers()"
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
