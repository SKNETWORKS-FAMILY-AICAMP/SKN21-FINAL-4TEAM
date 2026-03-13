"""부전패 예외 및 처리 클래스."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.services.debate.broadcast import publish_event
from app.services.debate.helpers import calculate_elo

logger = logging.getLogger(__name__)


class ForfeitError(Exception):
    """재시도를 모두 소진한 에이전트의 부전패를 알리는 예외."""

    def __init__(self, forfeited_speaker: str) -> None:
        self.forfeited_speaker = forfeited_speaker
        super().__init__(f"Forfeit by {forfeited_speaker}")


class ForfeitHandler:
    """부전패 처리 — 접속 미이행(handle_disconnect) + 재시도 소진(handle_retry_exhaustion)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def settle(
        self,
        match: DebateMatch,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
        elo_result: str,
        result_a: str,
        result_b: str,
        version_a_id: str | None = None,
        version_b_id: str | None = None,
    ) -> tuple[float, float]:
        """ELO + 전적 + 시즌 + 승급전 공통 처리. (new_a_elo, new_b_elo) 반환."""
        from app.services.debate.agent_service import DebateAgentService
        from app.services.debate.promotion_service import DebatePromotionService
        from app.services.debate.season_service import DebateSeasonService

        new_a, new_b = calculate_elo(
            agent_a.elo_rating, agent_b.elo_rating, elo_result,
            score_diff=settings.debate_elo_forfeit_score_diff,
        )

        if match.is_test:
            return new_a, new_b

        agent_service = DebateAgentService(self.db)
        await agent_service.update_elo(str(agent_a.id), new_a, result_a, version_a_id)
        await agent_service.update_elo(str(agent_b.id), new_b, result_b, version_b_id)

        if match.season_id:
            season_svc = DebateSeasonService(self.db)
            stats_a = await season_svc.get_or_create_season_stats(str(agent_a.id), str(match.season_id))
            stats_b = await season_svc.get_or_create_season_stats(str(agent_b.id), str(match.season_id))
            s_new_a, s_new_b = calculate_elo(
                stats_a.elo_rating, stats_b.elo_rating, elo_result,
                score_diff=settings.debate_elo_forfeit_score_diff,
            )
            await season_svc.update_season_stats(str(agent_a.id), str(match.season_id), s_new_a, result_a)
            await season_svc.update_season_stats(str(agent_b.id), str(match.season_id), s_new_b, result_b)

        promo_svc = DebatePromotionService(self.db)
        for agent_obj, res in [(agent_a, result_a), (agent_b, result_b)]:
            active = await promo_svc.get_active_series(str(agent_obj.id))
            if active:
                series_result = await promo_svc.record_match_result(str(active.id), res)
                await publish_event(str(match.id), "series_update", series_result)

        return new_a, new_b

    async def handle_disconnect(
        self,
        match: DebateMatch,
        loser: DebateAgent,
        winner: DebateAgent,
        side: str,
    ) -> None:
        """로컬 에이전트 접속 미이행 부전패 처리 (기존 _handle_forfeit 로직)."""
        match.status = "forfeit"
        match.finished_at = datetime.now(UTC)
        match.winner_id = winner.id
        # flush으로 상태만 세션에 반영 — settle() 완료 후 단일 commit()
        await self.db.flush()

        if side == "agent_a":
            agent_a_obj, agent_b_obj = loser, winner
            elo_result, result_a, result_b = "b_win", "loss", "win"
        else:
            agent_a_obj, agent_b_obj = winner, loser
            elo_result, result_a, result_b = "a_win", "win", "loss"

        version_a_id = str(match.agent_a_version_id) if match.agent_a_version_id else None
        version_b_id = str(match.agent_b_version_id) if match.agent_b_version_id else None

        await self.settle(
            match, agent_a_obj, agent_b_obj, elo_result, result_a, result_b,
            version_a_id, version_b_id,
        )

        await self.db.commit()
        await publish_event(str(match.id), "forfeit", {
            "match_id": str(match.id),
            "reason": f"Agent {loser.name} did not connect in time",
            "winner_id": str(winner.id),
        })
        logger.info("Match %s forfeit: agent %s did not connect", match.id, loser.name)

    async def handle_retry_exhaustion(
        self,
        match: DebateMatch,
        agent_a: DebateAgent,
        agent_b: DebateAgent,
        forfeited_speaker: str,
    ) -> None:
        """재시도 소진 부전패 처리 (기존 _finalize_forfeit 로직). judge() 없이 즉시 종료."""
        from app.services.debate.match_service import DebateMatchService

        if forfeited_speaker == "agent_a":
            forfeit_winner, forfeit_loser = agent_b, agent_a
            score_a, score_b = 0, 100
            elo_result, result_a, result_b = "b_win", "loss", "win"
        else:
            forfeit_winner, forfeit_loser = agent_a, agent_b
            score_a, score_b = 100, 0
            elo_result, result_a, result_b = "a_win", "win", "loss"

        elo_a_before = agent_a.elo_rating
        elo_b_before = agent_b.elo_rating

        match.status = "completed"
        match.finished_at = datetime.now(UTC)
        match.winner_id = forfeit_winner.id
        match.score_a = score_a
        match.score_b = score_b

        version_a_id = str(match.agent_a_version_id) if match.agent_a_version_id else None
        version_b_id = str(match.agent_b_version_id) if match.agent_b_version_id else None

        new_a, new_b = await self.settle(
            match, agent_a, agent_b, elo_result, result_a, result_b,
            version_a_id, version_b_id,
        )

        await self.db.execute(
            update(DebateMatch)
            .where(DebateMatch.id == match.id)
            .values(elo_a_before=elo_a_before, elo_b_before=elo_b_before, elo_a_after=new_a, elo_b_after=new_b)
        )
        await self.db.commit()

        await publish_event(str(match.id), "forfeit", {
            "forfeited_speaker": forfeited_speaker,
            "winner_id": str(forfeit_winner.id),
            "loser_id": str(forfeit_loser.id),
            "reason": "Turn execution failed after all retries",
        })

        await publish_event(str(match.id), "finished", {
            "winner_id": str(forfeit_winner.id),
            "score_a": score_a,
            "score_b": score_b,
            "elo_a_before": elo_a_before,
            "elo_a_after": new_a,
            "elo_b_before": elo_b_before,
            "elo_b_after": new_b,
            # 하위 호환
            "elo_a": new_a,
            "elo_b": new_b,
        })

        match_service = DebateMatchService(self.db)
        await match_service.resolve_predictions(
            str(match.id),
            str(forfeit_winner.id),
            str(match.agent_a_id),
            str(match.agent_b_id),
        )

        logger.info(
            "Match %s ended by forfeit. %s failed after retries, winner: %s",
            match.id, forfeit_loser.name, forfeit_winner.name,
        )
