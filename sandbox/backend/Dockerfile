# The interpreter is the one the test suite ran on. `.python-version` pins it
# for uv; the base image ships the same major so nothing is downloaded at
# build time. Measured before the pin: a python3.12 base with
# `requires-python >= 3.13` had uv fetch whatever 3.14.x was current, so two
# builds of one commit ran different interpreters (QA had 3.14.3, the tests
# 3.14.7).
# Pinned by digest, not by tag: uv publishes `<version>-python3.X-bookworm-slim`
# for older Pythons but the 3.14 variant exists only under the floating
# `python3.14-bookworm-slim` name (checked against the registry's tag list), so
# the digest is the only exact reference. It resolves to uv 0.9.30 on
# Python 3.14. Re-pin with: docker pull ghcr.io/astral-sh/uv:python3.14-bookworm-slim
# && docker image inspect --format '{{index .RepoDigests 0}}' that tag.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim@sha256:7cf77f594be8042dab6daa9fe326f90962252268b4f120a7f5dccce4d947e6c1

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN chmod +x scripts/start.sh

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["./scripts/start.sh"]