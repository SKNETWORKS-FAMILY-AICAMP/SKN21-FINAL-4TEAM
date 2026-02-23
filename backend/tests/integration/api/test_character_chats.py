"""캐릭터 간 1:1 대화 API 통합 테스트."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.models.persona_lounge_config import PersonaLoungeConfig
from app.models.user import User
from tests.conftest import auth_header


async def _create_persona(db_session: AsyncSession, owner: User, **kwargs) -> Persona:
    defaults = {
        "persona_key": f"test-{uuid.uuid4().hex[:8]}",
        "version": "1.0",
        "display_name": f"캐릭터-{uuid.uuid4().hex[:4]}",
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


async def _create_lounge_config(db_session: AsyncSession, persona_id, **kwargs) -> PersonaLoungeConfig:
    defaults = {
        "persona_id": persona_id,
        "is_active": True,
        "accept_chat_requests": True,
    }
    defaults.update(kwargs)
    config = PersonaLoungeConfig(**defaults)
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return config


@pytest.mark.asyncio
async def test_request_chat_creates_pending_session(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    p1 = await _create_persona(db_session, test_user)
    p2 = await _create_persona(db_session, test_adult_user)
    await _create_lounge_config(db_session, p2.id)

    headers = auth_header(test_user)
    resp = await client.post("/api/character-chats/request", json={
        "requester_persona_id": str(p1.id),
        "responder_persona_id": str(p2.id),
        "max_turns": 5,
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert data["max_turns"] == 5


@pytest.mark.asyncio
async def test_auto_accept_chat_sets_active_status(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    p1 = await _create_persona(db_session, test_user)
    p2 = await _create_persona(db_session, test_adult_user)
    await _create_lounge_config(db_session, p2.id, auto_accept_chats=True)

    headers = auth_header(test_user)
    resp = await client.post("/api/character-chats/request", json={
        "requester_persona_id": str(p1.id),
        "responder_persona_id": str(p2.id),
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_cannot_chat_with_self(
    client: AsyncClient, db_session: AsyncSession, test_user: User,
):
    persona = await _create_persona(db_session, test_user)
    headers = auth_header(test_user)

    resp = await client.post("/api/character-chats/request", json={
        "requester_persona_id": str(persona.id),
        "responder_persona_id": str(persona.id),
    }, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_not_own_persona_returns_403(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    """타인의 캐릭터로 요청 → 403."""
    p1 = await _create_persona(db_session, test_adult_user)
    p2 = await _create_persona(db_session, test_user)

    headers = auth_header(test_user)
    resp = await client.post("/api/character-chats/request", json={
        "requester_persona_id": str(p1.id),
        "responder_persona_id": str(p2.id),
    }, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_respond_accept_sets_active(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    p1 = await _create_persona(db_session, test_user)
    p2 = await _create_persona(db_session, test_adult_user)
    await _create_lounge_config(db_session, p2.id)

    # 요청
    h1 = auth_header(test_user)
    resp = await client.post("/api/character-chats/request", json={
        "requester_persona_id": str(p1.id),
        "responder_persona_id": str(p2.id),
    }, headers=h1)
    session_id = resp.json()["id"]

    # 수락
    h2 = auth_header(test_adult_user)
    resp = await client.post(f"/api/character-chats/{session_id}/respond", json={
        "accept": True,
    }, headers=h2)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_respond_reject_sets_rejected(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    p1 = await _create_persona(db_session, test_user)
    p2 = await _create_persona(db_session, test_adult_user)
    await _create_lounge_config(db_session, p2.id)

    h1 = auth_header(test_user)
    resp = await client.post("/api/character-chats/request", json={
        "requester_persona_id": str(p1.id),
        "responder_persona_id": str(p2.id),
    }, headers=h1)
    session_id = resp.json()["id"]

    h2 = auth_header(test_adult_user)
    resp = await client.post(f"/api/character-chats/{session_id}/respond", json={
        "accept": False,
    }, headers=h2)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_18plus_chat_requires_adult_verified(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    """18+ 캐릭터 간 채팅: 미인증 소유자 → 403."""
    # test_user는 미인증, 18+ 캐릭터를 소유
    p1 = await _create_persona(db_session, test_user, age_rating="18+")
    p2 = await _create_persona(db_session, test_adult_user, age_rating="18+")
    await _create_lounge_config(db_session, p2.id)

    headers = auth_header(test_user)
    resp = await client.post("/api/character-chats/request", json={
        "requester_persona_id": str(p1.id),
        "responder_persona_id": str(p2.id),
    }, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_incoming_and_outgoing(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    p1 = await _create_persona(db_session, test_user)
    p2 = await _create_persona(db_session, test_adult_user)
    await _create_lounge_config(db_session, p2.id)

    h1 = auth_header(test_user)
    await client.post("/api/character-chats/request", json={
        "requester_persona_id": str(p1.id),
        "responder_persona_id": str(p2.id),
    }, headers=h1)

    # 발신 목록
    resp = await client.get("/api/character-chats/requests/outgoing", headers=h1)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # 수신 목록
    h2 = auth_header(test_adult_user)
    resp = await client.get("/api/character-chats/requests/incoming", headers=h2)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
