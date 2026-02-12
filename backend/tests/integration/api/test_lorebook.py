import pytest
from httpx import AsyncClient

from tests.conftest import auth_header

PERSONA_DATA = {
    "persona_key": "lore-persona",
    "version": "v1.0",
    "display_name": "Lore Test",
    "system_prompt": "You are a test persona.",
    "style_rules": {"tone": "formal"},
    "safety_rules": {},
}


async def _create_persona(client: AsyncClient, headers: dict) -> str:
    """테스트용 페르소나 생성 후 ID 반환."""
    resp = await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    return resp.json()["id"]


# ── 생성 ──


@pytest.mark.asyncio
async def test_create_lorebook_entry(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    persona_id = await _create_persona(client, headers)

    response = await client.post("/api/lorebook/", json={
        "persona_id": persona_id,
        "title": "Character Background",
        "content": "Born in Seoul, loves webtoons.",
        "tags": ["background", "origin"],
    }, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Character Background"
    assert data["persona_id"] == persona_id
    assert data["created_by"] == str(test_user.id)
    assert data["tags"] == ["background", "origin"]


@pytest.mark.asyncio
async def test_create_lorebook_no_target(client: AsyncClient, test_user):
    """persona_id와 webtoon_id 모두 없으면 → 422."""
    headers = auth_header(test_user)
    response = await client.post("/api/lorebook/", json={
        "title": "Orphan entry",
        "content": "No parent",
    }, headers=headers)
    assert response.status_code == 422


# ── 목록 ──


@pytest.mark.asyncio
async def test_list_persona_lorebook(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    persona_id = await _create_persona(client, headers)

    # 2개 항목 생성
    for i in range(2):
        await client.post("/api/lorebook/", json={
            "persona_id": persona_id,
            "title": f"Entry {i}",
            "content": f"Content {i}",
        }, headers=headers)

    response = await client.get(f"/api/lorebook/persona/{persona_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


# ── 수정 ──


@pytest.mark.asyncio
async def test_update_lorebook_entry(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    persona_id = await _create_persona(client, headers)

    create_resp = await client.post("/api/lorebook/", json={
        "persona_id": persona_id,
        "title": "Original",
        "content": "Original content",
    }, headers=headers)
    entry_id = create_resp.json()["id"]

    response = await client.put(f"/api/lorebook/{entry_id}", json={
        "title": "Updated Title",
    }, headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"
    assert response.json()["content"] == "Original content"  # 변경하지 않은 필드 유지


@pytest.mark.asyncio
async def test_update_lorebook_not_owner(client: AsyncClient, test_user, test_adult_user):
    """소유자가 아닌 사용자 수정 → 403."""
    headers_owner = auth_header(test_user)
    persona_id = await _create_persona(client, headers_owner)

    create_resp = await client.post("/api/lorebook/", json={
        "persona_id": persona_id,
        "title": "Owner Only",
        "content": "Private",
    }, headers=headers_owner)
    entry_id = create_resp.json()["id"]

    headers_other = auth_header(test_adult_user)
    response = await client.put(f"/api/lorebook/{entry_id}", json={
        "title": "Hacked",
    }, headers=headers_other)
    assert response.status_code == 403


# ── 삭제 ──


@pytest.mark.asyncio
async def test_delete_lorebook_entry(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    persona_id = await _create_persona(client, headers)

    create_resp = await client.post("/api/lorebook/", json={
        "persona_id": persona_id,
        "title": "To Delete",
        "content": "Gone soon",
    }, headers=headers)
    entry_id = create_resp.json()["id"]

    response = await client.delete(f"/api/lorebook/{entry_id}", headers=headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_lorebook_not_owner(client: AsyncClient, test_user, test_adult_user):
    """소유자가 아닌 사용자 삭제 → 403."""
    headers_owner = auth_header(test_user)
    persona_id = await _create_persona(client, headers_owner)

    create_resp = await client.post("/api/lorebook/", json={
        "persona_id": persona_id,
        "title": "Protected",
        "content": "Do not delete",
    }, headers=headers_owner)
    entry_id = create_resp.json()["id"]

    headers_other = auth_header(test_adult_user)
    response = await client.delete(f"/api/lorebook/{entry_id}", headers=headers_other)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_lorebook_not_found(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.delete("/api/lorebook/999999", headers=headers)
    assert response.status_code == 404
