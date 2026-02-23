"""크레딧 API 통합 테스트."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


# ── 잔액 조회 ──


@pytest.mark.asyncio
async def test_get_balance_returns_default_free(client: AsyncClient, test_user, db_session):
    """크레딧 잔액 조회 시 일일 충전이 자동 적용되고 free 플랜 기본값을 반환."""
    # free 플랜 시드 데이터 삽입
    from app.models.subscription_plan import SubscriptionPlan

    plan = SubscriptionPlan(
        plan_key="free",
        display_name="무료",
        price_krw=0,
        daily_credits=50,
    )
    db_session.add(plan)
    await db_session.commit()

    headers = auth_header(test_user)
    resp = await client.get("/api/credits/balance", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan_key"] == "free"
    assert data["daily_credits"] == 50
    # 일일 충전이 자동 적용됨
    assert data["balance"] == 50
    assert data["granted_today"] is True


@pytest.mark.asyncio
async def test_get_balance_unauthenticated(client: AsyncClient):
    """인증 없이 잔액 조회 시 401."""
    resp = await client.get("/api/credits/balance")
    assert resp.status_code in (401, 403)


# ── 거래 내역 ──


@pytest.mark.asyncio
async def test_get_history_empty(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    resp = await client.get("/api/credits/history", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_get_history_after_purchase(client: AsyncClient, test_user, db_session):
    """구매 후 거래 내역에 기록이 남는다."""
    from app.models.subscription_plan import SubscriptionPlan

    plan = SubscriptionPlan(plan_key="free", display_name="무료", price_krw=0, daily_credits=50)
    db_session.add(plan)
    await db_session.commit()

    headers = auth_header(test_user)
    await client.post("/api/credits/purchase", json={"package": "small"}, headers=headers)

    resp = await client.get("/api/credits/history", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


# ── 소비 단가표 ──


@pytest.mark.asyncio
async def test_get_costs_empty(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    resp = await client.get("/api/credits/costs", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_costs_with_seed_data(client: AsyncClient, test_user, db_session):
    from app.models.credit_cost import CreditCost

    cost = CreditCost(action="chat", model_tier="standard", cost=3)
    db_session.add(cost)
    await db_session.commit()

    headers = auth_header(test_user)
    resp = await client.get("/api/credits/costs", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["action"] == "chat"
    assert data[0]["cost"] == 3


# ── 대화석 구매 ──


@pytest.mark.asyncio
async def test_purchase_small_package(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    resp = await client.post("/api/credits/purchase", json={"package": "small"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["credits_added"] == 500
    assert data["price_krw"] == 1000
    assert data["new_balance"] == 500


@pytest.mark.asyncio
async def test_purchase_invalid_package(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    resp = await client.post("/api/credits/purchase", json={"package": "mega"}, headers=headers)
    assert resp.status_code == 400


# ── 관리자 크레딧 ──


@pytest.mark.asyncio
async def test_admin_grant_credits(client: AsyncClient, test_superadmin, test_user, db_session):
    admin_headers = auth_header(test_superadmin)
    resp = await client.put(
        "/api/admin/credits/grant",
        json={"user_id": str(test_user.id), "amount": 100, "description": "테스트 지급"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["amount"] == 100


@pytest.mark.asyncio
async def test_admin_grant_requires_admin(client: AsyncClient, test_user):
    """일반 사용자가 관리자 크레딧 지급 시도 → 403."""
    headers = auth_header(test_user)
    resp = await client.put(
        "/api/admin/credits/grant",
        json={"user_id": str(test_user.id), "amount": 100},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_summary(client: AsyncClient, test_admin):
    admin_headers = auth_header(test_admin)
    resp = await client.get("/api/admin/credits/summary", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_credits_granted" in data
    assert "total_credits_spent" in data
