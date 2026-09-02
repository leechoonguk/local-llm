# ============================================================
# Imports
# ============================================================

# Every mapped class, imported here so the registry is complete the moment any
# model is touched. Python executes a package's `__init__` before its
# submodules, so `from app.models.user import User` registers all of them.
#
# This is not a barrel: nothing is re-exported, and no caller may import from
# `app.models` (import the table's own module). It exists because a
# `relationship("IntegrationCall")` is resolved by name against the registry at
# mapper-configuration time, and a class whose module nobody imported is not in
# it. `IntegrationCall` was reachable only from `alembic/env.py` and
# `tests/conftest.py` — both outside the app's import graph — so the test suite
# and the migrations were green while the running app raised
# `InvalidRequestError: failed to locate a name ('IntegrationCall')` on its
# first query, which is every request.
from app.models.base import AuditMixin, Base  # noqa: F401 — declarative base
from app.models.batch.schedule import BatchSchedule  # noqa: F401 — register model on metadata
from app.models.integration.call import IntegrationCall  # noqa: F401 — register model
from app.models.integration.field import IntegrationField  # noqa: F401 — register model
from app.models.integration.operation import (  # noqa: F401 — register model
    IntegrationOperation,
)
from app.models.integration.provider import Integration  # noqa: F401 — register model
from app.models.integration.secret import IntegrationSecret  # noqa: F401 — register model
from app.models.user import User  # noqa: F401 — register model on metadata
