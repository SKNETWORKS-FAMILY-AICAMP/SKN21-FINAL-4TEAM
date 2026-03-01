"""시즌 시스템 서비스 — 시즌 생성, 종료, 결과 조회."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_agent import DebateAgent
from app.models.debate_season import DebateSeason
from app.models.debate_season_result import DebateSeasonResult
from app.services.debate_agent_service import get_tier_from_elo

logger = logging.getLogger(__name__)

# 시즌 종료 보상 크레딧 (1~3위)
SEASON_REWARDS = {1: 500, 2: 300, 3: 200}
RANK_4_10_REWARD = 50


class DebateSeasonService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_season(
        self, season_number: int, title: str, start_at: datetime, end_at: datetime
    ) -> DebateSeason:
        season = DebateSeason(
            season_number=season_number,
            title=title,
            start_at=start_at,
            end_at=end_at,
            status="upcoming",
        )
        self.db.add(season)
        await self.db.commit()
        await self.db.refresh(season)
        return season

    async def get_current_season(self) -> DebateSeason | None:
        res = await self.db.execute(
            select(DebateSeason)
            .where(DebateSeason.status == "active")
            .order_by(DebateSeason.season_number.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def get_season_results(self, season_id: str) -> list[dict]:
        res = await self.db.execute(
            select(DebateSeasonResult, DebateAgent)
            .join(DebateAgent, DebateSeasonResult.agent_id == DebateAgent.id)
            .where(DebateSeasonResult.season_id == season_id)
            .order_by(DebateSeasonResult.rank)
        )
        items = []
        for result, agent in res.all():
            items.append({
                "rank": result.rank,
                "agent_id": str(result.agent_id),
                "agent_name": agent.name,
                "agent_image_url": agent.image_url,
                "final_elo": result.final_elo,
                "final_tier": result.final_tier,
                "wins": result.wins,
                "losses": result.losses,
                "draws": result.draws,
                "reward_credits": result.reward_credits,
            })
        return items

    async def close_season(self, season_id: str) -> None:
        """시즌 종료: results INSERT → 보상 → ELO soft reset → tier 재계산."""
        from app.models.credit_ledger import CreditLedger

        res = await self.db.execute(select(DebateSeason).where(DebateSeason.id == season_id))
        season = res.scalar_one_or_none()
        if season is None:
            raise ValueError("Season not found")
        if season.status != "active":
            raise ValueError("활성 시즌만 종료할 수 있습니다")

        # 활성 에이전트 ELO 내림차순 조회
        agents_res = await self.db.execute(
            select(DebateAgent)
            .where(DebateAgent.is_active == True)  # noqa: E712
            .order_by(DebateAgent.elo_rating.desc())
        )
        agents = list(agents_res.scalars().all())

        for rank, agent in enumerate(agents, start=1):
            reward = SEASON_REWARDS.get(rank, RANK_4_10_REWARD if rank <= 10 else 0)
            result = DebateSeasonResult(
                season_id=season.id,
                agent_id=agent.id,
                final_elo=agent.elo_rating,
                final_tier=get_tier_from_elo(agent.elo_rating),
                wins=agent.wins,
                losses=agent.losses,
                draws=agent.draws,
                rank=rank,
                reward_credits=reward,
            )
            self.db.add(result)

            # 크레딧 보상 (debug 에만 지급 — tx_type은 'admin_grant' 사용)
            if reward > 0:
                ledger = CreditLedger(
                    user_id=agent.owner_id,
                    amount=reward,
                    balance_after=0,  # 실제 잔액 계산 생략 (간단 구현)
                    tx_type="admin_grant",
                    reference_id=str(season.id),
                    description=f"시즌 {season.season_number} {rank}위 보상",
                )
                self.db.add(ledger)

            # ELO soft reset: (elo + 1500) // 2
            new_elo = (agent.elo_rating + 1500) // 2
            agent.elo_rating = new_elo
            agent.tier = get_tier_from_elo(new_elo)

        season.status = "completed"
        await self.db.commit()
        logger.info("Season %s closed, %d agents ranked", season_id, len(agents))
