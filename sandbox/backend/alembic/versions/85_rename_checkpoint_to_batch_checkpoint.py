"""rename checkpoint table to batch checkpoint

Revision ID: 85
Revises: 84

체크포인트도 배치 도메인 이름공간으로 들어온다 — 스케줄·실행·단위와 한 도메인이라야
한 서비스가 같은 트랜잭션에서 단위 로그와 재개점을 함께 쓸 수 있다.

autogenerate 는 rename 을 drop+create 로 본다. 그대로 두면 재개 지점을 버리고, 진행 중이던
초기 적재가 1번 행부터 다시 시작된다.


"""

from collections.abc import Sequence
from alembic import op

revision: str = "85"
down_revision: str | Sequence[str] | None = "84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("checkpoint", "batch_checkpoint")
    # Postgres renames the table, never what hangs off it.
    op.drop_index("ix_checkpoint_source_code", table_name="batch_checkpoint")
    op.create_index(
        "ix_batch_checkpoint_source_code", "batch_checkpoint", ["source_code"], unique=True
    )
    op.drop_constraint("ck_checkpoint_next_range_start", "batch_checkpoint", type_="check")
    op.create_check_constraint(
        "ck_batch_checkpoint_next_range_start", "batch_checkpoint", "next_range_start >= 1"
    )


def downgrade() -> None:
    op.drop_constraint("ck_batch_checkpoint_next_range_start", "batch_checkpoint", type_="check")
    op.create_check_constraint(
        "ck_checkpoint_next_range_start", "batch_checkpoint", "next_range_start >= 1"
    )
    op.drop_index("ix_batch_checkpoint_source_code", table_name="batch_checkpoint")
    op.create_index("ix_checkpoint_source_code", "batch_checkpoint", ["source_code"], unique=True)
    op.rename_table("batch_checkpoint", "checkpoint")
