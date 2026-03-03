"""토론 요약 리포트 생성 서비스."""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_turn_log import DebateTurnLog

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """당신은 AI 토론 분석 전문가입니다. 토론 로그를 분석하여 JSON 형식으로 요약을 생성하세요.

반드시 다음 JSON 형식으로만 응답하세요:
{
  "key_arguments": ["핵심 논거 1", "핵심 논거 2", "핵심 논거 3"],
  "winning_points": ["승부 포인트 1", "승부 포인트 2"],
  "rule_violations": ["위반 사항 1"],
  "overall_summary": "전체 토론 요약 (3-4문장)"
}"""


def _format_debate_log(turns: list, agent_a_name: str, agent_b_name: str) -> str:
    """턴 로그를 텍스트로 포맷."""
    name_map = {"agent_a": agent_a_name, "agent_b": agent_b_name}
    lines = []
    for t in turns:
        speaker_name = name_map.get(t.speaker, t.speaker)
        lines.append(f"[{speaker_name} 턴 {t.turn_number}] {t.action}: {t.claim}")
        if t.evidence:
            lines.append(f"  근거: {t.evidence}")
        if t.penalty_total > 0:
            lines.append(f"  벌점: {t.penalty_total}")
    return "\n".join(lines)


class DebateSummaryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_summary(self, match_id: str) -> None:
        """매치 완료 후 비동기 호출. 이미 summary_report가 있으면 스킵."""
        res = await self.db.execute(select(DebateMatch).where(DebateMatch.id == match_id))
        match = res.scalar_one_or_none()
        if match is None or match.status != "completed":
            return
        if match.summary_report is not None:
            return  # 중복 방지

        # 에이전트 이름 조회
        agents_res = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id.in_([match.agent_a_id, match.agent_b_id]))
        )
        agents = {str(a.id): a.name for a in agents_res.scalars().all()}
        agent_a_name = agents.get(str(match.agent_a_id), "Agent A")
        agent_b_name = agents.get(str(match.agent_b_id), "Agent B")

        # 턴 로그 조회
        turns_res = await self.db.execute(
            select(DebateTurnLog)
            .where(DebateTurnLog.match_id == match.id)
            .order_by(DebateTurnLog.turn_number)
        )
        turns = list(turns_res.scalars().all())
        if not turns:
            return

        log_text = _format_debate_log(turns, agent_a_name, agent_b_name)

        try:
            import httpx

            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": settings.debate_summary_model,
                "messages": [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"참가자: {agent_a_name} vs {agent_b_name}\n\n"
                            f"다음 토론 로그를 분석하세요:\n\n{log_text[:4000]}"
                        ),
                    },
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 800,
                "temperature": 0.3,
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            input_tokens = data.get("usage", {}).get("prompt_tokens", 0)
            output_tokens = data.get("usage", {}).get("completion_tokens", 0)

            summary_report = {
                "key_arguments": parsed.get("key_arguments", []),
                "winning_points": parsed.get("winning_points", []),
                "rule_violations": parsed.get("rule_violations", []),
                "overall_summary": parsed.get("overall_summary", ""),
                "generated_at": datetime.now(UTC).isoformat(),
                "model_used": settings.debate_summary_model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

            await self.db.execute(
                sa_update(DebateMatch)
                .where(DebateMatch.id == match.id)
                .values(summary_report=summary_report)
            )
            await self.db.commit()
            logger.info("Summary generated for match %s", match_id)

        except Exception as exc:
            logger.warning("Summary generation failed for match %s: %s", match_id, exc)


async def generate_summary_task(match_id: str) -> None:
    """백그라운드 태스크용 — 독립 DB 세션 생성."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        service = DebateSummaryService(db)
        await service.generate_summary(match_id)
    await engine.dispose()
