"""구독 API 통합 테스트."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


async def _seed_plans(db_session):
    """테스트용 구독 플랜 시드 데이터 삽입."""
    from app.models.subscription_plan import SubscriptionPlan

    free = SubscriptionPlan(
        plan_key="free",
        display_name="무료",
        price_krw=0,
        daily_credits=50,
    )
    premium = SubscriptionPlan(
        plan_key="premium",
        display_name="프리미엄",
        price_krw=6900,
        daily_credits=300,
    )
    db_session.add_all([free, premium])
    await db_session.commit()
    return free, premium


# ── 플랜 목록 ──


@pytest.mark.asyncio
async def test_get_plans(client: AsyncClient, db_session):
    await _seed_plans(db_session)
    resp = await client.get("/api/subscriptions/plans")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["plan_key"] == "free"
    assert data[1]["plan_key"] == "premium"


@pytest.mark.asyncio
async def test_get_plans_empty(client: AsyncClient):
    resp = await client.get("/api/subscriptions/plans")
    assert resp.status_code == 200
    assert resp.json() == []


# ── 내 구독 조회 ──


@pytest.mark.asyncio
async def test_get_my_subscription_none(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    resp = await client.get("/api/subscriptions/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "none"
    assert data["plan_key"] == "free"


@pytest.mark.asyncio
async def test_get_my_subscription_after_subscribe(client: AsyncClient, test_user, db_session):
    await _seed_plans(db_session)
    headers = auth_header(test_user)

    await client.post("/api/subscriptions/subscribe", json={"plan_key": "premium"}, headers=headers)

    resp = await client.get("/api/subscriptions/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["plan"]["plan_key"] == "premium"


# ── 구독 시작 ──


@pytest.mark.asyncio
async def test_subscribe_premium(client: AsyncClient, test_user, db_session):
    await _seed_plans(db_session)
    headers = auth_header(test_user)
    resp = await client.post("/api/subscriptions/subscribe", json={"plan_key": "premium"}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "active"
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_subscribe_free(client: AsyncClient, test_user, db_session):
    await _seed_plans(db_session)
    headers = auth_header(test_user)
    resp = await client.post("/api/subscriptions/subscribe", json={"plan_key": "free"}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["expires_at"] is None


@pytest.mark.asyncio
async def test_subscribe_invalid_plan(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    resp = await client.post("/api/subscriptions/subscribe", json={"plan_key": "gold"}, headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_subscribe_replaces_existing(client: AsyncClient, test_user, db_session):
    """새 구독 시작 시 기존 활성 구독이 만료 처리된다."""
    await _seed_plans(db_session)
    headers = auth_header(test_user)

    resp1 = await client.post("/api/subscriptions/subscribe", json={"plan_key": "free"}, headers=headers)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/subscriptions/subscribe", json={"plan_key": "premium"}, headers=headers)
    assert resp2.status_code == 201

    # 내 구독 조회 → premium만 활성
    me = await client.get("/api/subscriptions/me", headers=headers)
    assert me.json()["plan"]["plan_key"] == "premium"


@pytest.mark.asyncio
async def test_subscribe_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/subscriptions/subscribe", json={"plan_key": "free"})
    assert resp.status_code in (401, 403)


# ── 구독 해지 ──


@pytest.mark.asyncio
async def test_cancel_premium(client: AsyncClient, test_user, db_session):
    await _seed_plans(db_session)
    headers = auth_header(test_user)

    await client.post("/api/subscriptions/subscribe", json={"plan_key": "premium"}, headers=headers)

    resp = await client.post("/api/subscriptions/cancel", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cancelled"
    assert data["cancelled_at"] is not None


@pytest.mark.asyncio
async def test_cancel_free_plan_fails(client: AsyncClient, test_user, db_session):
    await _seed_plans(db_session)
    headers = auth_header(test_user)

    await client.post("/api/subscriptions/subscribe", json={"plan_key": "free"}, headers=headers)

    resp = await client.post("/api/subscriptions/cancel", headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cancel_no_subscription(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    resp = await client.post("/api/subscriptions/cancel", headers=headers)
    assert resp.status_code == 404


# ── 관리자 구독 통계 ──


@pytest.mark.asyncio
async def test_admin_subscription_summary(client: AsyncClient, test_admin, db_session):
    admin_headers = auth_header(test_admin)
    resp = await client.get("/api/admin/subscriptions/summary", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_subscribers" in data
    assert "active_subscribers" in data
    assert "monthly_revenue_krw" in data


@pytest.mark.asyncio
async def test_admin_summary_requires_admin(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    resp = await client.get("/api/admin/subscriptions/summary", headers=headers)
    assert resp.status_code == 403
