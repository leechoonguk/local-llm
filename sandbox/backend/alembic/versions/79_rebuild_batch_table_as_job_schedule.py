"""rebuild batch table as job schedule

Revision ID: 79
Revises: 78

`batch` stops being a nondescript CRUD row and becomes the schedule itself: one
row per scheduled job, carrying the job `code`, its `cron`, and the `enabled`
switch that stops it. The table is dropped and recreated rather than altered
because the old rows carried no code and no cron — there is no value to migrate
them to, and a backfilled placeholder would be a row that schedules nothing
while looking scheduled.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "79"
down_revision: str | Sequence[str] | None = "78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_COLUMNS = (
    sa.Column("created_by", sa.String(length=50), nullable=True),
    sa.Column("updated_by", sa.String(length=50), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("version", sa.Integer(), server_default="1", nullable=False),
)


def upgrade() -> None:
    op.drop_table("batch")
    op.create_table(
        "batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("cron", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *AUDIT_COLUMNS,
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_batch_code"), "batch", ["code"], unique=False)
    op.create_index(op.f("ix_batch_name"), "batch", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_batch_name"), table_name="batch")
    op.drop_index(op.f("ix_batch_code"), table_name="batch")
    op.drop_table("batch")
    op.create_table(
        "batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        *AUDIT_COLUMNS,
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_batch_name"), "batch", ["name"], unique=False)
