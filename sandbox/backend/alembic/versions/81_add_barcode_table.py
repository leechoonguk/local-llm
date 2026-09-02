"""add barcode table

Revision ID: 81
Revises: 80

바코드 품목정보 원장(I2570) — 외부 인터페이스를 우리 업무 테이블로 옮기는 첫 원장이다.
`(barcode_no, report_no)` 유니크 제약이 배치의 upsert 대상이고, `source_updated_at`
인덱스가 그 배치의 커서(=최댓값) 조회를 지탱한다. 나머지 네 인터페이스는 같은 모양의
형제 원장으로 들어온다.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "81"
down_revision: str | Sequence[str] | None = "80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "barcode",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("barcode_no", sa.String(length=32), nullable=False),
        sa.Column("report_no", sa.String(length=50), nullable=False),
        sa.Column("report_item_name", sa.String(length=200), nullable=True),
        sa.Column("product_name", sa.String(length=200), nullable=True),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("upper_product_classification_name", sa.String(length=120), nullable=True),
        sa.Column("top_product_classification_name", sa.String(length=120), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=50), nullable=True),
        sa.Column("updated_by", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("barcode_no", "report_no", name="uq_barcode_barcode_no_report_no"),
    )
    op.create_index("ix_barcode_report_no", "barcode", ["report_no"], unique=False)
    op.create_index("ix_barcode_source_updated_at", "barcode", ["source_updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_barcode_source_updated_at", table_name="barcode")
    op.drop_index("ix_barcode_report_no", table_name="barcode")
    op.drop_table("barcode")
