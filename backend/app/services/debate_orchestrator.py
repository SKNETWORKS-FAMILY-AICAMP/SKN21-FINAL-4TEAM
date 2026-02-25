"""오케스트레이터. LLM 기반 판정 + ELO 계산."""

import json
import logging
import re

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

JUDGE_SYSTEM_PROMPT = (
    "당신은 공정하지만 명확한 토론 심판입니다. 토론 양측을 엄격하게 평가하고 점수를 부여하세요."
    " 반드시 한국어로 답변하세요.\n\n"
    "채점 기준 (각 측 100점 만점):\n"
    "- logic (0-30점): 논리적 일관성, 타당한 추론 체계\n"
    "- evidence (0-25점): 근거, 데이터, 인용 활용도\n"
    "- rebuttal (0-25점): 반박 논리의 질, 상대 주장에 대한 대응 수준\n"
    "- relevance (0-20점): 주제 적합성, 핵심 쟁점 집중도\n\n"
    "⚠️ 채점 원칙:\n"
    "1. 각 항목에서 더 잘한 측에 더 높은 점수를 부여하세요. 동일 점수는 최소화하세요.\n"
    "2. 한 쪽이 더 나은 논거·근거·반박을 보였다면 전체 합산 점수에서 최소 6점 차이를 내세요.\n"
    "3. 무승부는 두 에이전트의 수행이 모든 항목에서 정말로 구분하기 어려울 때만 부여하세요.\n"
    "4. [TIMEOUT] 또는 [ERROR]가 포함된 응답은 해당 에이전트의 각 항목에 0~5점을 부여하세요.\n\n"
    "⚠️ 반드시 아래 JSON 형식만 출력하세요. 설명, 마크다운 코드블록, 추가 텍스트 절대 금지:\n"
    '{{"agent_a": {{"logic": <0-30>, "evidence": <0-25>, "rebuttal": <0-25>, "relevance": <0-20>}},'
    ' "agent_b": {{"logic": <0-30>, "evidence": <0-25>, "rebuttal": <0-25>, "relevance": <0-20>}},'
    ' "reasoning": "<한국어로 작성한 채점 근거>"}}'
)


class DebateOrchestrator:
    def __init__(self):
        self.client = InferenceClient()

    async def judge(
        self,
        match: DebateMatch,
        turns: list[DebateTurnLog],
        topic: DebateTopic,
        agent_a_name: str = "에이전트 A",
        agent_b_name: str = "에이전트 B",
    ) -> dict:
        """LLM으로 토론 판정. 스코어카드 dict 반환."""
        debate_log = self._format_debate_log(turns, topic, agent_a_name, agent_b_name)

        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": debate_log},
        ]

        raw_content = ""
        try:
            # 플랫폼 키로 오케스트레이터 모델 호출
            result = await self.client._call_openai_byok(
                model_id=settings.debate_orchestrator_model,
                api_key=settings.openai_api_key,
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
            )
            raw_content = result.get("content", "")
            content = raw_content.strip()
            # LLM이 마크다운 코드블록으로 감싸 반환하는 경우 제거
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
                content = re.sub(r"\s*```\s*$", "", content.strip())
            # JSON 오브젝트만 추출 (텍스트 앞뒤 잡동사니 제거)
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                content = json_match.group(0)
            scorecard = json.loads(content)
            if not isinstance(scorecard.get("agent_a"), dict) or not isinstance(scorecard.get("agent_b"), dict):
                raise ValueError("Invalid scorecard structure")
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.error("Judge response parse error: %s | raw: %.500s", exc, raw_content)
            # 파싱 실패 시 균등 점수 (무승부 폴백)
            scorecard = {
                "agent_a": {"logic": 15, "evidence": 12, "rebuttal": 12, "relevance": 10},
                "agent_b": {"logic": 15, "evidence": 12, "rebuttal": 12, "relevance": 10},
                "reasoning": "심판 채점 오류로 인해 동점 처리되었습니다.",
            }

        # 기본 점수 합산
        score_a = sum(scorecard.get("agent_a", {}).values()) if isinstance(scorecard.get("agent_a"), dict) else 0
        score_b = sum(scorecard.get("agent_b", {}).values()) if isinstance(scorecard.get("agent_b"), dict) else 0

        # 벌점 차감
        penalty_a = match.penalty_a
        penalty_b = match.penalty_b
        final_a = max(0, score_a - penalty_a)
        final_b = max(0, score_b - penalty_b)

        # 승패 판정: 점수차 >= 5 → 승/패, < 5 → 무승부
        diff = abs(final_a - final_b)
        winner_id = (match.agent_a_id if final_a > final_b else match.agent_b_id) if diff >= 5 else None

        return {
            "scorecard": scorecard,
            "score_a": final_a,
            "score_b": final_b,
            "penalty_a": penalty_a,
            "penalty_b": penalty_b,
            "winner_id": winner_id,
        }

    def _format_debate_log(
        self,
        turns: list[DebateTurnLog],
        topic: DebateTopic,
        agent_a_name: str = "에이전트 A",
        agent_b_name: str = "에이전트 B",
    ) -> str:
        lines = [f"토론 주제: {topic.title}", f"설명: {topic.description or '없음'}", ""]
        for turn in turns:
            label = f"{agent_a_name} (찬성)" if turn.speaker == "agent_a" else f"{agent_b_name} (반대)"
            lines.append(f"[턴 {turn.turn_number}] {label} ({turn.action}):")
            lines.append(f"주장: {turn.claim}")
            if turn.evidence:
                lines.append(f"근거: {turn.evidence}")
            if turn.penalty_total > 0:
                lines.append(f"벌점: -{turn.penalty_total} ({json.dumps(turn.penalties, ensure_ascii=False)})")
            lines.append("")
        return "\n".join(lines)


def calculate_elo(rating_a: int, rating_b: int, result: str, k: int | None = None) -> tuple[int, int]:
    """비대칭 ELO 공식. 승리 시 k_win, 패배 시 k_loss 적용. result: 'a_win' | 'b_win' | 'draw'. (new_a, new_b) 반환."""
    k_win = settings.debate_elo_k_win
    k_loss = settings.debate_elo_k_loss

    expected_a = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1.0 - expected_a

    if result == "a_win":
        actual_a, actual_b = 1.0, 0.0
        new_a = round(rating_a + k_win * (actual_a - expected_a))
        new_b = round(rating_b + k_loss * (actual_b - expected_b))
    elif result == "b_win":
        actual_a, actual_b = 0.0, 1.0
        new_a = round(rating_a + k_loss * (actual_a - expected_a))
        new_b = round(rating_b + k_win * (actual_b - expected_b))
    else:
        # draw — 양측 동일한 중간값 K 적용
        k_draw = (k_win + k_loss) // 2
        new_a = round(rating_a + k_draw * (0.5 - expected_a))
        new_b = round(rating_b + k_draw * (0.5 - expected_b))
    return new_a, new_b
