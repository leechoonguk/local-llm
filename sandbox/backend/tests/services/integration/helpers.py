"""Payload factories shared by the integration service tests."""

from __future__ import annotations

from app.schemas.integration.field import IntegrationFieldCreateRequest
from app.schemas.integration.operation import IntegrationOperationCreateRequest
from app.schemas.integration.provider import IntegrationCreateRequest


def configured_operation(**updates: object) -> IntegrationOperationCreateRequest:
    """A valid operation, so each test can invalidate exactly one thing."""
    values: dict[str, object] = {
        "code": "lookup",
        "method": "GET",
        "path_template": "/lookup/{id}",
        "connect_timeout_ms": 10,
        "read_timeout_ms": 20,
        "max_retries": 1,
        "retry_base_ms": 1,
        "retry_max_ms": 2,
        "idempotent": True,
        "fields": [
            {
                "direction": "REQUEST",
                "location": "PATH",
                "key": "id",
                "wire_path": "id",
                "value_source": "CALLER",
                "value_type": "STRING",
                "required": True,
            }
        ],
    }
    values.update(updates)
    return IntegrationOperationCreateRequest.model_validate(values)


def configured_integration(**updates: object) -> IntegrationCreateRequest:
    """A valid provider carrying one operation."""
    values: dict[str, object] = {
        "code": "catalog",
        "display_name": "Catalog",
        "base_url": "https://catalog.example.com",
        "operations": [configured_operation()],
    }
    values.update(updates)
    return IntegrationCreateRequest.model_validate(values)


def request_field(**updates: object) -> IntegrationFieldCreateRequest:
    """A valid outbound field to mutate one attribute of at a time."""
    values: dict[str, object] = {
        "direction": "REQUEST",
        "location": "QUERY",
        "key": "query",
        "wire_path": "query",
        "value_source": "CALLER",
        "value_type": "STRING",
        "required": True,
    }
    values.update(updates)
    return IntegrationFieldCreateRequest.model_validate(values)


def response_field(**updates: object) -> IntegrationFieldCreateRequest:
    """A valid inbound body field to mutate one attribute of at a time."""
    values: dict[str, object] = {
        "direction": "RESPONSE",
        "location": "BODY",
        "key": "result",
        "wire_path": "/result",
        "value_type": "STRING",
        "required": True,
    }
    values.update(updates)
    return IntegrationFieldCreateRequest.model_validate(values)
