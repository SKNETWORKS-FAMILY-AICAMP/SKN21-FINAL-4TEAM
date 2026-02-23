"""세계관 이벤트 API 통합 테스트."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_create_world_event(
    client: AsyncClient, db_session: AsyncSession, test_admin: User,
):
    headers = auth_header(test_admin)
    resp = await client.post("/api/admin/world-events/", json={
        "title": "유성 접근",
        "content": "유성이 도시에 접근 중입니다.",
        "event_type": "crisis",
        "priority": 10,
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "유성 접근"
    assert data["event_type"] == "crisis"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_world_events(
    client: AsyncClient, db_session: AsyncSession, test_admin: User,
):
    headers = auth_header(test_admin)

    # 이벤트 2개 생성
    await client.post("/api/admin/world-events/", json={
        "title": "이벤트1",
        "content": "내용1",
    }, headers=headers)
    await client.post("/api/admin/world-events/", json={
        "title": "이벤트2",
        "content": "내용2",
        "priority": 5,
    }, headers=headers)

    resp = await client.get("/api/admin/world-events/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # priority 높은 것이 먼저
    assert data["items"][0]["title"] == "이벤트2"


@pytest.mark.asyncio
async def test_update_world_event(
    client: AsyncClient, db_session: AsyncSession, test_admin: User,
):
    headers = auth_header(test_admin)
    create_resp = await client.post("/api/admin/world-events/", json={
        "title": "원본",
        "content": "원본 내용",
    }, headers=headers)
    event_id = create_resp.json()["id"]

    resp = await client.put(f"/api/admin/world-events/{event_id}", json={
        "title": "수정됨",
        "is_active": False,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "수정됨"
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_world_event(
    client: AsyncClient, db_session: AsyncSession, test_admin: User,
):
    headers = auth_header(test_admin)
    create_resp = await client.post("/api/admin/world-events/", json={
        "title": "삭제 대상",
        "content": "내용",
    }, headers=headers)
    event_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/admin/world-events/{event_id}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_normal_user_cannot_create_world_event(
    client: AsyncClient, db_session: AsyncSession, test_user: User,
):
    """일반 사용자 → 관리자 API 접근 403."""
    headers = auth_header(test_user)
    resp = await client.post("/api/admin/world-events/", json={
        "title": "해킹 시도",
        "content": "일반 유저가 만들기 시도",
    }, headers=headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_active_world_events(
    client: AsyncClient, db_session: AsyncSession, test_admin: User, test_user: User,
):
    admin_headers = auth_header(test_admin)

    # 활성 이벤트 생성
    await client.post("/api/admin/world-events/", json={
        "title": "활성 이벤트",
        "content": "현재 진행 중",
    }, headers=admin_headers)

    # 비활성 이벤트
    create_resp = await client.post("/api/admin/world-events/", json={
        "title": "비활성 이벤트",
        "content": "종료됨",
    }, headers=admin_headers)
    event_id = create_resp.json()["id"]
    await client.put(f"/api/admin/world-events/{event_id}", json={
        "is_active": False,
    }, headers=admin_headers)

    # 일반 사용자가 활성 이벤트 조회
    user_headers = auth_header(test_user)
    resp = await client.get("/api/world-events/active", headers=user_headers)
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["title"] == "활성 이벤트"
