"""Shared fixtures: an isolated SQLite client, auth headers, and a hermetic env.

Every fixture here exists to keep a test from depending on something outside its
own file — the production engine, an ambient environment variable, or a token
minted by another test.
"""

import os
import re
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.settings import Settings, settings
from app.main import app
from app.models.base import Base
from app.models.batch.run import BatchRun  # noqa: F401 — on metadata
from app.models.batch.schedule import BatchSchedule  # noqa: F401 — on metadata
from app.models.batch.step import BatchStep  # noqa: F401 — on metadata
from app.models.food.barcode import FoodBarcode  # noqa: F401 — on metadata
from app.models.food.business import FoodBusiness  # noqa: F401 — on metadata
from app.models.food.common_standard_exclusion import (
    FoodCommonStandardExclusion,  # noqa: F401 — on metadata
)
from app.models.food.common_standard_type import FoodCommonStandardType  # noqa: F401 — on metadata
from app.models.food.item_report import FoodItemReport  # noqa: F401 — on metadata
from app.models.food.item_report_declaration import (  # noqa: F401 — on metadata
    FoodItemReportDeclaration,
)
from app.models.food.item_report_ingredient import (  # noqa: F401 — on metadata
    FoodItemReportIngredient,
)
from app.models.food.label import FoodLabel  # noqa: F401 — on metadata
from app.models.food.label_allergen import FoodLabelAllergen  # noqa: F401 — on metadata
from app.models.food.label_caution import FoodLabelCaution  # noqa: F401 — on metadata
from app.models.food.label_packaging import FoodLabelPackaging  # noqa: F401 — on metadata
from app.models.food.ledger_additive_manufacturing_closure import (  # noqa: F401 — on metadata
    FoodLedgerAdditiveManufacturingClosure,
)
from app.models.food.ledger_admin_disposition import (  # noqa: F401 — on metadata
    FoodLedgerAdminDisposition,
)
from app.models.food.ledger_barcode import FoodLedgerBarcode  # noqa: F401 — on metadata
from app.models.food.ledger_business import (  # noqa: F401 — on metadata
    FoodLedgerBusiness,
)
from app.models.food.ledger_business_site import (  # noqa: F401 — on metadata
    FoodLedgerBusinessSite,
)
from app.models.food.ledger_collection_inspection import (  # noqa: F401 — on metadata
    FoodLedgerCollectionInspection,
)
from app.models.food.ledger_common_standard import (
    FoodLedgerCommonStandard,  # noqa: F401 — on metadata
)
from app.models.food.ledger_common_standard_exclusion import (  # noqa: F401 — on metadata
    FoodLedgerCommonStandardExclusion,
)
from app.models.food.ledger_common_standard_type import (  # noqa: F401 — on metadata
    FoodLedgerCommonStandardType,
)
from app.models.food.ledger_haccp_label import FoodLedgerHaccpLabel  # noqa: F401 — on metadata
from app.models.food.ledger_health_functional_closure import (  # noqa: F401 — on metadata
    FoodLedgerHealthFunctionalClosure,
)
from app.models.food.ledger_health_functional_item_report import (  # noqa: F401 — on metadata
    FoodLedgerHealthFunctionalItemReport,
)
from app.models.food.ledger_health_functional_production import (  # noqa: F401 — on metadata
    FoodLedgerHealthFunctionalProduction,
)
from app.models.food.ledger_import_business_closure import (  # noqa: F401 — on metadata
    FoodLedgerImportBusinessClosure,
)
from app.models.food.ledger_import_food_label import (  # noqa: F401 — on metadata
    FoodLedgerImportFoodLabel,
)
from app.models.food.ledger_individual_standard import (  # noqa: F401 — on metadata
    FoodLedgerIndividualStandard,
)
from app.models.food.ledger_inspection_failure import (  # noqa: F401 — on metadata
    FoodLedgerInspectionFailure,
)
from app.models.food.ledger_item_report import FoodLedgerItemReport  # noqa: F401 — on metadata
from app.models.food.ledger_item_report_raw_material import (  # noqa: F401 — on metadata
    FoodLedgerItemReportRawMaterial,
)
from app.models.food.ledger_livestock_item_report_raw_material import (  # noqa: F401 — on metadata
    FoodLedgerLivestockItemReportRawMaterial,
)
from app.models.food.ledger_livestock_processing_closure import (  # noqa: F401 — on metadata
    FoodLedgerLivestockProcessingClosure,
)
from app.models.food.ledger_livestock_production import (  # noqa: F401 — on metadata
    FoodLedgerLivestockProduction,
)
from app.models.food.ledger_manufacturing_closure import (  # noqa: F401 — on metadata
    FoodLedgerManufacturingClosure,
)
from app.models.food.ledger_meat_packaging_closure import (  # noqa: F401 — on metadata
    FoodLedgerMeatPackagingClosure,
)
from app.models.food.ledger_nutrition import FoodLedgerNutrition  # noqa: F401 — on metadata
from app.models.food.ledger_product_classification import (  # noqa: F401 — on metadata
    FoodLedgerProductClassification,
)
from app.models.food.ledger_production import FoodLedgerProduction  # noqa: F401 — on metadata
from app.models.food.ledger_qr_allergy import FoodLedgerQrAllergy  # noqa: F401 — on metadata
from app.models.food.ledger_qr_caution import FoodLedgerQrCaution  # noqa: F401 — on metadata
from app.models.food.ledger_qr_label import FoodLedgerQrLabel  # noqa: F401 — on metadata
from app.models.food.ledger_qr_manufacture import (
    FoodLedgerQrManufacture,  # noqa: F401 — on metadata
)
from app.models.food.ledger_qr_nutrition import FoodLedgerQrNutrition  # noqa: F401 — on metadata
from app.models.food.ledger_qr_packaging import FoodLedgerQrPackaging  # noqa: F401 — on metadata
from app.models.food.ledger_qr_raw_material import (
    FoodLedgerQrRawMaterial,  # noqa: F401 — on metadata
)
from app.models.food.ledger_qr_storage import FoodLedgerQrStorage  # noqa: F401 — on metadata
from app.models.food.ledger_raw_material import FoodLedgerRawMaterial  # noqa: F401 — on metadata
from app.models.food.ledger_recall import FoodLedgerRecall  # noqa: F401 — on metadata
from app.models.food.ledger_test_item import FoodLedgerTestItem  # noqa: F401 — on metadata
from app.models.food.nutrition import FoodNutrition  # noqa: F401 — on metadata
from app.models.food.product_classification import (  # noqa: F401 — on metadata
    FoodProductClassification,
)
from app.models.food.raw_material import FoodRawMaterial  # noqa: F401 — on metadata
from app.models.food.safety_record import FoodSafetyRecord  # noqa: F401 — on metadata
from app.models.food.standard import FoodStandard  # noqa: F401 — on metadata
from app.models.food.test_item import FoodTestItem  # noqa: F401 — on metadata
from app.models.integration.call import IntegrationCall  # noqa: F401 — on metadata
from app.models.integration.field import IntegrationField  # noqa: F401 — on metadata
from app.models.integration.operation import IntegrationOperation  # noqa: F401 — on metadata
from app.models.integration.provider import Integration  # noqa: F401 — on metadata
from app.models.integration.secret import IntegrationSecret  # noqa: F401 — on metadata
from app.models.refresh import Refresh  # noqa: F401 — on metadata
from app.models.user import User  # noqa: F401 — on metadata


