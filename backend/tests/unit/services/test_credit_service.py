"""CreditService 단위 테스트. DB 세션을 mock."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.credit_service import CreditService, PURCHASE_PACKAGES


def _make_user(credit_balance=100, last_grant=None):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.credit_balance = credit_balance
    user.last_credit_grant_at = last_grant
    return user


def _make_plan(plan_key="free", daily_credits=50):
    plan = MagicMock()
    plan.plan_key = plan_key
    plan.display_name = "무료" if plan_key == "free" else "프리미엄"
    plan.daily_credits = daily_credits
    plan.price_krw = 0 if plan_key == "free" else 6900
    plan.credit_rollover_days = 0
    plan.max_lounge_personas = 1
    plan.max_agent_actions = 5
    return plan


class TestGetBalance:

    @pytest.mark.asyncio
    async def test_returns_balance_with_plan_info(self):
        user = _make_user(credit_balance=200)
        plan = _make_plan()

        db = AsyncMock()
        # 1st call: select(User)
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        # _get_user_plan calls
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = None
        free_result = MagicMock()
        free_result.scalar_one_or_none.return_value = plan
        db.execute = AsyncMock(side_effect=[user_result, sub_result, free_result])

        service = CreditService(db)
        result = await service.get_balance(user.id)

        assert result["balance"] == 200
        assert result["plan_key"] == "free"
        assert result["daily_credits"] == 50


class TestGrantDailyCredits:

    @pytest.mark.asyncio
    async def test_grants_when_not_granted_today(self):
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        user = _make_user(credit_balance=10, last_grant=yesterday)
        plan = _make_plan(daily_credits=50)

        db = AsyncMock()
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = None
        free_result = MagicMock()
        free_result.scalar_one_or_none.return_value = plan
        # UPDATE ... RETURNING → fetchone().credit_balance = 60
        update_result = MagicMock()
        returning_row = MagicMock()
        returning_row.credit_balance = 60
        update_result.fetchone.return_value = returning_row
        db.execute = AsyncMock(side_effect=[user_result, sub_result, free_result, update_result])

        service = CreditService(db)
        ledger = await service.grant_daily_credits(user.id)

        assert ledger is not None
        assert ledger.amount == 50
        assert ledger.balance_after == 60
        assert ledger.tx_type == "daily_grant"

    @pytest.mark.asyncio
    async def test_skips_when_already_granted_today(self):
        now = datetime.now(timezone.utc)
        user = _make_user(credit_balance=100, last_grant=now)

        db = AsyncMock()
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        db.execute = AsyncMock(return_value=user_result)

        service = CreditService(db)
        ledger = await service.grant_daily_credits(user.id)

        assert ledger is None


class TestCheckAndDeduct:

    @pytest.mark.asyncio
    async def test_deducts_when_balance_sufficient(self):
        user = _make_user(credit_balance=50)

        db = AsyncMock()
        # _get_cost → scalar_one_or_none returns 3
        cost_result = MagicMock()
        cost_result.scalar_one_or_none.return_value = 3
        # UPDATE...RETURNING → fetchone returns row with credit_balance=47
        update_result = MagicMock()
        row = MagicMock()
        row.credit_balance = 47
        update_result.fetchone.return_value = row
        db.execute = AsyncMock(side_effect=[cost_result, update_result])

        service = CreditService(db)
        ledger = await service.check_and_deduct(user.id, "chat", "standard")

        assert ledger.amount == -3
        assert ledger.balance_after == 47
        assert ledger.tx_type == "chat"

    @pytest.mark.asyncio
    async def test_raises_402_when_insufficient(self):
        user = _make_user(credit_balance=1)

        db = AsyncMock()
        # _get_cost → cost = 5
        cost_result = MagicMock()
        cost_result.scalar_one_or_none.return_value = 5
        # UPDATE...RETURNING → fetchone returns None (balance insufficient)
        update_result = MagicMock()
        update_result.fetchone.return_value = None
        # SELECT User.credit_balance → balance = 1
        balance_result = MagicMock()
        balance_result.scalar_one_or_none.return_value = 1
        db.execute = AsyncMock(side_effect=[cost_result, update_result, balance_result])

        service = CreditService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.check_and_deduct(user.id, "chat", "premium")
        assert exc_info.value.status_code == 402


class TestPurchaseCredits:

    @pytest.mark.asyncio
    async def test_small_package_adds_500(self):
        user = _make_user(credit_balance=100)

        db = AsyncMock()
        # select(User.id) 존재 확인 → scalar_one_or_none returns user.id (non-None)
        exists_result = MagicMock()
        exists_result.scalar_one_or_none.return_value = user.id
        # UPDATE ... RETURNING → fetchone().credit_balance = 600
        update_result = MagicMock()
        returning_row = MagicMock()
        returning_row.credit_balance = 600
        update_result.fetchone.return_value = returning_row
        db.execute = AsyncMock(side_effect=[exists_result, update_result])
        db.commit = AsyncMock()

        service = CreditService(db)
        result = await service.purchase_credits(user.id, "small")

        assert result["credits_added"] == 500
        assert result["price_krw"] == 1000
        assert result["new_balance"] == 600

    @pytest.mark.asyncio
    async def test_invalid_package_raises_400(self):
        db = AsyncMock()
        service = CreditService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.purchase_credits(uuid.uuid4(), "invalid")
        assert exc_info.value.status_code == 400


class TestGetCostDefaults:

    @pytest.mark.asyncio
    async def test_returns_default_when_no_db_entry(self):
        db = AsyncMock()
        cost_result = MagicMock()
        cost_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=cost_result)

        service = CreditService(db)
        cost = await service._get_cost("chat", "economy")
        assert cost == 1

    @pytest.mark.asyncio
    async def test_returns_db_value_when_exists(self):
        db = AsyncMock()
        cost_result = MagicMock()
        cost_result.scalar_one_or_none.return_value = 5
        db.execute = AsyncMock(return_value=cost_result)

        service = CreditService(db)
        cost = await service._get_cost("chat", "premium")
        assert cost == 5
