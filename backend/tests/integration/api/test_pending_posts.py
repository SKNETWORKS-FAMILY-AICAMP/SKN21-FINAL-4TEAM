"""수동 모드 승인 큐 API 통합 테스트."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.pending_post import PendingPost
from app.models.persona import Persona
from app.models.persona_lounge_config import PersonaLoungeConfig
from app.models.user import User
from tests.conftest import auth_header


async def _create_persona(db_session: AsyncSession, owner: User, **kwargs) -> Persona:
    defaults = {
        "persona_key": f"test-{uuid.uuid4().hex[:8]}",
        "version": "1.0",
        "display_name": "테스트 캐릭터",
        "system_prompt": "테스트",
        "style_rules": {},
        "safety_rules": {},
        "created_by": owner.id,
        "type": "user_created",
        "visibility": "public",
        "moderation_status": "approved",
        "age_rating": "all",
        "is_active": True,
    }
    defaults.update(kwargs)
    persona = Persona(**defaults)
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    return persona


async def _seed_board(db_session: AsyncSession) -> Board:
    board = Board(
        board_key=f"test-{uuid.uuid4().hex[:8]}",
        display_name="테스트",
        age_rating="all",
        is_active=True,
        sort_order=1,
    )
    db_session.add(board)
    await db_session.commit()
    await db_session.refresh(board)
    return board


async def _create_pending(db_session: AsyncSession, persona: Persona, owner: User) -> PendingPost:
    pending = PendingPost(
        persona_id=persona.id,
        owner_user_id=owner.id,
        content_type="post",
        content="AI가 생성한 테스트 글",
        input_tokens=100,
        output_tokens=50,
    )
    db_session.add(pending)
    await db_session.commit()
    await db_session.refresh(pending)
    return pending


@pytest.mark.asyncio
async def test_list_pending_posts_for_owner(
    client: AsyncClient, db_session: AsyncSession, test_user: User,
):
    persona = await _create_persona(db_session, test_user)
    await _create_pending(db_session, persona, test_user)

    headers = auth_header(test_user)
    resp = await client.get("/api/pending-posts/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_approve_pending_post_creates_board_post(
    client: AsyncClient, db_session: AsyncSession, test_user: User,
):
    persona = await _create_persona(db_session, test_user)
    board = await _seed_board(db_session)

    # 라운지 설정 (게시판 연결)
    config = PersonaLoungeConfig(persona_id=persona.id, allowed_boards=[board.id])
    db_session.add(config)
    await db_session.commit()

    pending = await _create_pending(db_session, persona, test_user)

    headers = auth_header(test_user)
    resp = await client.post(f"/api/pending-posts/{pending.id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_pending_post(
    client: AsyncClient, db_session: AsyncSession, test_user: User,
):
    persona = await _create_persona(db_session, test_user)
    pending = await _create_pending(db_session, persona, test_user)

    headers = auth_header(test_user)
    resp = await client.post(f"/api/pending-posts/{pending.id}/reject", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_other_user_cannot_approve_pending(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    """타인 캐릭터의 pending 게시물 승인 시도 → 403."""
    persona = await _create_persona(db_session, test_user)
    pending = await _create_pending(db_session, persona, test_user)

    headers = auth_header(test_adult_user)
    resp = await client.post(f"/api/pending-posts/{pending.id}/approve", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_double_approve_returns_400(
    client: AsyncClient, db_session: AsyncSession, test_user: User,
):
    persona = await _create_persona(db_session, test_user)
    board = await _seed_board(db_session)
    config = PersonaLoungeConfig(persona_id=persona.id, allowed_boards=[board.id])
    db_session.add(config)
    await db_session.commit()

    pending = await _create_pending(db_session, persona, test_user)

    headers = auth_header(test_user)
    await client.post(f"/api/pending-posts/{pending.id}/approve", headers=headers)

    resp = await client.post(f"/api/pending-posts/{pending.id}/approve", headers=headers)
    assert resp.status_code == 400
