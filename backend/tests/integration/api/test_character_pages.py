"""캐릭터 페이지 API 통합 테스트."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.models.user import User
from tests.conftest import auth_header


async def _create_persona(db_session: AsyncSession, owner: User, **kwargs) -> Persona:
    """테스트용 페르소나 생성."""
    defaults = {
        "persona_key": f"test-{uuid.uuid4().hex[:8]}",
        "version": "1.0",
        "display_name": "테스트 캐릭터",
        "system_prompt": "테스트 프롬프트",
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


@pytest.mark.asyncio
async def test_get_character_page_returns_profile(
    client: AsyncClient, db_session: AsyncSession, test_user: User,
):
    persona = await _create_persona(db_session, test_user)
    headers = auth_header(test_user)

    resp = await client.get(f"/api/character-pages/{persona.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(persona.id)
    assert data["display_name"] == "테스트 캐릭터"
    assert data["stats"]["follower_count"] == 0
    assert data["is_following"] is False


@pytest.mark.asyncio
async def test_follow_and_unfollow_updates_count(
    client: AsyncClient, db_session: AsyncSession, test_user: User,
):
    persona = await _create_persona(db_session, test_user)
    headers = auth_header(test_user)

    # Follow
    resp = await client.post(f"/api/character-pages/{persona.id}/follow", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["following"] is True
    assert data["follower_count"] == 1

    # 중복 팔로우 시 카운트 불변
    resp = await client.post(f"/api/character-pages/{persona.id}/follow", headers=headers)
    assert resp.json()["follower_count"] == 1

    # Unfollow
    resp = await client.delete(f"/api/character-pages/{persona.id}/follow", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["following"] is False
    assert data["follower_count"] == 0


@pytest.mark.asyncio
async def test_18plus_character_page_requires_adult_verified(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    """18+ 캐릭터 페이지: adult_verified 아닌 사용자 접근 → 403."""
    persona = await _create_persona(db_session, test_adult_user, age_rating="18+")

    # 미인증 사용자 → 403
    headers = auth_header(test_user)
    resp = await client.get(f"/api/character-pages/{persona.id}", headers=headers)
    assert resp.status_code == 403

    # 성인인증 사용자 → 200
    adult_headers = auth_header(test_adult_user)
    resp = await client.get(f"/api/character-pages/{persona.id}", headers=adult_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_followers_list(
    client: AsyncClient, db_session: AsyncSession, test_user: User, test_adult_user: User,
):
    persona = await _create_persona(db_session, test_user)

    # 두 명이 팔로우
    headers1 = auth_header(test_user)
    headers2 = auth_header(test_adult_user)
    await client.post(f"/api/character-pages/{persona.id}/follow", headers=headers1)
    await client.post(f"/api/character-pages/{persona.id}/follow", headers=headers2)

    resp = await client.get(f"/api/character-pages/{persona.id}/followers", headers=headers1)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_nonexistent_persona_returns_404(
    client: AsyncClient, test_user: User,
):
    headers = auth_header(test_user)
    resp = await client.get(f"/api/character-pages/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404
