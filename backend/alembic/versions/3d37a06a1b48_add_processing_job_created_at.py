"""add processing job creation timestamps

Revision ID: 3d37a06a1b48
Revises: b10e7b1c7f5d
Create Date: 2026-10-01 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3d37a06a1b48"
down_revision: Union[str, Sequence[str], None] = "b10e7b1c7f5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "processing_jobs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("processing_jobs", "created_at")
