"""사용량 할당 검증 서비스."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.token_usage_log import TokenUsageLog
from app.models.usage_quota import UsageQuota


class QuotaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_quota(self, user_id: uuid.UUID) -> UsageQuota | None:
        """사용자의 할당 조회. None이면 할당 미설정(무제한)."""
        result = await self.db.execute(select(UsageQuota).where(UsageQuota.user_id == user_id))
        return result.scalar_one_or_none()

    async def check_quota(self, user_id: uuid.UUID) -> dict[str, Any]:
        """사용자가 한도 내인지 확인. 할당이 없거나 비활성이면 allowed=True."""
        quota = await self.get_user_quota(user_id)

        # 할당 미설정 또는 비활성 → 무제한
        if quota is None or not quota.is_active:
            return {
                "allowed": True,
                "daily_tokens_used": 0,
                "daily_token_limit": 0,
                "daily_remaining": 0,
                "monthly_tokens_used": 0,
                "monthly_token_limit": 0,
                "monthly_remaining": 0,
                "monthly_cost_used": 0.0,
                "monthly_cost_limit": 0.0,
                "unlimited": True,
            }

        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 일일 사용량 집계
        daily_query = select(
            func.coalesce(func.sum(TokenUsageLog.input_tokens + TokenUsageLog.output_tokens), 0).label("total_tokens"),
        ).where(
            TokenUsageLog.user_id == user_id,
            TokenUsageLog.created_at >= today_start,
        )
        daily_result = (await self.db.execute(daily_query)).one()
        daily_tokens_used = int(daily_result.total_tokens)

        # 월간 사용량 집계 (토큰 + 비용)
        monthly_query = select(
            func.coalesce(func.sum(TokenUsageLog.input_tokens + TokenUsageLog.output_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(TokenUsageLog.cost), 0).label("total_cost"),
        ).where(
            TokenUsageLog.user_id == user_id,
            TokenUsageLog.created_at >= month_start,
        )
        monthly_result = (await self.db.execute(monthly_query)).one()
        monthly_tokens_used = int(monthly_result.total_tokens)
        monthly_cost_used = float(monthly_result.total_cost)

        daily_remaining = max(0, quota.daily_token_limit - daily_tokens_used)
        monthly_remaining = max(0, quota.monthly_token_limit - monthly_tokens_used)

        # 한도 초과 여부 판단
        allowed = (
            daily_tokens_used < quota.daily_token_limit
            and monthly_tokens_used < quota.monthly_token_limit
            and monthly_cost_used < float(quota.monthly_cost_limit)
        )

        return {
            "allowed": allowed,
            "daily_tokens_used": daily_tokens_used,
            "daily_token_limit": quota.daily_token_limit,
            "daily_remaining": daily_remaining,
            "monthly_tokens_used": monthly_tokens_used,
            "monthly_token_limit": quota.monthly_token_limit,
            "monthly_remaining": monthly_remaining,
            "monthly_cost_used": monthly_cost_used,
            "monthly_cost_limit": float(quota.monthly_cost_limit),
        }

    async def set_user_quota(
        self,
        user_id: uuid.UUID,
        daily_limit: int | None = None,
        monthly_limit: int | None = None,
        cost_limit: float | None = None,
        is_active: bool | None = None,
    ) -> UsageQuota:
        """사용자 할당 upsert. 기존이 있으면 업데이트, 없으면 생성."""
        quota = await self.get_user_quota(user_id)

        defaults = self.get_default_limits()

        if quota is None:
            quota = UsageQuota(
                user_id=user_id,
                daily_token_limit=daily_limit if daily_limit is not None else defaults["daily_token_limit"],
                monthly_token_limit=monthly_limit if monthly_limit is not None else defaults["monthly_token_limit"],
                monthly_cost_limit=cost_limit if cost_limit is not None else defaults["monthly_cost_limit"],
                is_active=is_active if is_active is not None else True,
            )
            self.db.add(quota)
        else:
            if daily_limit is not None:
                quota.daily_token_limit = daily_limit
            if monthly_limit is not None:
                quota.monthly_token_limit = monthly_limit
            if cost_limit is not None:
                quota.monthly_cost_limit = cost_limit
            if is_active is not None:
                quota.is_active = is_active

        await self.db.commit()
        await self.db.refresh(quota)
        return quota

    @staticmethod
    def get_default_limits() -> dict[str, Any]:
        """설정에서 기본 할당 한도를 반환."""
        return {
            "daily_token_limit": settings.default_daily_token_limit,
            "monthly_token_limit": settings.default_monthly_token_limit,
            "monthly_cost_limit": settings.default_monthly_cost_limit,
        }
