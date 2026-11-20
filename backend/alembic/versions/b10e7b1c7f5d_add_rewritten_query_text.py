"""add rewritten query text

Revision ID: b10e7b1c7f5d
Revises: 05a21b2cf93e
Create Date: 2026-09-30 13:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "b10e7b1c7f5d"
down_revision: Union[str, Sequence[str], None] = "05a21b2cf93e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("search_queries", sa.Column("rewritten_query_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("search_queries", "rewritten_query_text")
