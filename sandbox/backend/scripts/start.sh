#!/usr/bin/env bash
# Run DB migrations then start the backend server.
# ENV=local (default)  → uvicorn with --reload on BACKEND_PORT, bound on every
#                        interface: the Host allowlist (ALLOWED_HOSTS) is what
#                        gates access, not the bind address, and a loopback-only
#                        dev server cannot be called from another machine at all.
# ENV=production        → uvicorn on 0.0.0.0:8000, no reload. The port is the
#                        fixed in-network one docker-compose maps the host port
#                        onto; every in-network URL names it, so it never moves.
# Usage: ./scripts/start.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# The container's in-network port. Host-side publishing is BACKEND_PORT in the
# root .env, which docker-compose maps onto this one.
CONTAINER_PORT=8000

echo "==> Applying database migrations"
.venv/bin/alembic upgrade head

if [ "${ENV:-local}" = "local" ]; then
    # Local dev serves on the host port, because that is what the Vite proxy and
    # api/*.http resolve to. Hardcoding it here would need two edits per move.
    port="${BACKEND_PORT:-$CONTAINER_PORT}"
    echo "==> Starting backend (uvicorn :$port, reload)"
    nohup .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port "$port" > /tmp/uvicorn.log 2>&1 &
    disown
    echo "==> Backend PID: $!"
else
    echo "==> Starting backend (uvicorn :$CONTAINER_PORT, production)"
    # Foreground: as container PID 1, the server must stay attached (docker).
    # exec replaces the shell so uvicorn receives SIGTERM directly on shutdown.
    exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$CONTAINER_PORT"
fi
