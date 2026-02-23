"""오케스트레이터. LLM 기반 판정 + ELO 계산."""

import json
import logging
import math

from app.core.config import settings
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)

# 채점 기준 (총 100점 만점)
SCORING_CRITERIA = {
    "logic": 30,       # 논리성
    "evidence": 25,    # 근거 활용
    "rebuttal": 25,    # 반박력
    "relevance": 20,   # 주제 적합성
}

JUDGE_SYSTEM_PROMPT = """You are an impartial debate judge. Evaluate both sides of the debate and provide scores.

Scoring criteria (total 100 points per side):
- logic (30): Logical consistency, valid reasoning chains
- evidence (25): Use of evidence, data, and citations
- rebuttal (25): Quality of counter-arguments and responses to opponent
- relevance (20): Staying on topic, addressing the core question

Apply penalty deductions that have already been assessed during the debate.

Respond with ONLY valid JSON:
{
  "agent_a": {"logic": <0-30>, "evidence": <0-25>, "rebuttal": <0-25>, "relevance": <0-20>},
  "agent_b": {"logic": <0-30>, "evidence": <0-25>, "rebuttal": <0-25>, "relevance": <0-20>},
  "reasoning": "<brief explanation of scoring>"
}"""


class DebateOrchestrator:
    def __init__(self):
        self.client = InferenceClient()

    async def judge(
        self, match: DebateMatch, turns: list[DebateTurnLog], topic: DebateTopic
    ) -> dict:
        """LLM으로 토론 판정. 스코어카드 dict 반환."""
        debate_log = self._format_debate_log(turns, topic)

        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": debate_log},
        ]

        try:
            # 플랫폼 키로 오케스트레이터 모델 호출
            result = await self.client._call_openai_byok(
                model_id=settings.debate_orchestrator_model,
                api_key=settings.openai_api_key,
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
            )
            scorecard = json.loads(result["content"])
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Judge response parse error: %s", exc)
            # 파싱 실패 시 균등 점수
            scorecard = {
                "agent_a": {"logic": 15, "evidence": 12, "rebuttal": 12, "relevance": 10},
                "agent_b": {"logic": 15, "evidence": 12, "rebuttal": 12, "relevance": 10},
                "reasoning": "Judge scoring failed, equal scores assigned.",
            }

        # 기본 점수 합산
        score_a = sum(scorecard.get("agent_a", {}).values()) if isinstance(scorecard.get("agent_a"), dict) else 0
        score_b = sum(scorecard.get("agent_b", {}).values()) if isinstance(scorecard.get("agent_b"), dict) else 0

        # 벌점 차감
        penalty_a = match.penalty_a
        penalty_b = match.penalty_b
        final_a = max(0, score_a - penalty_a)
        final_b = max(0, score_b - penalty_b)

        # 승패 판정: 점수차 >= 10 → 승/패, < 10 → 무승부
        diff = abs(final_a - final_b)
        if diff >= 10:
            winner_id = match.agent_a_id if final_a > final_b else match.agent_b_id
        else:
            winner_id = None

        return {
            "scorecard": scorecard,
            "score_a": final_a,
            "score_b": final_b,
            "penalty_a": penalty_a,
            "penalty_b": penalty_b,
            "winner_id": winner_id,
        }

    def _format_debate_log(self, turns: list[DebateTurnLog], topic: DebateTopic) -> str:
        lines = [f"Topic: {topic.title}", f"Description: {topic.description or 'N/A'}", ""]
        for turn in turns:
            label = "Agent A" if turn.speaker == "agent_a" else "Agent B"
            lines.append(f"[Turn {turn.turn_number}] {label} ({turn.action}):")
            lines.append(f"Claim: {turn.claim}")
            if turn.evidence:
                lines.append(f"Evidence: {turn.evidence}")
            if turn.penalty_total > 0:
                lines.append(f"Penalties: -{turn.penalty_total} ({json.dumps(turn.penalties)})")
            lines.append("")
        return "\n".join(lines)


def calculate_elo(rating_a: int, rating_b: int, result: str, k: int | None = None) -> tuple[int, int]:
    """표준 ELO 공식. result: 'a_win' | 'b_win' | 'draw'. (new_a, new_b) 반환."""
    if k is None:
        k = settings.debate_elo_k_factor

    expected_a = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1.0 - expected_a

    if result == "a_win":
        actual_a, actual_b = 1.0, 0.0
    elif result == "b_win":
        actual_a, actual_b = 0.0, 1.0
    else:
        actual_a, actual_b = 0.5, 0.5

    new_a = round(rating_a + k * (actual_a - expected_a))
    new_b = round(rating_b + k * (actual_b - expected_b))
    return new_a, new_b
