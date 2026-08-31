# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.integration.field import IntegrationField
from app.models.integration.operation import IntegrationOperation
from app.models.integration.provider import Integration
from app.models.integration.secret import IntegrationSecret
from app.schemas.integration.field import IntegrationFieldCreateRequest
from app.schemas.integration.operation import IntegrationOperationCreateRequest
from app.schemas.integration.provider import IntegrationCreateInternal, IntegrationUpdateInternal


# ============================================================
# Classes
# ============================================================

class IntegrationProviderRepository:
    """The provider aggregate root: its own rows, and its children's rows.

    Secret and operation each own their own direct queries in their own file
    (backend-repository-files.md). What stays here is what only the aggregate
    root can do: create and update the whole tree in one transaction, because
    an operation's fields and a provider's secrets are children of *this*
    write, not of a caller who fetched them separately.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, integration_id: UUID) -> Integration | None:
        result = await self.session.execute(
            select(Integration).where(Integration.id == integration_id).options(*self._options())
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Integration | None:
        result = await self.session.execute(
            select(Integration).where(Integration.code == code).options(*self._options())
        )
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 100) -> list[Integration]:
        result = await self.session.execute(
            select(Integration)
            .order_by(Integration.code)
            .offset(offset)
            .limit(limit)
            .options(*self._options())
        )
        return list(result.scalars().unique().all())

    async def find_stale(self, older_than: datetime) -> list[Integration]:
        result = await self.session.execute(
            select(Integration).where(Integration.created_at < older_than).options(*self._options())
        )
        return list(result.scalars().unique().all())

    async def create(self, data: IntegrationCreateInternal) -> Integration:
        secrets = [
            IntegrationSecret(
                **secret.model_dump(), created_by=data.created_by, updated_by=data.created_by
            )
            for secret in data.secrets
        ]
        provider = Integration(
            code=data.code,
            display_name=data.display_name,
            base_url=data.base_url,
            enabled=data.enabled,
            created_by=data.created_by,
            updated_by=data.created_by,
            secrets=secrets,
            operations=[
                self._operation(operation, data.created_by, {s.name: s for s in secrets})
                for operation in data.operations
            ],
        )
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def update(self, provider: Integration, data: IntegrationUpdateInternal) -> Integration:
        updates = data.model_dump(exclude_unset=True, exclude={"operations", "updated_by"})
        for field, value in updates.items():
            setattr(provider, field, value)
        provider.updated_by = data.updated_by
        if data.operations is not None:
            by_name = {secret.name: secret for secret in provider.secrets}
            # Delete the old set and flush before inserting the new one: the unit
            # of work inserts children before deleting orphans, so re-sending an
            # existing code violated uq_integration_operation_provider_code and
            # surfaced as a 500 (measured).
            for existing in list(provider.operations):
                await self.session.delete(existing)
            await self.session.flush()
            provider.operations = [
                self._operation(operation, data.updated_by, by_name)
                for operation in data.operations
            ]
        await self.session.flush()
        return provider

    async def delete(self, provider: Integration) -> None:
        await self.session.delete(provider)

    @staticmethod
    def _options():
        """Eager-load the whole configuration tree: reads happen after commit."""
        return (
            selectinload(Integration.secrets),
            selectinload(Integration.operations)
            .selectinload(IntegrationOperation.fields)
            .selectinload(IntegrationField.secret),
        )

    @classmethod
    def _operation(
        cls,
        data: IntegrationOperationCreateRequest,
        actor: str,
        secrets: dict[str, IntegrationSecret],
    ) -> IntegrationOperation:
        return IntegrationOperation(
            code=data.code,
            method=data.method,
            path_template=data.path_template,
            request_media_type=data.request_media_type,
            response_format=data.response_format,
            response_root=data.response_root,
            connect_timeout_ms=data.connect_timeout_ms,
            read_timeout_ms=data.read_timeout_ms,
            max_retries=data.max_retries,
            retry_base_ms=data.retry_base_ms,
            retry_max_ms=data.retry_max_ms,
            idempotent=data.idempotent,
            request_schema=data.request_schema,
            enabled=data.enabled,
            created_by=actor,
            updated_by=actor,
            fields=[cls._field(field, actor, secrets) for field in data.fields],
        )

    @staticmethod
    def _field(
        data: IntegrationFieldCreateRequest, actor: str, secrets: dict[str, IntegrationSecret]
    ) -> IntegrationField:
        values = data.model_dump(exclude={"secret_name"})
        secret = None if data.secret_name is None else secrets[data.secret_name]
        return IntegrationField(**values, secret=secret, created_by=actor, updated_by=actor)
