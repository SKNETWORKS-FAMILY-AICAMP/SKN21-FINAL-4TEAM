"""add_preferred_themes_to_users

Revision ID: 0de13d3298fa
Revises: l3m4n5o6p7q8
Create Date: 2026-03-17 01:09:24.524666
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0de13d3298fa"
down_revision: str | None = "l3m4n5o6p7q8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_themes", postgresql.ARRAY(sa.String(length=30)), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "preferred_themes")
