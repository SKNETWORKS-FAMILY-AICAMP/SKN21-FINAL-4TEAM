import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header

PERSONA_DATA = {
    "persona_key": "test-char",
    "version": "v1.0",
    "display_name": "Test Character",
    "system_prompt": "You are a friendly reviewer.",
    "style_rules": {"tone": "casual"},
    "safety_rules": {},
    "age_rating": "all",
    "visibility": "private",
}


# ── 생성 ──


@pytest.mark.asyncio
async def test_create_persona_success(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["persona_key"] == "test-char"
    assert data["created_by"] == str(test_user.id)
    assert data["type"] == "user_created"
    assert data["moderation_status"] == "pending"


@pytest.mark.asyncio
async def test_create_persona_18_requires_adult(client: AsyncClient, test_user):
    """미인증 사용자가 18+ 페르소나 생성 시도 → 403."""
    headers = auth_header(test_user)
    data = {**PERSONA_DATA, "persona_key": "adult-char", "age_rating": "18+"}
    response = await client.post("/api/personas/", json=data, headers=headers)
    assert response.status_code == 403
    assert "Adult verification" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_persona_18_adult_verified(client: AsyncClient, test_adult_user):
    """성인인증 사용자는 18+ 페르소나 생성 가능."""
    headers = auth_header(test_adult_user)
    data = {**PERSONA_DATA, "persona_key": "adult-char-ok", "age_rating": "18+"}
    response = await client.post("/api/personas/", json=data, headers=headers)
    assert response.status_code == 201
    assert response.json()["age_rating"] == "18+"


@pytest.mark.asyncio
async def test_create_persona_duplicate_key_version(client: AsyncClient, test_user):
    """같은 persona_key + version 중복 → 409."""
    headers = auth_header(test_user)
    await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    response = await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    assert response.status_code == 409


# ── 목록 ──


@pytest.mark.asyncio
async def test_list_personas_own(client: AsyncClient, test_user):
    """자신이 만든 비공개 페르소나가 목록에 포함."""
    headers = auth_header(test_user)
    await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    response = await client.get("/api/personas/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(p["persona_key"] == "test-char" for p in data["items"])


@pytest.mark.asyncio
async def test_list_personas_excludes_other_private(client: AsyncClient, test_user, test_adult_user):
    """다른 사용자의 비공개 페르소나는 보이지 않음."""
    # test_adult_user가 비공개 페르소나 생성
    headers_adult = auth_header(test_adult_user)
    data = {**PERSONA_DATA, "persona_key": "other-private", "visibility": "private"}
    await client.post("/api/personas/", json=data, headers=headers_adult)

    # test_user 목록에서 안 보여야 함
    headers_user = auth_header(test_user)
    response = await client.get("/api/personas/", headers=headers_user)
    items = response.json()["items"]
    assert not any(p["persona_key"] == "other-private" for p in items)


# ── 상세 조회 ──


@pytest.mark.asyncio
async def test_get_own_persona(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    create_resp = await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    persona_id = create_resp.json()["id"]

    response = await client.get(f"/api/personas/{persona_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == persona_id


@pytest.mark.asyncio
async def test_get_other_private_persona_404(client: AsyncClient, test_user, test_adult_user):
    """다른 사용자의 비공개 페르소나 조회 → 404."""
    headers_adult = auth_header(test_adult_user)
    data = {**PERSONA_DATA, "persona_key": "hidden-char"}
    create_resp = await client.post("/api/personas/", json=data, headers=headers_adult)
    persona_id = create_resp.json()["id"]

    headers_user = auth_header(test_user)
    response = await client.get(f"/api/personas/{persona_id}", headers=headers_user)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_18_persona_requires_adult(client: AsyncClient, test_user, test_adult_user, db_session):
    """미인증 사용자가 18+ 페르소나 조회 시도 → 403."""
    # 성인인증 사용자가 18+ 공개 페르소나 생성
    headers_adult = auth_header(test_adult_user)
    data = {**PERSONA_DATA, "persona_key": "adult-view", "age_rating": "18+", "visibility": "public"}
    create_resp = await client.post("/api/personas/", json=data, headers=headers_adult)
    persona_id = create_resp.json()["id"]

    # 모더레이션 승인 (직접 DB 업데이트)
    from app.models.persona import Persona
    result = await db_session.execute(
        Persona.__table__.update().where(Persona.__table__.c.id == uuid.UUID(persona_id)).values(moderation_status="approved")
    )
    await db_session.commit()

    # 미인증 사용자 접근 → 403
    headers_user = auth_header(test_user)
    response = await client.get(f"/api/personas/{persona_id}", headers=headers_user)
    assert response.status_code == 403


# ── 수정 ──


@pytest.mark.asyncio
async def test_update_persona_owner(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    create_resp = await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    persona_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/personas/{persona_id}",
        json={"display_name": "Updated Name"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_persona_not_owner(client: AsyncClient, test_user, test_adult_user):
    """소유자가 아닌 사용자가 수정 시도 → 403."""
    headers_adult = auth_header(test_adult_user)
    data = {**PERSONA_DATA, "persona_key": "not-mine"}
    create_resp = await client.post("/api/personas/", json=data, headers=headers_adult)
    persona_id = create_resp.json()["id"]

    headers_user = auth_header(test_user)
    response = await client.put(
        f"/api/personas/{persona_id}",
        json={"display_name": "Hacked"},
        headers=headers_user,
    )
    assert response.status_code == 403


# ── 삭제 ──


@pytest.mark.asyncio
async def test_delete_persona_owner(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    create_resp = await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    persona_id = create_resp.json()["id"]

    response = await client.delete(f"/api/personas/{persona_id}", headers=headers)
    assert response.status_code == 204

    # 삭제 확인
    response = await client.get(f"/api/personas/{persona_id}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_persona_not_owner(client: AsyncClient, test_user, test_adult_user):
    """소유자가 아닌 사용자가 삭제 시도 → 403."""
    headers_adult = auth_header(test_adult_user)
    data = {**PERSONA_DATA, "persona_key": "del-test"}
    create_resp = await client.post("/api/personas/", json=data, headers=headers_adult)
    persona_id = create_resp.json()["id"]

    headers_user = auth_header(test_user)
    response = await client.delete(f"/api/personas/{persona_id}", headers=headers_user)
    assert response.status_code == 403
