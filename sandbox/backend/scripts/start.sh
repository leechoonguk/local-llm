#!/usr/bin/env bash
# Run DB migrations then start the backend server.
# ENV=local (default)  → uvicorn with --reload, bound on every interface: the
#                        Host allowlist (ALLOWED_HOSTS) is what gates access, not
#                        the bind address, and a loopback-only dev server cannot
#                        be called from another machine at all.
# ENV=production        → uvicorn on 0.0.0.0 (no reload)
# Usage: ./scripts/start.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Applying database migrations"
.venv/bin/alembic upgrade head

if [ "${ENV:-local}" = "local" ]; then
    echo "==> Starting backend (uvicorn :18000, reload)"
    nohup .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 18000 > /tmp/uvicorn.log 2>&1 &
    disown
    echo "==> Backend PID: $!"
else
    echo "==> Starting backend (uvicorn :18000, production)"
    # Foreground: as container PID 1, the server must stay attached (docker).
    # exec replaces the shell so uvicorn receives SIGTERM directly on shutdown.
    exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 18000
fi
