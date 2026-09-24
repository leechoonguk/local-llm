"""Renderer selection: console locally, JSON in production."""

import logging

import structlog

from app.core.integration import TRANSPORT_LOGGERS
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


def test_the_http_client_is_held_to_warnings() -> None:
    """At INFO the client prints every URL, and the provider's key is in the URL."""
    configure_logging("local")

    assert logging.getLogger().level == logging.INFO
    for name in TRANSPORT_LOGGERS:
        assert logging.getLogger(name).getEffectiveLevel() == logging.WARNING
