# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.integration import (
    Integration,
    IntegrationField,
    IntegrationOperation,
    IntegrationSecret,
)
from app.schemas.integration import (
    IntegrationCreateInternal,
    IntegrationFieldCreateRequest,
    IntegrationOperationCreateRequest,
    IntegrationSecretCreateRequest,
    IntegrationUpdateInternal,
)


# ============================================================
# Classes
# ============================================================

class IntegrationRepository:
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

    async def get_operation(
        self, provider_code: str, operation_code: str
    ) -> IntegrationOperation | None:
        result = await self.session.execute(
            select(IntegrationOperation)
            .join(IntegrationOperation.provider)
            .where(
                Integration.code == provider_code,
                IntegrationOperation.code == operation_code,
            )
            .options(
                selectinload(IntegrationOperation.provider),
                selectinload(IntegrationOperation.fields).selectinload(IntegrationField.secret),
            )
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

    async def get_secret(self, provider_id: UUID, name: str) -> IntegrationSecret | None:
        result = await self.session.execute(
            select(IntegrationSecret).where(
                IntegrationSecret.provider_id == provider_id, IntegrationSecret.name == name
            )
        )
        return result.scalar_one_or_none()

    async def list_secrets(
        self, provider_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[IntegrationSecret]:
        result = await self.session.execute(
            select(IntegrationSecret)
            .where(IntegrationSecret.provider_id == provider_id)
            .order_by(IntegrationSecret.name)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_secret_references(self, secret_id: UUID) -> int:
        result = await self.session.execute(
            select(IntegrationField.id).where(IntegrationField.secret_id == secret_id)
        )
        return len(list(result.scalars().all()))

    async def create_secret(
        self, provider: Integration, data: IntegrationSecretCreateRequest, actor: str
    ) -> IntegrationSecret:
        secret = IntegrationSecret(
            provider_id=provider.id,
            name=data.name,
            value=data.value,
            description=data.description,
            enabled=data.enabled,
            created_by=actor,
            updated_by=actor,
        )
        self.session.add(secret)
        await self.session.flush()
        return secret

    async def delete_secret(self, secret: IntegrationSecret) -> None:
        await self.session.delete(secret)

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
