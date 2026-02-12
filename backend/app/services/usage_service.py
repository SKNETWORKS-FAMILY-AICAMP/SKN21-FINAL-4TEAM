import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import cast, func, select, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from app.models.user import User


class UsageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log_usage(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID | None,
        llm_model_id: uuid.UUID,
        input_tokens: int,
        output_tokens: int,
    ) -> TokenUsageLog:
        """토큰 사용량 기록 + 비용 산출."""
        # 모델 비용 조회
        result = await self.db.execute(select(LLMModel).where(LLMModel.id == llm_model_id))
        model = result.scalar_one_or_none()

        if model:
            input_cost = Decimal(str(input_tokens)) * Decimal(str(model.input_cost_per_1m)) / Decimal("1000000")
            output_cost = Decimal(str(output_tokens)) * Decimal(str(model.output_cost_per_1m)) / Decimal("1000000")
            cost = input_cost + output_cost
        else:
            cost = Decimal("0")

        log = TokenUsageLog(
            user_id=user_id,
            session_id=session_id,
            llm_model_id=llm_model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def get_user_summary(self, user_id: uuid.UUID) -> dict:
        """사용자 사용량 요약 (일/월/총계)."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        base = select(
            func.coalesce(func.sum(TokenUsageLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(TokenUsageLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(TokenUsageLog.cost), 0).label("cost"),
        ).where(TokenUsageLog.user_id == user_id)

        # 총계
        total = (await self.db.execute(base)).one()
        # 오늘
        daily = (await self.db.execute(
            base.where(TokenUsageLog.created_at >= today_start)
        )).one()
        # 이번 달
        monthly = (await self.db.execute(
            base.where(TokenUsageLog.created_at >= month_start)
        )).one()

        return {
            "total_input_tokens": int(total.input_tokens),
            "total_output_tokens": int(total.output_tokens),
            "total_cost": float(total.cost),
            "daily_input_tokens": int(daily.input_tokens),
            "daily_output_tokens": int(daily.output_tokens),
            "daily_cost": float(daily.cost),
            "monthly_input_tokens": int(monthly.input_tokens),
            "monthly_output_tokens": int(monthly.output_tokens),
            "monthly_cost": float(monthly.cost),
        }

    async def get_user_history(self, user_id: uuid.UUID, days: int = 30) -> list[dict]:
        """일별 사용량 히스토리."""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        query = (
            select(
                cast(TokenUsageLog.created_at, Date).label("date"),
                func.sum(TokenUsageLog.input_tokens).label("input_tokens"),
                func.sum(TokenUsageLog.output_tokens).label("output_tokens"),
                func.sum(TokenUsageLog.cost).label("cost"),
            )
            .where(
                TokenUsageLog.user_id == user_id,
                TokenUsageLog.created_at >= since,
            )
            .group_by(cast(TokenUsageLog.created_at, Date))
            .order_by(cast(TokenUsageLog.created_at, Date).asc())
        )
        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "date": str(row.date),
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "cost": float(row.cost),
            }
            for row in rows
        ]

    async def get_admin_summary(self) -> dict:
        """전체 사용량 통계 (관리자용)."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        base = select(
            func.coalesce(func.sum(TokenUsageLog.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(TokenUsageLog.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(TokenUsageLog.cost), 0).label("cost"),
            func.count(func.distinct(TokenUsageLog.user_id)).label("unique_users"),
        )

        # 총계
        total = (await self.db.execute(base)).one()
        # 오늘
        daily = (await self.db.execute(
            base.where(TokenUsageLog.created_at >= today_start)
        )).one()
        # 이번 달
        monthly = (await self.db.execute(
            base.where(TokenUsageLog.created_at >= month_start)
        )).one()

        # 모델별 사용량
        model_query = (
            select(
                LLMModel.display_name,
                func.sum(TokenUsageLog.input_tokens).label("input_tokens"),
                func.sum(TokenUsageLog.output_tokens).label("output_tokens"),
                func.sum(TokenUsageLog.cost).label("cost"),
            )
            .join(LLMModel, TokenUsageLog.llm_model_id == LLMModel.id)
            .group_by(LLMModel.display_name)
            .order_by(func.sum(TokenUsageLog.cost).desc())
        )
        model_rows = (await self.db.execute(model_query)).all()

        return {
            "total": {
                "input_tokens": int(total.input_tokens),
                "output_tokens": int(total.output_tokens),
                "cost": float(total.cost),
                "unique_users": int(total.unique_users),
            },
            "daily": {
                "input_tokens": int(daily.input_tokens),
                "output_tokens": int(daily.output_tokens),
                "cost": float(daily.cost),
                "unique_users": int(daily.unique_users),
            },
            "monthly": {
                "input_tokens": int(monthly.input_tokens),
                "output_tokens": int(monthly.output_tokens),
                "cost": float(monthly.cost),
                "unique_users": int(monthly.unique_users),
            },
            "by_model": [
                {
                    "model_name": row.display_name,
                    "input_tokens": int(row.input_tokens),
                    "output_tokens": int(row.output_tokens),
                    "cost": float(row.cost),
                }
                for row in model_rows
            ],
        }

    async def get_user_usage_admin(self, user_id: uuid.UUID) -> dict:
        """관리자가 특정 사용자의 사용량을 조회."""
        summary = await self.get_user_summary(user_id)
        history = await self.get_user_history(user_id, days=30)
        return {"summary": summary, "history": history}
