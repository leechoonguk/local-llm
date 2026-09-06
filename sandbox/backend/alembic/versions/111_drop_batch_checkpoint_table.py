"""drop the batch checkpoint table

The cursors this table held belonged to the five per-ledger jobs revision 110
retired: a job that reads a whole feed every night has nothing to resume from,
and a table nothing writes is a table that lies the day its rows go stale.
Revisions 83, 85, 89, 90 and 98 stay as the history of what it was.

The downgrade recreates the shape as of revision 98 (rows are not restored -
the positions were only ever valid for the pass that wrote them), so the
retired jobs can start from row 1 as they did on their first night.

Revision ID: 111
Revises: 110
Create Date: 2026-09-06 12:21:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "111"
down_revision: str | Sequence[str] | None = "110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_batch_checkpoint_source_code"), table_name="batch_checkpoint")
    op.drop_table("batch_checkpoint")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "batch_checkpoint",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=64), nullable=False),
        sa.Column("resume_position", sa.Integer(), nullable=True),
        sa.Column("resume_key", sa.String(length=200), nullable=True),
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
        sa.CheckConstraint("resume_position >= 1", name="ck_batch_checkpoint_resume_position"),
        sa.PrimaryKeyConstraint("id", name="checkpoint_pkey"),
    )
    op.create_index(
        op.f("ix_batch_checkpoint_source_code"),
        "batch_checkpoint",
        ["source_code"],
        unique=True,
    )
