"""Engine construction: the URL comes from settings and pooling pre-pings."""

from app.core.database import engine
from app.core.settings import settings


def test_database_engine_uses_configured_url_and_pre_ping() -> None:
    """A hardcoded driver or a missing pre-ping only surfaces in production.

    Without `pool_pre_ping` a pooled connection killed by the database (restart,
    idle timeout) is handed to a request and fails it.
    """
    assert engine.url.drivername == settings.database_url.split(":", 1)[0]
    assert engine.pool._pre_ping is True
