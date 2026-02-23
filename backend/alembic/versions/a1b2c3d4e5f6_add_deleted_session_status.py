"""add_deleted_session_status

Revision ID: a1b2c3d4e5f6
Revises: f5a6b7c8d9e0
Create Date: 2026-02-15 22:00:00.000000

세션 상태에 'deleted' 추가 (소프트 삭제 지원).
"""

from typing import Sequence, Union
from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_session_status", "chat_sessions", type_="check")
    op.create_check_constraint(
        "ck_session_status",
        "chat_sessions",
        "status IN ('active', 'archived', 'deleted')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_session_status", "chat_sessions", type_="check")
    op.create_check_constraint(
        "ck_session_status",
        "chat_sessions",
        "status IN ('active', 'archived')",
    )
