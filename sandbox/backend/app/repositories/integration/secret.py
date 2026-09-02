# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration.field import IntegrationField
from app.models.integration.provider import Integration
from app.models.integration.secret import IntegrationSecret
from app.schemas.integration.secret import (
    IntegrationSecretCreateRequest,
    IntegrationSecretUpdateRequest,
)


# ============================================================
# Classes
# ============================================================


class IntegrationSecretRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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

    async def count_secrets(self, provider_id: UUID) -> int:
        """How many rows the unwindowed `list_secrets` would return."""
        result = await self.session.execute(
            select(func.count())
            .select_from(IntegrationSecret)
            .where(IntegrationSecret.provider_id == provider_id)
        )
        return result.scalar_one()

    async def count_secret_references(self, secret_id: UUID) -> int:
        """A column projection, not IntegrationField's CRUD in the wrong file.

        This is the referential-integrity check a delete needs: is the secret
        still used. It does not read a field's other columns and it never writes
        one (backend-repository-files.md).
        """
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

    async def update_secret(
        self, secret: IntegrationSecret, data: IntegrationSecretUpdateRequest, actor: str
    ) -> IntegrationSecret:
        """Replace in place, so the name every field references keeps resolving.

        The refresh is not decoration: `updated_at` is a server-side `onupdate`, so
        after the flush the attribute is stale and the response would lazy-load it
        outside the transaction — `MissingGreenlet`, measured.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(secret, field, value)
        secret.updated_by = actor
        await self.session.flush()
        await self.session.refresh(secret)
        return secret

    async def delete_secret(self, secret: IntegrationSecret) -> None:
        await self.session.delete(secret)
