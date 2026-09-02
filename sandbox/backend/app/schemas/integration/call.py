# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.integration import IntegrationExchange


# ============================================================
# Classes
# ============================================================


class IntegrationCallCreateInternal(BaseModel):
    """One executed external call, as the log stores it.

    Internal only: this is never an HTTP body. The client hands back an
    `IntegrationExchange` whose values are already scrubbed of every secret it
    resolved — these providers carry the credential as a path segment and echo
    the request back, so the raw URL is the key.
    """

    model_config = ConfigDict(extra="forbid")

    operation_id: uuid.UUID | None = None
    provider_code: str
    operation_code: str
    method: str
    url: str
    request_headers: dict[str, Any]
    request_body: dict[str, Any] | None = None
    status_code: int | None = None
    response_headers: dict[str, Any] | None = None
    response_body: str | None = None
    outcome: str
    duration_ms: int
    attempts: int
    request_id: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    created_by: str

    @classmethod
    def from_exchange(
        cls,
        exchange: IntegrationExchange,
        *,
        operation_id: uuid.UUID,
        provider_code: str,
        operation_code: str,
        created_by: str,
    ) -> IntegrationCallCreateInternal:
        """Map what the client recorded onto the row.

        The codes are stored as strings beside the `SET NULL` foreign key: a
        `_replace_` revision deletes and re-inserts the operation, and a log
        that vanished with its configuration could not answer what we sent
        last month (`models/integration/call.py`).
        """
        body = exchange.request_body if isinstance(exchange.request_body, dict) else None
        return cls(
            operation_id=operation_id,
            provider_code=provider_code,
            operation_code=operation_code,
            method=exchange.method,
            url=exchange.url,
            request_headers=dict(exchange.request_headers),
            request_body=body,
            status_code=exchange.status_code,
            response_headers=(
                None if exchange.response_headers is None else dict(exchange.response_headers)
            ),
            response_body=exchange.response_body,
            outcome=exchange.outcome,
            duration_ms=exchange.duration_ms,
            attempts=exchange.attempts,
            request_id=exchange.request_id,
            error_code=exchange.error_code,
            error_detail=exchange.error_detail,
            created_by=created_by,
        )
