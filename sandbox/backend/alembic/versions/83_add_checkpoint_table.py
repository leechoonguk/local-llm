"""add checkpoint table

Revision ID: 83
Revises: 82

원장 마이그레이션의 체크포인트 — 외부 피드를 어디까지 읽었는지, 그 한 가지. 외부 페이지 순서가
호출 간 안정하다는 실측(같은 창 = 같은 행, 15분 뒤에도 동일, 경계에 겹침·누락 없음) 위에서만
성립한다. 그 덕에 5만 건 적재가 중단돼도 다음 창부터 이어서 한다.

원장 행 수로 대신할 수 없다: 피드가 같은 레코드를 다시 보내므로(실측 1000건 → 976행) 행 수는
읽은 행 수보다 작고, 그 차이만큼 레코드를 건너뛰게 된다.

날짜 경계(CHNG_DT)는 일부러 두지 않는다: I2570 은 전 구간 표본 4000행이 모두 2015-01-22 이라
아무것도 좁히지 못하고, 좁히는 경계는 옛 날짜를 달고 뒤늦게 삽입된 행을 영영 가린다. 전량 패스는
그 사각이 없고 54회 호출로 끝난다.


"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "83"
down_revision: str | Sequence[str] | None = "82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "checkpoint",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=64), nullable=False),
        sa.Column("next_range_start", sa.Integer(), server_default="1", nullable=False),
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
        sa.CheckConstraint("next_range_start >= 1", name="ck_checkpoint_next_range_start"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_checkpoint_source_code"), "checkpoint", ["source_code"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_checkpoint_source_code"), table_name="checkpoint")
    op.drop_table("checkpoint")
