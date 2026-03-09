"""시즌 시스템 서비스 — 시즌 생성, 종료, 결과 조회."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate_agent import DebateAgent, DebateAgentSeasonStats
from app.models.debate_season import DebateSeason, DebateSeasonResult
from app.models.user import User
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

    async def get_active_season(self) -> DebateSeason | None:
        """status='active'인 시즌만 반환 (upcoming 제외)."""
        res = await self.db.execute(
            select(DebateSeason)
            .where(DebateSeason.status == "active")
            .order_by(DebateSeason.season_number.desc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def get_current_season(self) -> DebateSeason | None:
        # active 우선, 없으면 가장 최신 upcoming 반환
        for target_status in ("active", "upcoming"):
            res = await self.db.execute(
                select(DebateSeason)
                .where(DebateSeason.status == target_status)
                .order_by(DebateSeason.season_number.desc())
                .limit(1)
            )
            season = res.scalar_one_or_none()
            if season:
                return season
        return None

    async def get_or_create_season_stats(
        self, agent_id: str, season_id: str
    ) -> DebateAgentSeasonStats:
        """에이전트의 시즌 통계 행을 가져오거나 생성 (ELO 1500, Iron 시작)."""
        res = await self.db.execute(
            select(DebateAgentSeasonStats).where(
                DebateAgentSeasonStats.agent_id == agent_id,
                DebateAgentSeasonStats.season_id == season_id,
            )
        )
        stats = res.scalar_one_or_none()
        if stats is None:
            stats = DebateAgentSeasonStats(
                agent_id=agent_id,
                season_id=season_id,
                elo_rating=1500,
                tier="Iron",
            )
            self.db.add(stats)
            await self.db.flush()
        return stats

    async def update_season_stats(
        self, agent_id: str, season_id: str, new_elo: int, result_type: str
    ) -> None:
        """시즌 ELO/전적 갱신 + tier 재계산.

        result_type: 'win' | 'loss' | 'draw'
        """
        stats = await self.get_or_create_season_stats(agent_id, season_id)
        stats.elo_rating = new_elo
        stats.tier = get_tier_from_elo(new_elo)
        if result_type == "win":
            stats.wins += 1
        elif result_type == "loss":
            stats.losses += 1
        else:
            stats.draws += 1

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

        res = await self.db.execute(select(DebateSeason).where(DebateSeason.id == season_id))
        season = res.scalar_one_or_none()
        if season is None:
            raise ValueError("Season not found")
        if season.status != "active":
            raise ValueError("활성 시즌만 종료할 수 있습니다")

        # 해당 시즌 참가 에이전트 시즌 ELO 내림차순 조회 (매치 0회 에이전트 제외)
        stats_res = await self.db.execute(
            select(DebateAgentSeasonStats, DebateAgent)
            .join(DebateAgent, DebateAgentSeasonStats.agent_id == DebateAgent.id)
            .where(
                DebateAgentSeasonStats.season_id == season.id,
                DebateAgent.is_active == True,  # noqa: E712
            )
            .order_by(DebateAgentSeasonStats.elo_rating.desc())
        )
        season_stats_rows = stats_res.all()

        for rank, (stats, agent) in enumerate(season_stats_rows, start=1):
            reward = SEASON_REWARDS.get(rank, RANK_4_10_REWARD if rank <= 10 else 0)
            result = DebateSeasonResult(
                season_id=season.id,
                agent_id=agent.id,
                # 시즌 전적/ELO 기준으로 결과 저장
                final_elo=stats.elo_rating,
                final_tier=stats.tier,
                wins=stats.wins,
                losses=stats.losses,
                draws=stats.draws,
                rank=rank,
                reward_credits=reward,
            )
            self.db.add(result)

            # 보상 크레딧 실제 지급 — 에이전트 소유자 credit_balance에 직접 반영
            if reward > 0:
                user_res = await self.db.execute(
                    select(User).where(User.id == agent.owner_id)
                )
                owner = user_res.scalar_one_or_none()
                if owner is not None:
                    owner.credit_balance += reward

            # 누적 ELO soft reset: (누적 elo + 1500) // 2
            new_elo = (agent.elo_rating + 1500) // 2
            agent.elo_rating = new_elo
            agent.tier = get_tier_from_elo(new_elo)

        season.status = "completed"
        await self.db.commit()
        logger.info("Season %s closed, %d agents ranked", season_id, len(season_stats_rows))
