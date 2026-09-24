# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import logging
import sys

import structlog

from app.core.integration import TRANSPORT_LOGGERS


# ============================================================
# Functions
# ============================================================


def configure_logging(environment: str) -> None:
    """Configure structured application logs for the current environment."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
        force=True,
    )
    # The transport's loggers print the URL, and the key is in the URL
    # (`TRANSPORT_LOGGERS`, beside the transport).
    for name in TRANSPORT_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if environment == "production"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
