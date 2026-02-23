"""QuotaService 단위 테스트. DB 세션을 mock."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.quota_service import QuotaService


def _make_quota(
    user_id=None,
    daily_limit=100_000,
    monthly_limit=2_000_000,
    cost_limit=10.0,
    is_active=True,
):
    quota = MagicMock()
    quota.id = uuid.uuid4()
    quota.user_id = user_id or uuid.uuid4()
    quota.daily_token_limit = daily_limit
    quota.monthly_token_limit = monthly_limit
    quota.monthly_cost_limit = Decimal(str(cost_limit))
    quota.is_active = is_active
    return quota


def _mock_db_execute_for_check(daily_tokens=0, monthly_tokens=0, monthly_cost=0.0):
    """check_quota 내부의 DB 쿼리 결과를 순서대로 mock.

    호출 순서:
    1. get_user_quota → select(UsageQuota)
    2. daily aggregate query
    3. monthly aggregate query
    """
    daily_row = MagicMock()
    daily_row.total_tokens = daily_tokens

    monthly_row = MagicMock()
    monthly_row.total_tokens = monthly_tokens
    monthly_row.total_cost = Decimal(str(monthly_cost))

    return daily_row, monthly_row


class TestCheckQuotaAllowed:
    """한도 내 사용량 → allowed=True."""

    @pytest.mark.asyncio
    async def test_returns_allowed_when_under_all_limits(self):
        user_id = uuid.uuid4()
        quota = _make_quota(user_id=user_id, daily_limit=100_000, monthly_limit=2_000_000, cost_limit=10.0)
        daily_row, monthly_row = _mock_db_execute_for_check(
            daily_tokens=5000, monthly_tokens=50_000, monthly_cost=1.5,
        )

        db = AsyncMock()
        # 1st call: get_user_quota
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = quota
        # 2nd call: daily aggregate
        daily_result = MagicMock()
        daily_result.one.return_value = daily_row
        # 3rd call: monthly aggregate
        monthly_result = MagicMock()
        monthly_result.one.return_value = monthly_row

        db.execute = AsyncMock(side_effect=[quota_result, daily_result, monthly_result])

        service = QuotaService(db)
        status = await service.check_quota(user_id)

        assert status["allowed"] is True
        assert status["daily_tokens_used"] == 5000
        assert status["daily_token_limit"] == 100_000
        assert status["daily_remaining"] == 95_000
        assert status["monthly_tokens_used"] == 50_000
        assert status["monthly_token_limit"] == 2_000_000
        assert status["monthly_remaining"] == 1_950_000
        assert status["monthly_cost_used"] == 1.5
        assert status["monthly_cost_limit"] == 10.0


class TestCheckQuotaDailyExceeded:
    """일일 한도 초과 → allowed=False."""

    @pytest.mark.asyncio
    async def test_returns_not_allowed_when_daily_limit_exceeded(self):
        user_id = uuid.uuid4()
        quota = _make_quota(user_id=user_id, daily_limit=100_000)
        daily_row, monthly_row = _mock_db_execute_for_check(
            daily_tokens=150_000, monthly_tokens=150_000, monthly_cost=0.5,
        )

        db = AsyncMock()
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = quota
        daily_result = MagicMock()
        daily_result.one.return_value = daily_row
        monthly_result = MagicMock()
        monthly_result.one.return_value = monthly_row

        db.execute = AsyncMock(side_effect=[quota_result, daily_result, monthly_result])

        service = QuotaService(db)
        status = await service.check_quota(user_id)

        assert status["allowed"] is False
        assert status["daily_tokens_used"] == 150_000
        assert status["daily_remaining"] == 0


class TestCheckQuotaMonthlyExceeded:
    """월간 한도 초과 → allowed=False."""

    @pytest.mark.asyncio
    async def test_returns_not_allowed_when_monthly_token_limit_exceeded(self):
        user_id = uuid.uuid4()
        quota = _make_quota(user_id=user_id, monthly_limit=2_000_000)
        daily_row, monthly_row = _mock_db_execute_for_check(
            daily_tokens=1000, monthly_tokens=2_500_000, monthly_cost=5.0,
        )

        db = AsyncMock()
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = quota
        daily_result = MagicMock()
        daily_result.one.return_value = daily_row
        monthly_result = MagicMock()
        monthly_result.one.return_value = monthly_row

        db.execute = AsyncMock(side_effect=[quota_result, daily_result, monthly_result])

        service = QuotaService(db)
        status = await service.check_quota(user_id)

        assert status["allowed"] is False
        assert status["monthly_tokens_used"] == 2_500_000
        assert status["monthly_remaining"] == 0

    @pytest.mark.asyncio
    async def test_returns_not_allowed_when_monthly_cost_limit_exceeded(self):
        user_id = uuid.uuid4()
        quota = _make_quota(user_id=user_id, cost_limit=10.0)
        daily_row, monthly_row = _mock_db_execute_for_check(
            daily_tokens=1000, monthly_tokens=500_000, monthly_cost=12.5,
        )

        db = AsyncMock()
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = quota
        daily_result = MagicMock()
        daily_result.one.return_value = daily_row
        monthly_result = MagicMock()
        monthly_result.one.return_value = monthly_row

        db.execute = AsyncMock(side_effect=[quota_result, daily_result, monthly_result])

        service = QuotaService(db)
        status = await service.check_quota(user_id)

        assert status["allowed"] is False
        assert status["monthly_cost_used"] == 12.5


class TestCheckQuotaNoQuotaSet:
    """할당 미설정 → 무제한 (allowed=True)."""

    @pytest.mark.asyncio
    async def test_returns_allowed_when_no_quota_exists(self):
        user_id = uuid.uuid4()

        db = AsyncMock()
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=quota_result)

        service = QuotaService(db)
        status = await service.check_quota(user_id)

        assert status["allowed"] is True
        assert status.get("unlimited") is True

    @pytest.mark.asyncio
    async def test_returns_allowed_when_quota_inactive(self):
        user_id = uuid.uuid4()
        quota = _make_quota(user_id=user_id, is_active=False)

        db = AsyncMock()
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = quota
        db.execute = AsyncMock(return_value=quota_result)

        service = QuotaService(db)
        status = await service.check_quota(user_id)

        assert status["allowed"] is True
        assert status.get("unlimited") is True


class TestSetUserQuota:
    """할당 생성/업데이트 테스트."""

    @pytest.mark.asyncio
    async def test_creates_new_quota_when_none_exists(self):
        user_id = uuid.uuid4()

        db = AsyncMock()
        # get_user_quota returns None
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=quota_result)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        service = QuotaService(db)
        result = await service.set_user_quota(
            user_id=user_id,
            daily_limit=50_000,
            monthly_limit=1_000_000,
            cost_limit=5.0,
        )

        # db.add가 UsageQuota 인스턴스로 호출되었는지
        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert added_obj.user_id == user_id
        assert added_obj.daily_token_limit == 50_000
        assert added_obj.monthly_token_limit == 1_000_000
        assert added_obj.monthly_cost_limit == 5.0

    @pytest.mark.asyncio
    async def test_updates_existing_quota(self):
        user_id = uuid.uuid4()
        existing_quota = _make_quota(
            user_id=user_id, daily_limit=100_000, monthly_limit=2_000_000, cost_limit=10.0,
        )

        db = AsyncMock()
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = existing_quota
        db.execute = AsyncMock(return_value=quota_result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        service = QuotaService(db)
        await service.set_user_quota(
            user_id=user_id,
            daily_limit=200_000,
        )

        # 기존 quota 객체의 daily_token_limit이 업데이트됨
        assert existing_quota.daily_token_limit == 200_000
        # 다른 필드는 변경되지 않음
        assert existing_quota.monthly_token_limit == 2_000_000
        # db.add 호출 안 됨 (기존 객체 업데이트)
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_defaults_when_limits_not_specified(self):
        user_id = uuid.uuid4()

        db = AsyncMock()
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=quota_result)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        service = QuotaService(db)
        await service.set_user_quota(user_id=user_id)

        added_obj = db.add.call_args[0][0]
        defaults = QuotaService.get_default_limits()
        assert added_obj.daily_token_limit == defaults["daily_token_limit"]
        assert added_obj.monthly_token_limit == defaults["monthly_token_limit"]
        assert added_obj.monthly_cost_limit == defaults["monthly_cost_limit"]


class TestGetDefaultLimits:
    """설정에서 기본 한도를 반환하는지 확인."""

    def test_returns_defaults_from_settings(self):
        defaults = QuotaService.get_default_limits()

        assert "daily_token_limit" in defaults
        assert "monthly_token_limit" in defaults
        assert "monthly_cost_limit" in defaults
        assert isinstance(defaults["daily_token_limit"], int)
        assert isinstance(defaults["monthly_token_limit"], int)
        assert isinstance(defaults["monthly_cost_limit"], float)

    @patch("app.services.quota_service.settings")
    def test_reflects_custom_settings(self, mock_settings):
        mock_settings.default_daily_token_limit = 50_000
        mock_settings.default_monthly_token_limit = 500_000
        mock_settings.default_monthly_cost_limit = 25.0

        defaults = QuotaService.get_default_limits()

        assert defaults["daily_token_limit"] == 50_000
        assert defaults["monthly_token_limit"] == 500_000
        assert defaults["monthly_cost_limit"] == 25.0
