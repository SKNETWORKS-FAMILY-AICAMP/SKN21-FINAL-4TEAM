"""승급전/강등전 시리즈 서비스.

ELO가 티어 경계를 넘을 때 즉시 승급/강등하는 대신
- 승급전: 3판 2선승(required_wins=2)
- 강등전: 1판 필승(required_wins=1)
시리즈를 생성하여 결과에 따라 티어를 결정한다.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_agent import DebateAgent
from app.models.debate_promotion_series import DebatePromotionSeries

logger = logging.getLogger(__name__)

TIER_ORDER = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"]


class DebatePromotionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_series(self, agent_id: str) -> DebatePromotionSeries | None:
        """에이전트의 현재 활성 시리즈 조회."""
        result = await self.db.execute(
            select(DebatePromotionSeries).where(
                DebatePromotionSeries.agent_id == agent_id,
                DebatePromotionSeries.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def get_series_history(
        self, agent_id: str, limit: int = 20, offset: int = 0
    ) -> list[DebatePromotionSeries]:
        """에이전트의 시리즈 이력 조회 (최신 순)."""
        result = await self.db.execute(
            select(DebatePromotionSeries)
            .where(DebatePromotionSeries.agent_id == agent_id)
            .order_by(DebatePromotionSeries.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create_promotion_series(
        self, agent_id: str, from_tier: str, to_tier: str
    ) -> DebatePromotionSeries:
        """승급전 시리즈 생성 (required_wins=2, 3판 2선승)."""
        series = DebatePromotionSeries(
            agent_id=agent_id,
            series_type="promotion",
            from_tier=from_tier,
            to_tier=to_tier,
            required_wins=2,
        )
        self.db.add(series)
        await self.db.flush()  # ID 확보

        # 에이전트의 active_series_id 업데이트
        await self.db.execute(
            update(DebateAgent)
            .where(DebateAgent.id == agent_id)
            .values(active_series_id=series.id)
        )
        logger.info("Promotion series created: agent=%s %s→%s", agent_id, from_tier, to_tier)
        return series

    async def create_demotion_series(
        self, agent_id: str, from_tier: str, to_tier: str
    ) -> DebatePromotionSeries:
        """강등전 시리즈 생성 (required_wins=1, 1판 필승)."""
        series = DebatePromotionSeries(
            agent_id=agent_id,
            series_type="demotion",
            from_tier=from_tier,
            to_tier=to_tier,
            required_wins=1,
        )
        self.db.add(series)
        await self.db.flush()

        await self.db.execute(
            update(DebateAgent)
            .where(DebateAgent.id == agent_id)
            .values(active_series_id=series.id)
        )
        logger.info("Demotion series created: agent=%s %s→%s", agent_id, from_tier, to_tier)
        return series

    async def record_match_result(self, series_id: str, result: str) -> dict:
        """시리즈에 매치 결과를 기록하고 시리즈 종료 여부를 반환.

        result: 'win' | 'loss'  (무승부는 호출 전에 처리)

        반환 dict:
          series_type, status, current_wins, current_losses,
          required_wins, tier_changed, new_tier (optional)
        """
        res = await self.db.execute(
            select(DebatePromotionSeries).where(DebatePromotionSeries.id == series_id)
        )
        series = res.scalar_one_or_none()
        if series is None or series.status != "active":
            return {"status": "not_found"}

        if result == "win":
            series.current_wins += 1
        else:
            series.current_losses += 1

        # 시리즈 종료 조건 판정
        series_done = False
        series_won = False
        max_losses = 3 - series.required_wins  # 승급전: 1패, 강등전: 0패

        if series.current_wins >= series.required_wins:
            series_done = True
            series_won = True
        elif series.current_losses > max_losses:
            series_done = True
            series_won = False

        tier_changed = False
        new_tier: str | None = None

        if series_done:
            series.status = "won" if series_won else "lost"
            series.completed_at = datetime.now(UTC)

            if series.series_type == "promotion":
                if series_won:
                    # 승급 성공: to_tier로 변경 + 보호 3회
                    await self.db.execute(
                        update(DebateAgent)
                        .where(DebateAgent.id == str(series.agent_id))
                        .values(
                            tier=series.to_tier,
                            tier_protection_count=3,
                            active_series_id=None,
                        )
                    )
                    tier_changed = True
                    new_tier = series.to_tier
                else:
                    # 승급 실패: 티어 유지
                    await self.db.execute(
                        update(DebateAgent)
                        .where(DebateAgent.id == str(series.agent_id))
                        .values(active_series_id=None)
                    )
            else:  # demotion
                if series_won:
                    # 강등전 생존: 티어 유지 + 보호 1회 보상
                    await self.db.execute(
                        update(DebateAgent)
                        .where(DebateAgent.id == str(series.agent_id))
                        .values(
                            tier_protection_count=1,
                            active_series_id=None,
                        )
                    )
                else:
                    # 강등 확정
                    await self.db.execute(
                        update(DebateAgent)
                        .where(DebateAgent.id == str(series.agent_id))
                        .values(
                            tier=series.to_tier,
                            active_series_id=None,
                        )
                    )
                    tier_changed = True
                    new_tier = series.to_tier

        return {
            "series_id": str(series.id),
            "series_type": series.series_type,
            "status": series.status,
            "current_wins": series.current_wins,
            "current_losses": series.current_losses,
            "required_wins": series.required_wins,
            "from_tier": series.from_tier,
            "to_tier": series.to_tier,
            "tier_changed": tier_changed,
            "new_tier": new_tier,
        }

    async def cancel_series(self, agent_id: str) -> None:
        """에이전트의 활성 시리즈를 취소 (비활성화, 탈퇴 등)."""
        series = await self.get_active_series(agent_id)
        if series is None:
            return
        series.status = "cancelled"
        series.completed_at = datetime.now(UTC)
        await self.db.execute(
            update(DebateAgent)
            .where(DebateAgent.id == agent_id)
            .values(active_series_id=None)
        )
        logger.info("Series cancelled: agent=%s series=%s", agent_id, series.id)

    async def check_and_trigger(
        self,
        agent_id: str,
        old_elo: int,
        new_elo: int,
        current_tier: str,
        protection_count: int,
    ) -> DebatePromotionSeries | None:
        """ELO 변화로 승급전/강등전 트리거 여부를 확인하고 시리즈를 생성.

        이미 활성 시리즈가 있으면 생성하지 않는다.
        Iron 강등 / Master 승급은 한계이므로 미생성.
        """
        from app.services.debate_agent_service import get_tier_from_elo

        old_tier = current_tier
        new_tier = get_tier_from_elo(new_elo)
        old_idx = TIER_ORDER.index(old_tier) if old_tier in TIER_ORDER else 0
        new_idx = TIER_ORDER.index(new_tier) if new_tier in TIER_ORDER else 0

        if old_idx == new_idx:
            return None

        # 이미 활성 시리즈가 있으면 새 시리즈 미생성
        existing = await self.get_active_series(agent_id)
        if existing is not None:
            return None

        if new_idx > old_idx:
            # 승급 조건: Master는 이미 최상위이므로 미생성
            if old_tier == "Master":
                return None
            next_tier = TIER_ORDER[old_idx + 1]
            return await self.create_promotion_series(agent_id, old_tier, next_tier)
        else:
            # 강등 조건: Iron은 이미 최하위이므로 미생성
            if old_tier == "Iron":
                return None
            # 보호 횟수가 남아있으면 시리즈 미생성 (보호 소진 우선)
            if protection_count > 0:
                return None
            prev_tier = TIER_ORDER[old_idx - 1]
            return await self.create_demotion_series(agent_id, old_tier, prev_tier)
