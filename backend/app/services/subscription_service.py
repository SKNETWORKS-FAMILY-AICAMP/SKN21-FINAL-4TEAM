"""구독 서비스.

구독 플랜 조회, 구독 시작/해지, 상태 관리를 담당한다.
프로토타입 단계에서는 실제 결제 연동 없이 상태만 관리한다.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.models.user_subscription import UserSubscription

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_plans(self) -> list[SubscriptionPlan]:
        """활성 구독 플랜 목록."""
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.price_krw)
        )
        return list(result.scalars().all())

    async def get_my_subscription(self, user_id: uuid.UUID) -> dict[str, Any] | None:
        """내 활성 구독 조회. 없으면 None."""
        q = (
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id, UserSubscription.status == "active")
            .order_by(UserSubscription.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(q)
        sub = result.scalar_one_or_none()
        if sub is None:
            return None

        plan_result = await self.db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id))
        plan = plan_result.scalar_one_or_none()

        return {
            "id": sub.id,
            "plan": plan,
            "status": sub.status,
            "started_at": sub.started_at,
            "expires_at": sub.expires_at,
            "cancelled_at": sub.cancelled_at,
        }

    async def subscribe(self, user_id: uuid.UUID, plan_key: str) -> UserSubscription:
        """구독 시작. 기존 활성 구독이 있으면 만료 처리 후 새 구독 생성."""
        # 플랜 확인
        plan_result = await self.db.execute(
            select(SubscriptionPlan).where(
                SubscriptionPlan.plan_key == plan_key,
                SubscriptionPlan.is_active == True,
            )
        )
        plan = plan_result.scalar_one_or_none()
        if plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

        # 유저 확인
        user_result = await self.db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # 기존 활성 구독 만료 처리
        existing_q = select(UserSubscription).where(
            UserSubscription.user_id == user_id, UserSubscription.status == "active"
        )
        existing_result = await self.db.execute(existing_q)
        for existing in existing_result.scalars().all():
            existing.status = "expired"

        now = datetime.now(UTC)
        expires_at = None
        if plan.price_krw > 0:
            expires_at = now + relativedelta(months=1)

        sub = UserSubscription(
            user_id=user_id,
            plan_id=plan.id,
            status="active",
            started_at=now,
            expires_at=expires_at,
        )
        self.db.add(sub)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def cancel(self, user_id: uuid.UUID) -> UserSubscription:
        """활성 구독 해지. 즉시 만료가 아닌 기간 만료 시 종료."""
        q = (
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id, UserSubscription.status == "active")
            .order_by(UserSubscription.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(q)
        sub = result.scalar_one_or_none()
        if sub is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription")

        # free 플랜은 해지 불가
        plan_result = await self.db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id))
        plan = plan_result.scalar_one_or_none()
        if plan and plan.plan_key == "free":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot cancel free plan")

        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(sub)
        return sub

    async def get_admin_summary(self) -> dict[str, Any]:
        """구독 통계 (관리자용)."""
        total = (await self.db.execute(select(func.count()).select_from(UserSubscription))).scalar()

        active = (
            await self.db.execute(
                select(func.count()).select_from(UserSubscription).where(UserSubscription.status == "active")
            )
        ).scalar()

        # 플랜별 구독자 수
        breakdown_q = (
            select(
                SubscriptionPlan.plan_key,
                SubscriptionPlan.display_name,
                SubscriptionPlan.price_krw,
                func.count(UserSubscription.id).label("count"),
            )
            .join(SubscriptionPlan, UserSubscription.plan_id == SubscriptionPlan.id)
            .where(UserSubscription.status == "active")
            .group_by(SubscriptionPlan.plan_key, SubscriptionPlan.display_name, SubscriptionPlan.price_krw)
        )
        breakdown_result = await self.db.execute(breakdown_q)
        breakdown = []
        monthly_revenue = 0
        for row in breakdown_result.all():
            breakdown.append(
                {
                    "plan_key": row.plan_key,
                    "display_name": row.display_name,
                    "price_krw": row.price_krw,
                    "count": row.count,
                }
            )
            monthly_revenue += row.price_krw * row.count

        return {
            "total_subscribers": total,
            "active_subscribers": active,
            "monthly_revenue_krw": monthly_revenue,
            "plan_breakdown": breakdown,
        }
