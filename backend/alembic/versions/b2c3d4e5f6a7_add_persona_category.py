"""add_persona_category

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-17 21:00:00.000000

페르소나에 category 컬럼 추가 (회원가입 테마와 매칭).
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("personas", sa.Column("category", sa.String(30), nullable=True))
    op.create_index("idx_personas_category", "personas", ["category"])


def downgrade() -> None:
    op.drop_index("idx_personas_category", table_name="personas")
    op.drop_column("personas", "category")
