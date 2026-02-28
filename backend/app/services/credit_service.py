"""대화석 크레딧 서비스.

크레딧 잔액 관리, 일일 충전, 차감, 구매, 거래 내역 조회를 담당한다.
credit_ledger는 append-only로 운영하며, users.credit_balance는 캐시 필드이다.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_cost import CreditCost
from app.models.credit_ledger import CreditLedger
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.models.user_subscription import UserSubscription

logger = logging.getLogger(__name__)

# 대화석 구매 패키지
PURCHASE_PACKAGES: dict[str, dict[str, int]] = {
    "small": {"credits": 500, "price_krw": 1000},
    "medium": {"credits": 3000, "price_krw": 5000},
    "large": {"credits": 10000, "price_krw": 15000},
}


class CreditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_balance(self, user_id: uuid.UUID) -> dict[str, Any]:
        """현재 잔액 + 오늘 충전 여부 + 플랜 정보."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        plan = await self._get_user_plan(user_id)
        now = datetime.now(UTC)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        granted_today = user.last_credit_grant_at is not None and user.last_credit_grant_at >= today

        return {
            "balance": user.credit_balance,
            "daily_credits": plan.daily_credits,
            "granted_today": granted_today,
            "plan_key": plan.plan_key,
        }

    async def grant_daily_credits(self, user_id: uuid.UUID) -> CreditLedger | None:
        """일일 대화석 충전. 오늘 이미 충전했으면 None 반환."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        now = datetime.now(UTC)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if user.last_credit_grant_at is not None and user.last_credit_grant_at >= today:
            return None

        plan = await self._get_user_plan(user_id)
        amount = plan.daily_credits
        new_balance = user.credit_balance + amount

        ledger = CreditLedger(
            user_id=user_id,
            amount=amount,
            balance_after=new_balance,
            tx_type="daily_grant",
            description=f"일일 충전 ({plan.display_name})",
        )
        self.db.add(ledger)

        await self.db.execute(
            update(User).where(User.id == user_id).values(credit_balance=new_balance, last_credit_grant_at=now)
        )
        await self.db.flush()

        from app.services.notification_service import NotificationService

        notif_svc = NotificationService(self.db)
        await notif_svc.create(
            user_id=user_id,
            type_="credit",
            title=f"일일 대화석 {amount}개 충전!",
            body="오늘의 무료 대화석이 충전되었습니다.",
            link="/mypage?tab=usage",
        )

        return ledger

    async def check_and_deduct(
        self,
        user_id: uuid.UUID,
        action: str,
        model_tier: str,
        reference_id: str | None = None,
    ) -> CreditLedger:
        """크레딧 잔액 확인 후 원자적 차감. 부족하면 402 반환."""
        cost = await self._get_cost(action, model_tier)

        # 원자적 UPDATE: 잔액이 충분할 때만 차감 (레이스 컨디션 방지)
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id, User.credit_balance >= cost)
            .values(credit_balance=User.credit_balance - cost)
            .returning(User.credit_balance)
        )
        row = result.fetchone()

        if row is None:
            # UPDATE가 적용되지 않음 — 사용자 없음 또는 잔액 부족
            check = await self.db.execute(select(User.credit_balance).where(User.id == user_id))
            balance = check.scalar_one_or_none()
            if balance is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"대화석이 부족합니다 (필요: {cost}, 보유: {balance})",
                headers={"X-Error-Code": "CREDITS_INSUFFICIENT"},
            )

        new_balance = row.credit_balance
        ledger = CreditLedger(
            user_id=user_id,
            amount=-cost,
            balance_after=new_balance,
            tx_type=action,
            reference_id=reference_id,
            description=f"{action} ({model_tier}): -{cost}석",
        )
        self.db.add(ledger)
        await self.db.flush()
        return ledger

    async def deduct_by_tokens(
        self,
        user_id: uuid.UUID,
        total_tokens: int,
        credit_per_1k_tokens: int,
        reference_id: str | None = None,
    ) -> CreditLedger:
        """토큰 수 기반 원자적 크레딧 차감. cost = ceil(total_tokens / 1000 * rate), 최소 1석."""
        cost = max(1, -(-total_tokens * credit_per_1k_tokens // 1000))  # ceiling division

        # 원자적 UPDATE: 잔액이 충분할 때만 차감 (동시 요청 레이스 컨디션 방지)
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id, User.credit_balance >= cost)
            .values(credit_balance=User.credit_balance - cost)
            .returning(User.credit_balance)
        )
        row = result.fetchone()

        if row is None:
            # UPDATE가 적용되지 않음 — 사용자 없음 또는 잔액 부족
            check = await self.db.execute(select(User.credit_balance).where(User.id == user_id))
            balance = check.scalar_one_or_none()
            if balance is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"대화석이 부족합니다 (필요: {cost}, 보유: {balance})",
                headers={"X-Error-Code": "CREDITS_INSUFFICIENT"},
            )

        new_balance = row.credit_balance
        ledger = CreditLedger(
            user_id=user_id,
            amount=-cost,
            balance_after=new_balance,
            tx_type="chat",
            reference_id=reference_id,
            description=f"chat ({total_tokens} tokens × {credit_per_1k_tokens}석/1K): -{cost}석",
        )
        self.db.add(ledger)
        await self.db.flush()
        return ledger

    async def check_has_credits(self, user_id: uuid.UUID) -> bool:
        """잔액이 1석 이상인지 확인 (토큰 기반 과금의 사전 체크용)."""
        result = await self.db.execute(select(User.credit_balance).where(User.id == user_id))
        balance = result.scalar_one_or_none()
        return balance is not None and balance > 0

    async def check_balance_sufficient(self, user_id: uuid.UUID, action: str, model_tier: str) -> bool:
        """차감 없이 잔액이 충분한지만 확인."""
        cost = await self._get_cost(action, model_tier)
        result = await self.db.execute(select(User.credit_balance).where(User.id == user_id))
        balance = result.scalar_one_or_none()
        if balance is None:
            return False
        return balance >= cost

    async def purchase_credits(self, user_id: uuid.UUID, package: str) -> dict[str, Any]:
        """대화석 구매."""
        if package not in PURCHASE_PACKAGES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid package: {package}")

        pkg = PURCHASE_PACKAGES[package]
        amount = pkg["credits"]

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        new_balance = user.credit_balance + amount

        ledger = CreditLedger(
            user_id=user_id,
            amount=amount,
            balance_after=new_balance,
            tx_type="purchase",
            description=f"대화석 구매 ({package}: {amount}석)",
        )
        self.db.add(ledger)

        await self.db.execute(update(User).where(User.id == user_id).values(credit_balance=new_balance))
        await self.db.commit()

        return {
            "credits_added": amount,
            "price_krw": pkg["price_krw"],
            "new_balance": new_balance,
        }

    async def admin_grant(self, user_id: uuid.UUID, amount: int, description: str | None = None) -> CreditLedger:
        """관리자 크레딧 지급."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        new_balance = user.credit_balance + amount

        ledger = CreditLedger(
            user_id=user_id,
            amount=amount,
            balance_after=new_balance,
            tx_type="admin_grant",
            description=description or f"관리자 지급: +{amount}석",
        )
        self.db.add(ledger)

        await self.db.execute(update(User).where(User.id == user_id).values(credit_balance=new_balance))
        await self.db.commit()
        await self.db.refresh(ledger)
        return ledger

    async def get_history(self, user_id: uuid.UUID, skip: int = 0, limit: int = 20) -> dict[str, Any]:
        """거래 내역 조회."""
        count_q = select(func.count()).select_from(CreditLedger).where(CreditLedger.user_id == user_id)
        total = (await self.db.execute(count_q)).scalar()

        q = (
            select(CreditLedger)
            .where(CreditLedger.user_id == user_id)
            .order_by(CreditLedger.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(q)
        items = result.scalars().all()
        return {"items": list(items), "total": total}

    async def get_cost_table(self) -> list[CreditCost]:
        """행동별 소비 단가 테이블."""
        result = await self.db.execute(select(CreditCost).order_by(CreditCost.action, CreditCost.model_tier))
        return list(result.scalars().all())

    async def get_admin_summary(self) -> dict[str, Any]:
        """전체 크레딧 경제 통계."""
        now = datetime.now(UTC)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 총 지급/소비/구매
        granted = (
            await self.db.execute(
                select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(CreditLedger.amount > 0)
            )
        ).scalar()

        spent = (
            await self.db.execute(
                select(func.coalesce(func.sum(func.abs(CreditLedger.amount)), 0)).where(CreditLedger.amount < 0)
            )
        ).scalar()

        purchased = (
            await self.db.execute(
                select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(CreditLedger.tx_type == "purchase")
            )
        ).scalar()

        active_today = (
            await self.db.execute(
                select(func.count(func.distinct(CreditLedger.user_id))).where(CreditLedger.created_at >= today)
            )
        ).scalar()

        return {
            "total_credits_granted": int(granted),
            "total_credits_spent": int(spent),
            "total_credits_purchased": int(purchased),
            "active_users_today": int(active_today),
        }

    # ── 내부 헬퍼 ──

    async def _get_user_plan(self, user_id: uuid.UUID) -> SubscriptionPlan:
        """유저의 현재 구독 플랜 조회. 구독 없으면 free 플랜."""
        sub_q = (
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id, UserSubscription.status == "active")
            .order_by(UserSubscription.created_at.desc())
            .limit(1)
        )
        sub_result = await self.db.execute(sub_q)
        sub = sub_result.scalar_one_or_none()

        if sub is not None:
            plan_result = await self.db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == sub.plan_id))
            plan = plan_result.scalar_one_or_none()
            if plan is not None:
                return plan

        # 무료 플랜 폴백
        free_result = await self.db.execute(select(SubscriptionPlan).where(SubscriptionPlan.plan_key == "free"))
        free_plan = free_result.scalar_one_or_none()
        if free_plan is None:
            # free 플랜이 DB에 없으면 기본값 반환
            return SubscriptionPlan(
                plan_key="free",
                display_name="무료",
                price_krw=0,
                daily_credits=50,
                credit_rollover_days=0,
                max_lounge_personas=1,
                max_agent_actions=5,
            )
        return free_plan

    async def _get_cost(self, action: str, model_tier: str) -> int:
        """행동 + 모델 등급 → 대화석 소비량."""
        result = await self.db.execute(
            select(CreditCost.cost).where(
                CreditCost.action == action,
                CreditCost.model_tier == model_tier,
            )
        )
        cost = result.scalar_one_or_none()
        if cost is None:
            # 단가 미설정 시 기본값 (경제형 기준)
            defaults = {"chat": 1, "lounge_post": 2, "lounge_comment": 1, "review": 3, "agent_action": 1}
            return defaults.get(action, 1)
        return cost
