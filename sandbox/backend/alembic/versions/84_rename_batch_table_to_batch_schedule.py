"""rename batch table to batch schedule

Revision ID: 84
Revises: 83

배치 도메인이 네 테이블(스케줄·체크포인트·실행·단위)로 커지면서 이름공간을 접두사로 모은다.
autogenerate 는 rename 을 drop+create 로 보므로 손으로 `rename_table` 을 쓴다 — 데이터를 버리면
이미 시드된 잡 행(리비전 80·82)이 사라진다.


"""

from collections.abc import Sequence

from alembic import op

revision: str = "84"
down_revision: str | Sequence[str] | None = "83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("batch", "batch_schedule")
    # Postgres renames the table, never the indexes on it: without this the ORM
    # expects ix_batch_schedule_* while the database still answers ix_batch_*.
    op.drop_index("ix_batch_code", table_name="batch_schedule")
    op.drop_index("ix_batch_name", table_name="batch_schedule")
    op.create_index("ix_batch_schedule_code", "batch_schedule", ["code"])
    op.create_index("ix_batch_schedule_name", "batch_schedule", ["name"])


def downgrade() -> None:
    op.drop_index("ix_batch_schedule_name", table_name="batch_schedule")
    op.drop_index("ix_batch_schedule_code", table_name="batch_schedule")
    op.create_index("ix_batch_name", "batch_schedule", ["name"])
    op.create_index("ix_batch_code", "batch_schedule", ["code"])
    op.rename_table("batch_schedule", "batch")
