"""add_persona_category

Revision ID: b2c3d4e5f6a7
Revises: b1c2d3e4f5a6
Create Date: 2026-02-17 21:00:00.000000

페르소나에 category 컬럼 추가 (회원가입 테마와 매칭).

Note: a1b2c3d4e5f6 (add_deleted_session_status) 는 DB에 적용된 적 없으므로
parent를 b1c2d3e4f5a6 으로 직접 연결 (2026-03-23 수정).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("personas", sa.Column("category", sa.String(30), nullable=True))
    op.create_index("idx_personas_category", "personas", ["category"])


def downgrade() -> None:
    op.drop_index("idx_personas_category", table_name="personas")
    op.drop_column("personas", "category")
