"""라운지(에이전트) API 통합 테스트."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


PERSONA_DATA = {
    "persona_key": "lounge-char",
    "version": "v1.0",
    "display_name": "Lounge Character",
    "system_prompt": "You are a friendly character for the lounge.",
    "style_rules": {"tone": "casual"},
    "safety_rules": {},
}


async def _create_persona(client, headers):
    resp = await client.post("/api/personas", json=PERSONA_DATA, headers=headers)
    return resp.json()["id"]


# ── 라운지 설정 ──


@pytest.mark.asyncio
async def test_get_config_creates_default(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    persona_id = await _create_persona(client, headers)

    resp = await client.get(f"/api/lounge/personas/{persona_id}/config", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["persona_id"] == persona_id
    assert data["is_active"] is False
    assert data["activity_level"] == "normal"
    assert data["actions_today"] == 0


@pytest.mark.asyncio
async def test_get_config_requires_ownership(client: AsyncClient, test_user, test_adult_user, db_session):
    """타인의 페르소나 설정 접근 → 403."""
    owner_headers = auth_header(test_user)
    persona_id = await _create_persona(client, owner_headers)

    other_headers = auth_header(test_adult_user)
    resp = await client.get(f"/api/lounge/personas/{persona_id}/config", headers=other_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_config(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    persona_id = await _create_persona(client, headers)

    # 먼저 기본 config 생성
    await client.get(f"/api/lounge/personas/{persona_id}/config", headers=headers)

    resp = await client.put(f"/api/lounge/personas/{persona_id}/config", json={
        "activity_level": "active",
        "interest_tags": ["웹툰", "리뷰"],
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["activity_level"] == "active"
    assert "웹툰" in data["interest_tags"]


# ── 활성화/비활성화 ──


@pytest.mark.asyncio
async def test_activate_and_deactivate(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    persona_id = await _create_persona(client, headers)

    # 활성화
    resp = await client.post(f"/api/lounge/personas/{persona_id}/activate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    # 비활성화
    resp = await client.post(f"/api/lounge/personas/{persona_id}/deactivate", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


# ── 활동 로그 ──


@pytest.mark.asyncio
async def test_get_activity_log_empty(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    persona_id = await _create_persona(client, headers)

    resp = await client.get(f"/api/lounge/personas/{persona_id}/activity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


# ── 관리자 ──


@pytest.mark.asyncio
async def test_admin_agent_summary(client: AsyncClient, test_admin):
    admin_headers = auth_header(test_admin)
    resp = await client.get("/api/admin/agents/activity", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_actions_today" in data
    assert "active_personas" in data


@pytest.mark.asyncio
async def test_admin_agent_costs(client: AsyncClient, test_admin):
    admin_headers = auth_header(test_admin)
    resp = await client.get("/api/admin/agents/costs", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_requires_admin_role(client: AsyncClient, test_user):
    """일반 사용자가 관리자 에이전트 API 접근 → 403."""
    headers = auth_header(test_user)
    resp = await client.get("/api/admin/agents/activity", headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_lounge_access(client: AsyncClient):
    resp = await client.get(f"/api/lounge/personas/{uuid.uuid4()}/config")
    assert resp.status_code in (401, 403)
