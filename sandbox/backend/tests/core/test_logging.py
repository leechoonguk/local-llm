"""Renderer selection: console locally, JSON in production."""

import structlog

from app.core.logging import configure_logging


def test_configure_logging_supports_local_and_production_renderers() -> None:
    """Log shipping breaks silently when production emits console output.

    The renderer is the last processor, so this asserts the tail of the chain
    rather than the call that configured it.
    """
    configure_logging("local")
    assert isinstance(structlog.get_config()["processors"][-1], structlog.dev.ConsoleRenderer)

    configure_logging("production")
    assert isinstance(structlog.get_config()["processors"][-1], structlog.processors.JSONRenderer)
