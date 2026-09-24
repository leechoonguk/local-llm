"""replace the provider jobs with one job per ledger

Revision ID: 259
Revises: 258
Create Date: 2026-09-15

식품안전나라 answers `ERROR-503 09시~19시에는 서비스가 제한됩니다` to every
service and every key during its own working day (measured 2026-09-15 across
I0490, I2620, I1250, C006, I0030, I0300, I1420, I0310, C005 and the three
keys). The night is therefore 19:00-09:00, fourteen hours, and this provider's
feeds are about eighteen hours of walking - so they do not fit one run, in any
order.

One schedule row per ledger, laid across the weekend's nights:

    Friday   19:00  the feeds that exist today, smallest first (~3.5 h),
                    then 건강기능식품 생산실적 (0.1 h) at 06:00
    Saturday 19:00  식품 생산실적 I0300 (5.7 h, walked year by year)
    Sunday   19:00  축산물 생산실적 I1420 (8.5 h, walked year by year)

data.go.kr has no such window - it answered every call at midday - and its
eleven feeds keep the same Friday night, an hour behind, so one reader sees one
night's work in one place.

The jobs of one provider still take turns: the queue moved from a tuple inside
one job to a lock in the scheduler (`JOB_PROVIDERS`), where a feed waits only
for whatever is actually walking.

`derive_food_tables` moves to every day at 10:00 and stands down - SKIPPED,
with the reason - on the days a ledger job is still in flight.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.sql import column, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "259"
down_revision: str | Sequence[str] | None = "258"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DERIVE_JOB_ID = uuid5(NAMESPACE_URL, "fast-api-standard/batch/derive-food-tables")

# The two rows this revision retires, as revisions 110 and 247 left them.
RETIRED_JOBS: list[dict[str, object]] = [
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-mfds-ledgers"),
        "code": "sync_mfds_ledgers",
        "name": "Sync 식품안전나라 ledgers",
        "description": "Replaces every 식품안전나라 ledger with a whole pass of its feed.",
        "cron": "0 20 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-data-go-kr-ledgers"),
        "code": "sync_data_go_kr_ledgers",
        "name": "Sync data.go.kr ledgers",
        "description": "Replaces every data.go.kr ledger with a whole pass of its feed.",
        "cron": "0 20 * * 5",
    },
]

LEDGER_JOBS: list[dict[str, object]] = [
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-recall"),
        "code": "sync_food_ledger_recall",
        "name": "Sync food_ledger_recall",
        "description": (
            "Replaces the food_ledger_recall ledger with a whole pass of "
            "search-food-recall: 식품 회수·판매중지 (I0490), 376행 1창."
        ),
        "cron": "0 19 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-inspection-failure"),
        "code": "sync_food_ledger_inspection_failure",
        "name": "Sync food_ledger_inspection_failure",
        "description": (
            "Replaces the food_ledger_inspection_failure ledger with a whole pass of "
            "search-food-inspection-failure: 검사 부적합 (I2620), 572행 1창."
        ),
        "cron": "5 19 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-test-item"),
        "code": "sync_food_ledger_test_item",
        "name": "Sync food_ledger_test_item",
        "description": (
            "Replaces the food_ledger_test_item ledger with a whole pass of "
            "search-test-item: 시험항목 (I2710), 3,393행 118창."
        ),
        "cron": "10 19 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-product-classification"),
        "code": "sync_food_ledger_product_classification",
        "name": "Sync food_ledger_product_classification",
        "description": (
            "Replaces the food_ledger_product_classification ledger with a whole pass of "
            "search-product-classification: 식품분류 (I2500), 9,634행 331창."
        ),
        "cron": "25 19 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-common-standard-exclusion"),
        "code": "sync_food_ledger_common_standard_exclusion",
        "name": "Sync food_ledger_common_standard_exclusion",
        "description": (
            "Replaces the food_ledger_common_standard_exclusion ledger with a whole pass of "
            "search-common-standard-exclusion: 공통기준규격 적용제외 (I2610), 21행."
        ),
        "cron": "15 19 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-common-standard-type"),
        "code": "sync_food_ledger_common_standard_type",
        "name": "Sync food_ledger_common_standard_type",
        "description": (
            "Replaces the food_ledger_common_standard_type ledger with a whole pass of "
            "search-common-standard-type: 공통기준규격 유형 (I2590), 90행."
        ),
        "cron": "20 19 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-individual-standard"),
        "code": "sync_food_ledger_individual_standard",
        "name": "Sync food_ledger_individual_standard",
        "description": (
            "Replaces the food_ledger_individual_standard ledger with a whole pass of "
            "search-individual-standard: 개별기준규격 (I2580), 16,408행 21분."
        ),
        "cron": "0 20 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-common-standard"),
        "code": "sync_food_ledger_common_standard",
        "name": "Sync food_ledger_common_standard",
        "description": (
            "Replaces the food_ledger_common_standard ledger with a whole pass of "
            "search-common-standard: 공통기준규격 (I2600), 57,457행 2h06m - 이 provider 최장."
        ),
        "cron": "0 22 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-health-functional-item-report"),
        "code": "sync_food_ledger_health_functional_item_report",
        "name": "Sync food_ledger_health_functional_item_report",
        "description": (
            "Replaces the food_ledger_health_functional_item_report ledger with a whole pass of "
            "search-health-functional-item-report: 건강기능식품 품목제조신고 (I0030), 46,086행 47창."
        ),
        "cron": "35 19 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-barcode"),
        "code": "sync_food_ledger_barcode",
        "name": "Sync food_ledger_barcode",
        "description": (
            "Replaces the food_ledger_barcode ledger with a whole pass of "
            "search-barcode-product-info: 바코드연계제품정보 (C005), 259,669행 19분."
        ),
        "cron": "30 20 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-raw-material"),
        "code": "sync_food_ledger_raw_material",
        "name": "Sync food_ledger_raw_material",
        "description": (
            "Replaces the food_ledger_raw_material ledger with a whole pass of "
            "search-food-raw-material: 식품 원재료 (I2520), 130,830행 5분."
        ),
        "cron": "45 19 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-livestock-item-report-raw-material"),
        "code": "sync_food_ledger_livestock_item_report_raw_material",
        "name": "Sync food_ledger_livestock_item_report_raw_material",
        "description": (
            "Replaces the food_ledger_livestock_item_report_raw_material ledger with a whole pass of "
            "search-livestock-item-report-raw-material: 축산물 품목제조보고 원재료 (C006), 649,537행 37분."
        ),
        "cron": "0 21 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-item-report"),
        "code": "sync_food_ledger_item_report",
        "name": "Sync food_ledger_item_report",
        "description": (
            "Replaces the food_ledger_item_report ledger with a whole pass of "
            "search-food-item-report: 식품 품목제조보고 (I1250), 1,072,302행."
        ),
        "cron": "30 0 * * 6",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-item-report-raw-material"),
        "code": "sync_food_ledger_item_report_raw_material",
        "name": "Sync food_ledger_item_report_raw_material",
        "description": (
            "Replaces the food_ledger_item_report_raw_material ledger with a whole pass of "
            "search-food-item-report-raw-material: 품목제조보고 원재료 (C002), 1,072,136행."
        ),
        "cron": "30 3 * * 6",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-health-functional-production"),
        "code": "sync_food_ledger_health_functional_production",
        "name": "Sync food_ledger_health_functional_production",
        "description": (
            "Replaces the food_ledger_health_functional_production ledger with a whole pass of "
            "search-health-functional-production: 건강기능식품 생산실적 (I0310), 316,747행 연도별 0.1h."
        ),
        "cron": "0 6 * * 6",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-production"),
        "code": "sync_food_ledger_production",
        "name": "Sync food_ledger_production",
        "description": (
            "Replaces the food_ledger_production ledger with a whole pass of "
            "search-food-production: 식품 생산실적 (I0300), 7,927,213행 연도별 5.7h."
        ),
        "cron": "0 19 * * 6",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-livestock-production"),
        "code": "sync_food_ledger_livestock_production",
        "name": "Sync food_ledger_livestock_production",
        "description": (
            "Replaces the food_ledger_livestock_production ledger with a whole pass of "
            "search-livestock-production: 축산물 생산실적 (I1420), 3,397,141행 연도별 8.5h."
        ),
        "cron": "0 19 * * 0",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-import-food-label"),
        "code": "sync_food_ledger_import_food_label",
        "name": "Sync food_ledger_import_food_label",
        "description": (
            "Replaces the food_ledger_import_food_label ledger with a whole pass of "
            "search-import-food-label: 수입식품 한글표시사항 (B553748), 1,087,781행 66분."
        ),
        "cron": "0 20 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-qr-raw-material"),
        "code": "sync_food_ledger_qr_raw_material",
        "name": "Sync food_ledger_qr_raw_material",
        "description": (
            "Replaces the food_ledger_qr_raw_material ledger with a whole pass of "
            "search-food-qr-raw-material: 무료QR 원재료, 2,301행."
        ),
        "cron": "0 23 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-qr-label"),
        "code": "sync_food_ledger_qr_label",
        "name": "Sync food_ledger_qr_label",
        "description": (
            "Replaces the food_ledger_qr_label ledger with a whole pass of "
            "search-food-qr-label: 무료QR 표시사항, 2,278행."
        ),
        "cron": "10 23 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-qr-storage"),
        "code": "sync_food_ledger_qr_storage",
        "name": "Sync food_ledger_qr_storage",
        "description": (
            "Replaces the food_ledger_qr_storage ledger with a whole pass of "
            "search-food-qr-storage: 무료QR 보관방법, 2,868행."
        ),
        "cron": "20 23 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-qr-manufacture"),
        "code": "sync_food_ledger_qr_manufacture",
        "name": "Sync food_ledger_qr_manufacture",
        "description": (
            "Replaces the food_ledger_qr_manufacture ledger with a whole pass of "
            "search-food-qr-manufacture: 무료QR 품목제조정보, 2,976행."
        ),
        "cron": "30 23 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-qr-packaging"),
        "code": "sync_food_ledger_qr_packaging",
        "name": "Sync food_ledger_qr_packaging",
        "description": (
            "Replaces the food_ledger_qr_packaging ledger with a whole pass of "
            "search-food-qr-packaging: 무료QR 포장재질, 6,914행."
        ),
        "cron": "40 23 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-qr-caution"),
        "code": "sync_food_ledger_qr_caution",
        "name": "Sync food_ledger_qr_caution",
        "description": (
            "Replaces the food_ledger_qr_caution ledger with a whole pass of "
            "search-food-qr-caution: 무료QR 주의사항, 8,134행."
        ),
        "cron": "50 23 * * 5",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-qr-allergy"),
        "code": "sync_food_ledger_qr_allergy",
        "name": "Sync food_ledger_qr_allergy",
        "description": (
            "Replaces the food_ledger_qr_allergy ledger with a whole pass of "
            "search-food-qr-allergy: 무료QR 알레르기, 8,580행."
        ),
        "cron": "0 1 * * 6",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-haccp-label"),
        "code": "sync_food_ledger_haccp_label",
        "name": "Sync food_ledger_haccp_label",
        "description": (
            "Replaces the food_ledger_haccp_label ledger with a whole pass of "
            "search-haccp-label: HACCP 표기정보, 14,664행."
        ),
        "cron": "15 1 * * 6",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-qr-nutrition"),
        "code": "sync_food_ledger_qr_nutrition",
        "name": "Sync food_ledger_qr_nutrition",
        "description": (
            "Replaces the food_ledger_qr_nutrition ledger with a whole pass of "
            "search-food-qr-nutrition: 무료QR 영양표시, 25,663행."
        ),
        "cron": "30 1 * * 6",
    },
    {
        "id": uuid5(NAMESPACE_URL, "fast-api-standard/batch/sync-food-ledger-nutrition"),
        "code": "sync_food_ledger_nutrition",
        "name": "Sync food_ledger_nutrition",
        "description": (
            "Replaces the food_ledger_nutrition ledger with a whole pass of "
            "search-food-nutrition: 식품영양성분DB (I2790), 319,060행 639창."
        ),
        "cron": "30 21 * * 5",
    },
]

# Every day, and the days the ledgers are still moving end SKIPPED.
DERIVE_CRON = "0 10 * * *"

WEEKLY_DERIVE_CRON = "0 10 * * 0"


def _schedules() -> sa.TableClause:
    return table(
        "batch_schedule",
        column("id", sa.Uuid()),
        column("code", sa.String()),
        column("name", sa.String()),
        column("description", sa.String()),
        column("cron", sa.String()),
        column("enabled", sa.Boolean()),
        column("created_by", sa.String()),
        column("updated_by", sa.String()),
    )


def _seed(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {**row, "enabled": True, "created_by": "migration", "updated_by": "migration"}
        for row in rows
    ]


def upgrade() -> None:
    """Upgrade schema."""
    schedules = _schedules()
    bind = op.get_bind()
    bind.execute(
        schedules.delete().where(schedules.c.code.in_([job["code"] for job in RETIRED_JOBS]))
    )
    op.bulk_insert(schedules, _seed(LEDGER_JOBS))
    bind.execute(
        schedules.update().where(schedules.c.id == DERIVE_JOB_ID).values(cron=DERIVE_CRON)
    )


def downgrade() -> None:
    """Downgrade schema."""
    schedules = _schedules()
    bind = op.get_bind()
    bind.execute(
        schedules.delete().where(schedules.c.code.in_([job["code"] for job in LEDGER_JOBS]))
    )
    op.bulk_insert(schedules, _seed(RETIRED_JOBS))
    bind.execute(
        schedules.update().where(schedules.c.id == DERIVE_JOB_ID).values(cron=WEEKLY_DERIVE_CRON)
    )