# Prevent scheduler from starting during tests
settings.env = "test"


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Hide ambient environment variables that map to Settings fields.

    `Settings(_env_file=None, ...)` bypasses the .env file but **not**
    `os.environ`: pydantic-settings reads the process environment first. A shell
    (or CI job) that exported the root .env — `REDIS_URL`, `ITEMS_PER_USER`, … —
    therefore changed what the settings tests observed, and the same commit was
    green in one terminal and red in another.

    The names come from the model, not a hardcoded list, so a new field cannot
    reintroduce the leak. What was hidden is returned, because one test starts
    a subprocess that imports the app and needs the suite's own environment
    (`[tool.pytest.ini_options] env`) - the process it starts, not this one.
    """
    hidden: dict[str, str] = {}
    for field in Settings.model_fields:
        for name in (field.upper(), field):
            value = os.environ.get(name)
            if value is not None:
                hidden[name] = value
            monkeypatch.delenv(name, raising=False)
    return hidden


@pytest.fixture()
async def client() -> AsyncIterator[TestClient]:
    """Isolated in-memory SQLite client.

    The REAL get_session() dependency runs against a test engine swapped in
    place of the production one — the request lifecycle (session create /
    yield / close) is exercised, not a dependency override.
    """
    from app.dependencies import core as deps_core

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Point the session factory used by get_session() at the test engine.
    deps_core.async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    with TestClient(app) as c:
        yield c

    deps_core.async_session_factory = async_sessionmaker(  # reset for other fixtures
        engine, class_=AsyncSession, expire_on_commit=False
    )
    await engine.dispose()


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    """Create a test user and return Bearer auth headers."""
    client.post(
        "/api/v1/user/",
        json={"username": "tester", "email": "tester@example.com", "password": "secret-pass"},
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "tester", "password": "secret-pass"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
async def engine():
    """In-memory SQLite engine with all tables — for repository/service tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with_postgresql_functions(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


def with_postgresql_functions(engine: AsyncEngine) -> None:
    """Give the SQLite double the PostgreSQL functions the app's SQL may name.

    `regexp_replace(text, pattern, replacement, flags)` is the one PostgreSQL
    function this project's SQL has needed; SQLite has no regex at all, so the
    function is Python's. Registered on connect, before the first connection -
    the pool is static, so that is the only one.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _register(dbapi_connection, _record) -> None:
        dbapi_connection.create_function("regexp_replace", 4, _regexp_replace)


def _regexp_replace(text: str | None, pattern: str, replacement: str, _flags: str) -> str | None:
    return None if text is None else re.sub(pattern, replacement, text)


@pytest.fixture()
def factory(engine):
    """Session factory bound to the in-memory engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
