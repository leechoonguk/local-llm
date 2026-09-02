"""add batch step table

Revision ID: 87
Revises: 86

실행 안의 단위 1건 — 페이징 잡이면 창 하나. 실패한 창이 어디였고 그 창이 무엇을 가져왔는지는
실행 단위 상태로는 답할 수 없다. integration_call 로 이어지는 FK 가 "그 창이 실제로 무엇을
보내고 무엇을 받았는지"까지 한 조인으로 잇는다.


"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "87"
down_revision: str | Sequence[str] | None = "86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "batch_step",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("range_start", sa.Integer(), nullable=True),
        sa.Column("range_end", sa.Integer(), nullable=True),
        sa.Column("received", sa.Integer(), nullable=True),
        sa.Column("written", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("integration_call_id", sa.Uuid(), nullable=True),
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
        sa.CheckConstraint("status IN ('SUCCEEDED', 'FAILED')", name="ck_batch_step_status"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_batch_step_duration"),
        sa.CheckConstraint(
            "range_start IS NULL OR range_start >= 1", name="ck_batch_step_range_start"
        ),
        sa.CheckConstraint("sequence >= 1", name="ck_batch_step_sequence"),
        sa.ForeignKeyConstraint(
            ["integration_call_id"], ["integration_call.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["batch_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_batch_step_run_id_sequence"),
    )
    op.create_index(
        op.f("ix_batch_step_integration_call_id"),
        "batch_step",
        ["integration_call_id"],
        unique=False,
    )
    op.create_index(op.f("ix_batch_step_run_id"), "batch_step", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_batch_step_run_id"), table_name="batch_step")
    op.drop_index(op.f("ix_batch_step_integration_call_id"), table_name="batch_step")
    op.drop_table("batch_step")
