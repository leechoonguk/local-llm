"""add batch run table

Revision ID: 86
Revises: 85

배치 실행 1건. 시작·종료 시각과 네 가지 결말(정상/실패/사용자 중지/프로세스 유실)을 구분해
남긴다. 스케줄 행이 지워져도 이력은 남아야 하므로 batch_id 는 SET NULL 이고 code 를 함께 든다.


"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "86"
down_revision: str | Sequence[str] | None = "85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "batch_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("trigger", sa.String(length=8), nullable=False),
        sa.Column("triggered_by", sa.String(length=50), nullable=False),
        sa.Column("stopped_by", sa.String(length=50), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("result", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.String(length=512), nullable=True),
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
        sa.CheckConstraint(
            "(status = 'RUNNING') = (finished_at IS NULL)", name="ck_batch_run_finished_at"
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'STOPPED', 'INTERRUPTED')",
            name="ck_batch_run_status",
        ),
        sa.CheckConstraint("trigger IN ('CRON', 'MANUAL')", name="ck_batch_run_trigger"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_batch_run_duration"),
        sa.ForeignKeyConstraint(["batch_id"], ["batch_schedule.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_batch_run_code_started_at", "batch_run", ["code", "started_at"], unique=False
    )
    op.create_index(op.f("ix_batch_run_batch_id"), "batch_run", ["batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_batch_run_code_started_at", table_name="batch_run")
    op.drop_index("ix_batch_run_batch_id", table_name="batch_run")
    op.drop_table("batch_run")
