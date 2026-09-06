# ============================================================
# Imports
# ============================================================

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
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

    async def list_pool(
        self, provider_code: str, now: datetime
    ) -> dict[str, list[IntegrationSecret]]:
        """Every grouped, enabled, unspent secret of one provider, by group.

        Ordered by name inside a group so two processes agree on the sequence
        and a round-robin offset means the same thing to both. A member whose
        `exhausted_until` is still ahead is not a candidate; one whose window
        has passed is, without anyone clearing the column.
        """
        result = await self.session.execute(
            select(IntegrationSecret)
            .join(Integration, Integration.id == IntegrationSecret.provider_id)
            .where(
                Integration.code == provider_code,
                IntegrationSecret.rotation_group.is_not(None),
                IntegrationSecret.enabled.is_(True),
                (IntegrationSecret.exhausted_until.is_(None))
                | (IntegrationSecret.exhausted_until <= now),
            )
            .order_by(IntegrationSecret.rotation_group, IntegrationSecret.name)
        )
        pool: dict[str, list[IntegrationSecret]] = {}
        for secret in result.scalars():
            pool.setdefault(str(secret.rotation_group), []).append(secret)
        return pool

    async def mark_exhausted(self, secret_id: UUID, until: datetime, actor: str) -> None:
        """Record that a member answered the quota code, in one statement.

        A Core UPDATE and not a loaded row: the job that hits the quota and the
        endpoint that hits it in the same second must both succeed, and the
        optimistic lock would fail the second one for a column no reader
        compares (`revoke_user_tokens` is the precedent).
        """
        await self.session.execute(
            update(IntegrationSecret)
            .where(IntegrationSecret.id == secret_id)
            .values(exhausted_until=until, updated_at=until, updated_by=actor)
        )

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
            rotation_group=data.rotation_group,
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
