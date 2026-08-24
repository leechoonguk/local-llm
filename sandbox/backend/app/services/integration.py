# ============================================================
# Imports
# ============================================================

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

import httpx2
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, IntegrationConfigurationError, NotFoundError
from app.core.integration import (
    PAGING_FAMILIES,
    PAGING_KEYS,
    IntegrationClient,
    IntegrationExecutionResult,
)
from app.models.integration import Integration, IntegrationOperation, IntegrationSecret
from app.repositories.integration import IntegrationRepository
from app.schemas.integration import (
    IntegrationCreateInternal,
    IntegrationCreateRequest,
    IntegrationFieldCreateRequest,
    IntegrationOperationCreateRequest,
    IntegrationSecretCreateRequest,
    IntegrationUpdateInternal,
    IntegrationUpdateRequest,
)


# ============================================================
# Constants
# ============================================================

CODE_PATTERN = re.compile(r"^[a-z0-9-]+$")
RESULT_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
CONTEXT_KEYS = frozenset({"request_id", "correlation_id", "tenant_id", "actor_id"})
HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
SENSITIVE_HEADER_TERMS = ("token", "secret", "key", "credential")
FORBIDDEN_REQUEST_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "upgrade",
        "proxy-authorization",
        "te",
        "trailer",
    }
)


# ============================================================
# Classes
# ============================================================

class IntegrationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.integration_repository = IntegrationRepository(session)

    async def get_integration(self, integration_id: UUID) -> Integration:
        provider = await self.integration_repository.get(integration_id)
        if provider is None:
            raise NotFoundError(integration_id)
        return provider

    async def list_integrations(self, offset: int = 0, limit: int = 100) -> list[Integration]:
        return await self.integration_repository.list(offset, limit)

    async def find_stale(self, older_than: datetime) -> list[Integration]:
        return await self.integration_repository.find_stale(older_than)

    async def create_integration(
        self, data: IntegrationCreateRequest, created_by: str
    ) -> Integration:
        self._validate_create(data)
        internal = IntegrationCreateInternal(**data.model_dump(), created_by=created_by)
        async with self.session.begin():
            if await self.integration_repository.get_by_code(data.code) is not None:
                raise ConflictError("Integration provider code already exists")
            provider = await self.integration_repository.create(internal)
        return await self.get_integration(provider.id)

    async def update_integration(
        self, integration_id: UUID, data: IntegrationUpdateRequest, updated_by: str
    ) -> Integration:
        internal = IntegrationUpdateInternal(
            **data.model_dump(exclude_unset=True), updated_by=updated_by
        )
        async with self.session.begin():
            provider = await self.integration_repository.get(integration_id)
            if provider is None:
                raise NotFoundError(integration_id)
            self._validate_update(data, {secret.name for secret in provider.secrets})
            await self.integration_repository.update(provider, internal)
        return await self.get_integration(integration_id)

    async def create_secret(
        self, integration_id: UUID, data: IntegrationSecretCreateRequest, created_by: str
    ) -> IntegrationSecret:
        async with self.session.begin():
            provider = await self.integration_repository.get(integration_id)
            if provider is None:
                raise NotFoundError(integration_id)
            if await self.integration_repository.get_secret(provider.id, data.name) is not None:
                raise ConflictError(f"Secret '{data.name}' already exists for this provider")
            return await self.integration_repository.create_secret(provider, data, created_by)

    async def list_secrets(
        self, integration_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[IntegrationSecret]:
        provider = await self.integration_repository.get(integration_id)
        if provider is None:
            raise NotFoundError(integration_id)
        return await self.integration_repository.list_secrets(provider.id, offset, limit)

    async def delete_secret(self, integration_id: UUID, name: str) -> None:
        """Refuse to orphan a field: the secret FK is ON DELETE RESTRICT."""
        async with self.session.begin():
            provider = await self.integration_repository.get(integration_id)
            if provider is None:
                raise NotFoundError(integration_id)
            secret = await self.integration_repository.get_secret(provider.id, name)
            if secret is None:
                raise NotFoundError(integration_id)
            if await self.integration_repository.count_secret_references(secret.id) > 0:
                raise ConflictError(f"Secret '{name}' is still referenced by a request field")
            await self.integration_repository.delete_secret(secret)

    async def delete_integration(self, integration_id: UUID) -> None:
        async with self.session.begin():
            provider = await self.integration_repository.get(integration_id)
            if provider is None:
                raise NotFoundError(integration_id)
            await self.integration_repository.delete(provider)

    async def get_operation(self, provider_code: str, operation_code: str) -> IntegrationOperation:
        operation = await self.integration_repository.get_operation(provider_code, operation_code)
        if operation is None or not operation.provider.enabled or not operation.enabled:
            raise IntegrationConfigurationError("Integration operation is unavailable")
        return operation

    async def execute_operation(
        self,
        provider_code: str,
        operation_code: str,
        inputs: Mapping[str, object],
        *,
        client: httpx2.AsyncClient | None = None,
    ) -> IntegrationExecutionResult:
        """Execute a configured operation against the external API.

        Resolves the operation from the database and runs it through
        IntegrationClient — the only sanctioned outbound HTTP path. The
        caller-supplied inputs map to CALLER-sourced request fields.
        """
        integration_client = await IntegrationClient.from_database(
            session=self.session,
            provider_code=provider_code,
            operation_code=operation_code,
            client=client,
        )
        try:
            return await integration_client.execute(inputs)
        finally:
            await integration_client.aclose()

    def _validate_create(self, data: IntegrationCreateRequest) -> None:
        self._validate_provider(data.code, data.base_url)
        names = {secret.name for secret in data.secrets}
        if len(names) != len(data.secrets):
            raise IntegrationConfigurationError("Secret names must be unique per provider")
        self._validate_operations(data.operations, names)

    def _validate_update(self, data: IntegrationUpdateRequest, secret_names: set[str]) -> None:
        if data.base_url is not None:
            self._validate_base_url(data.base_url)
        if data.operations is not None:
            self._validate_operations(data.operations, secret_names)

    @staticmethod
    def _validate_provider(code: str, base_url: str) -> None:
        if CODE_PATTERN.fullmatch(code) is None:
            raise IntegrationConfigurationError(
                "Provider code must use lowercase letters, digits, and hyphens"
            )
        IntegrationService._validate_base_url(base_url)

    @staticmethod
    def _validate_base_url(base_url: str) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise IntegrationConfigurationError("Base URL must be an HTTPS origin")

    def _validate_operations(
        self, operations: list[IntegrationOperationCreateRequest], secret_names: set[str]
    ) -> None:
        seen_codes: set[str] = set()
        for operation in operations:
            if CODE_PATTERN.fullmatch(operation.code) is None or operation.code in seen_codes:
                raise IntegrationConfigurationError(
                    "Operation codes must be unique lowercase identifiers"
                )
            seen_codes.add(operation.code)
            self._validate_operation(operation, secret_names)

    def _validate_operation(
        self, operation: IntegrationOperationCreateRequest, secret_names: set[str]
    ) -> None:
        if (
            not operation.path_template.startswith("/")
            or "//" in operation.path_template
            or any(token in operation.path_template for token in ("?", "#", "..", "://"))
        ):
            raise IntegrationConfigurationError("Operation path must be a safe relative path")
        if operation.read_timeout_ms < operation.connect_timeout_ms:
            raise IntegrationConfigurationError("Read timeout must be at least the connect timeout")
        if operation.retry_max_ms < operation.retry_base_ms:
            raise IntegrationConfigurationError("Retry maximum must be at least the retry base")
        if operation.request_schema is not None:
            self._validate_schema(operation.request_schema, "Request schema")
        self._validate_response_root(operation)
        self._validate_fields(operation, secret_names)

    @staticmethod
    def _validate_response_root(operation: IntegrationOperationCreateRequest) -> None:
        """A paging operation names the page it returns; anything else may map a record.

        Mapping is the only response contract, so `response_root` carries the whole
        decision: absent maps one record through absolute pointers, present maps every
        element of the page it names. Two shapes are refused because both were
        measured defects: a root that is not a pointer resolves to nothing, and a root
        that pins an index (`/body/items/0`) returned one record however large the page
        was, which made the page-size input unobservable.
        """
        root = operation.response_root
        if root is not None:
            if not root.startswith("/"):
                raise IntegrationConfigurationError(
                    "A response root must be a JSON Pointer starting with '/'"
                )
            if re.search(r"/\d+$", root):
                raise IntegrationConfigurationError(
                    f"A response root must name the page, not one record in it: {root}"
                )
        request_keys = {field.key for field in operation.fields if field.direction == "REQUEST"}
        paging = request_keys & PAGING_KEYS
        if not paging:
            return
        family = next(
            (name for name, keys in PAGING_FAMILIES.items() if paging == keys),
            None,
        )
        if family is None:
            raise IntegrationConfigurationError(
                f"Paging inputs {sorted(paging)} are not one whole family — "
                f"declare exactly one of {sorted(PAGING_FAMILIES)}"
            )
        if root is None:
            raise IntegrationConfigurationError(
                "A paging operation must name the page it returns in response_root"
            )

    @staticmethod
    def _validate_schema(schema: dict[str, object], label: str) -> None:
        if IntegrationService._contains_external_ref(schema):
            raise IntegrationConfigurationError(f"{label} cannot use external references")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise IntegrationConfigurationError(f"{label} is invalid: {exc.message}") from exc

    @staticmethod
    def _contains_external_ref(value: object) -> bool:
        if isinstance(value, dict):
            return any(
                key == "$ref"
                and isinstance(child, str)
                and not child.startswith("#")
                or IntegrationService._contains_external_ref(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(IntegrationService._contains_external_ref(child) for child in value)
        return False

    def _validate_fields(
        self, operation: IntegrationOperationCreateRequest, secret_names: set[str]
    ) -> None:
        seen_keys: set[tuple[str, str]] = set()
        seen_wires: set[tuple[str, str, str]] = set()
        body_fields = False
        for field in operation.fields:
            key_id = (field.direction, field.key)
            wire_id = (field.direction, field.location, field.wire_path)
            if key_id in seen_keys or wire_id in seen_wires:
                raise IntegrationConfigurationError(
                    f"Field keys and wire paths must be unique per direction: {field.key}"
                )
            seen_keys.add(key_id)
            seen_wires.add(wire_id)
            self._validate_match(field)
            if field.direction == "REQUEST":
                body_fields = self._validate_request_field(field, secret_names) or body_fields
            else:
                self._validate_response_field(field)
        if body_fields and operation.request_schema is None:
            raise IntegrationConfigurationError("Body fields require a request schema")

    @staticmethod
    def _validate_match(field: IntegrationFieldCreateRequest) -> None:
        """A matched value is one the provider sends: a response header, or a verdict.

        `match_mode` says "this value must hold", which only means something for a value
        the provider chose. Two locations carry one: a RESPONSE header, and a RESPONSE
        ENVELOPE row — the body wrapper that decides whether the answer counts at all.
        Refusing the second here made the I1250 configuration the app serves impossible
        to create through the app's own API.
        """
        is_matchable = field.direction == "RESPONSE" and field.location in {"HEADER", "ENVELOPE"}
        if not is_matchable:
            if field.match_mode is not None or field.expected_values is not None:
                raise IntegrationConfigurationError(
                    f"Value matching applies to response headers and envelopes only: {field.key}"
                )
            return
        expected_count = len(field.expected_values or [])
        if (
            (field.match_mode == "EXACT" and expected_count != 1)
            or (field.match_mode == "ONE_OF" and expected_count == 0)
            or (field.match_mode in {None, "IGNORE", "PRESENT"} and expected_count != 0)
        ):
            raise IntegrationConfigurationError(
                f"Expected values do not match the field's mode: {field.key}"
            )

    def _validate_request_field(
        self, field: IntegrationFieldCreateRequest, secret_names: set[str]
    ) -> bool:
        """Validate one outbound field; returns True when it writes the body."""
        self._validate_source(field, secret_names)
        if field.location == "BODY":
            if not field.wire_path.startswith("/"):
                raise IntegrationConfigurationError("Body fields must use JSON Pointer paths")
            return True
        if field.location == "HEADER":
            self._validate_request_header(field.wire_path, field.value_source, field.sensitive)
        elif not HEADER_NAME_PATTERN.fullmatch(field.wire_path):
            raise IntegrationConfigurationError("Request field path is invalid")
        return False

    @staticmethod
    def _validate_response_field(field: IntegrationFieldCreateRequest) -> None:
        if field.value_source is not None or field.secret_name is not None:
            raise IntegrationConfigurationError(
                f"Response fields never carry a value source: {field.key}"
            )
        if RESULT_KEY_PATTERN.fullmatch(field.key) is None:
            raise IntegrationConfigurationError(f"Response field key is invalid: {field.key}")
        if field.location == "BODY" and not field.wire_path.startswith("/"):
            raise IntegrationConfigurationError("Response body fields must use JSON Pointer paths")
        if field.location == "HEADER" and HEADER_NAME_PATTERN.fullmatch(field.wire_path) is None:
            raise IntegrationConfigurationError(f"Response header name is invalid: {field.key}")
        if field.location in {"PATH", "QUERY"}:
            raise IntegrationConfigurationError(
                f"Response fields read the body or a header only: {field.key}"
            )

    @staticmethod
    def _validate_source(field: IntegrationFieldCreateRequest, secret_names: set[str]) -> None:
        """Each source owns exactly one value column; a secret is named, never inlined."""
        source = field.value_source
        if source is None:
            raise IntegrationConfigurationError(
                f"Request fields need a value source: {field.key}"
            )
        if source == "SECRET":
            if field.secret_name is None or field.value is not None:
                raise IntegrationConfigurationError(
                    f"Secret fields reference a provider secret by name: {field.key}"
                )
            if field.secret_name not in secret_names:
                raise IntegrationConfigurationError(
                    f"Unknown provider secret: {field.secret_name}"
                )
            return
        if field.secret_name is not None:
            raise IntegrationConfigurationError(
                f"Only SECRET fields reference a secret: {field.key}"
            )
        if source == "LITERAL" and field.value is None:
            raise IntegrationConfigurationError(f"Literal fields need a value: {field.key}")
        if source == "CONTEXT" and field.key not in CONTEXT_KEYS:
            raise IntegrationConfigurationError(f"Unknown request context key: {field.key}")

    @staticmethod
    def _validate_request_header(
        header: str, value_source: str | None, sensitive: bool
    ) -> None:
        normalized = header.lower()
        if normalized == "x-request-id" or HEADER_NAME_PATTERN.fullmatch(header) is None:
            raise IntegrationConfigurationError("Request header name is reserved or invalid")
        if normalized in FORBIDDEN_REQUEST_HEADERS:
            raise IntegrationConfigurationError(
                "Request header is controlled by the HTTP transport"
            )
        is_secret = normalized in {"authorization", "cookie", "x-api-key"} or any(
            term in normalized for term in SENSITIVE_HEADER_TERMS
        )
        if is_secret and (value_source != "SECRET" or not sensitive):
            raise IntegrationConfigurationError("Sensitive headers require a secret reference")
