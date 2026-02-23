"""SubscriptionService 단위 테스트."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.subscription_service import SubscriptionService


def _make_plan(plan_key="premium", price_krw=6900):
    plan = MagicMock()
    plan.id = uuid.uuid4()
    plan.plan_key = plan_key
    plan.display_name = "프리미엄" if plan_key == "premium" else "무료"
    plan.price_krw = price_krw
    plan.daily_credits = 300 if plan_key == "premium" else 50
    plan.is_active = True
    return plan


def _make_sub(user_id=None, plan_id=None, sub_status="active"):
    sub = MagicMock()
    sub.id = uuid.uuid4()
    sub.user_id = user_id or uuid.uuid4()
    sub.plan_id = plan_id or uuid.uuid4()
    sub.status = sub_status
    sub.started_at = datetime.now(timezone.utc)
    sub.expires_at = None
    sub.cancelled_at = None
    return sub


class TestGetPlans:

    @pytest.mark.asyncio
    async def test_returns_active_plans(self):
        plans = [_make_plan("free", 0), _make_plan("premium", 6900)]

        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = plans
        db.execute = AsyncMock(return_value=result)

        service = SubscriptionService(db)
        result = await service.get_plans()

        assert len(result) == 2
        assert result[0].plan_key == "free"


class TestGetMySubscription:

    @pytest.mark.asyncio
    async def test_returns_none_when_no_subscription(self):
        db = AsyncMock()
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=sub_result)

        service = SubscriptionService(db)
        result = await service.get_my_subscription(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_subscription_with_plan(self):
        plan = _make_plan()
        sub = _make_sub(plan_id=plan.id)

        db = AsyncMock()
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sub
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = plan
        db.execute = AsyncMock(side_effect=[sub_result, plan_result])

        service = SubscriptionService(db)
        result = await service.get_my_subscription(sub.user_id)

        assert result is not None
        assert result["status"] == "active"
        assert result["plan"].plan_key == "premium"


class TestCancel:

    @pytest.mark.asyncio
    async def test_cancel_sets_status_cancelled(self):
        plan = _make_plan("premium", 6900)
        sub = _make_sub()

        db = AsyncMock()
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sub
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = plan
        db.execute = AsyncMock(side_effect=[sub_result, plan_result])
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        service = SubscriptionService(db)
        result = await service.cancel(sub.user_id)

        assert result.status == "cancelled"
        assert result.cancelled_at is not None

    @pytest.mark.asyncio
    async def test_cancel_free_plan_raises_400(self):
        plan = _make_plan("free", 0)
        sub = _make_sub()

        db = AsyncMock()
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sub
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = plan
        db.execute = AsyncMock(side_effect=[sub_result, plan_result])

        service = SubscriptionService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.cancel(sub.user_id)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_cancel_no_active_raises_404(self):
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        service = SubscriptionService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.cancel(uuid.uuid4())
        assert exc_info.value.status_code == 404
