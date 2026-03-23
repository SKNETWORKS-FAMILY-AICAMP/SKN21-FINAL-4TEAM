"""토론 판정기. LLM 기반 최종 판정(judge)."""

import asyncio
import json
import logging
import re

from app.core.config import settings
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
from app.services.llm.inference_client import InferenceClient

logger = logging.getLogger(__name__)


def _infer_provider(model_id: str) -> str:
    """모델 ID 접두사로 provider를 추론한다.

    Args:
        model_id: LLM 모델 ID 문자열.

    Returns:
        'anthropic' | 'google' | 'runpod' | 'openai'
    """
    if model_id.startswith("claude"):
        return "anthropic"
    if model_id.startswith("gemini"):
        return "google"
    if model_id.startswith(("meta-", "llama", "mistral", "qwen")):
        return "runpod"
    return "openai"


def _platform_api_key(provider: str) -> str:
    """provider에 맞는 플랫폼 API 키를 반환한다.

    Args:
        provider: 'anthropic' | 'google' | 'runpod' | 'openai'.

    Returns:
        해당 플랫폼 API 키 문자열 (미설정이면 빈 문자열).
    """
    if provider == "anthropic":
        return settings.anthropic_api_key or ""
    if provider == "google":
        return settings.google_api_key or ""
    if provider == "runpod":
        return settings.runpod_api_key or ""
    return settings.openai_api_key or ""


# 벌점 키 → 한국어 라벨 (Judge LLM에 영문 파라미터명 노출 방지)
PENALTY_KO_LABELS: dict[str, str] = {
    "repetition": "주장 반복",
    "false_source": "허위 출처",
    "prompt_injection": "프롬프트 인젝션(LLM)",
    "ad_hominem": "인신공격(LLM)",
    "false_claim": "허위 주장(LLM)",
    "straw_man": "허수아비 논증(LLM)",
    "off_topic": "주제 이탈(LLM)",
    "no_web_evidence": "웹 근거 미제시(LLM)",
    "false_citation": "허위 인용(LLM)",
    # debate_formats.py가 llm_ 접두사를 붙여 turn.penalties에 저장하므로 두 형태 모두 등록
    "llm_no_web_evidence": "웹 근거 미제시(LLM)",
    "llm_false_citation": "허위 인용(LLM)",
}

# 채점 기준 (총 100점 만점)
# argumentation: 주장·근거·추론의 일체 (logic + evidence 통합)
# rebuttal: 상대 논거에 대한 직접 대응
# strategy: 쟁점 주도력, 논점 우선순위 설정, 흐름 운영
SCORING_CRITERIA = {
    "argumentation": 40,
    "rebuttal": 35,
    "strategy": 25,
}

def _build_score_format() -> str:
    """SCORING_CRITERIA에서 Judge LLM이 반환할 JSON 출력 스펙을 동적 생성한다.

    scoring criteria 변경 시 자동으로 반영된다.

    Returns:
        Judge LLM 시스템 프롬프트에 삽입할 JSON 형식 문자열.
    """
    fields = ", ".join(f'"{k}": <0-{v}>' for k, v in SCORING_CRITERIA.items())
    return f'{{"agent_a": {{{fields}}}, "agent_b": {{{fields}}}, "reasoning": "<한국어로 작성한 채점 근거>"}}'


# Judge LLM 시스템 프롬프트 — 하위 호환을 위해 보존 (deprecated: 2-stage chain으로 대체됨)
JUDGE_SYSTEM_PROMPT = (
    "당신은 공정한 토론 심판입니다. 전체 토론 트랜스크립트를 읽고 두 에이전트를 독립적으로 채점하세요."
    " 반드시 한국어로 답변하세요.\n\n"
    "채점 기준 (각 측 100점 만점):\n"
    "- argumentation (0-40점): 주장·근거·추론의 일체."
    " 핵심 주장이 명확하고, 이를 뒷받침하는 근거와 추론이 논리적으로 연결되는지 평가한다."
    " 구체적 사례·데이터·수치를 활용할수록 높게 평가한다.\n"
    "- rebuttal (0-35점): 상대 논거에 대한 직접 대응."
    " 상대 주장의 핵심 약점을 정확히 짚고 반박했는지 평가한다."
    " 첫 발언자는 반박 대상이 없으므로, 선제 프레이밍의 질(핵심 쟁점 선점, 논거 배치)로 평가한다.\n"
    "- strategy (0-25점): 쟁점 주도력과 흐름 운영."
    " 논점 우선순위를 명확히 설정하고, 유리한 쟁점에 집중하며 불리한 쟁점을 효과적으로 처리했는지 평가한다.\n\n"
    "채점 원칙:\n"
    "1. 각 에이전트를 상대와 비교하기 전에 절대 기준으로 먼저 독립 평가하라.\n"
    "2. 발언 길이가 아닌 논증 밀도를 평가하라. 핵심 논거의 수와 근거의 구체성이 기준이다.\n"
    "3. 에이전트의 찬성/반대 입장이나 토론 주제에 대한 개인 견해와 무관하게,"
    " 제시된 논증의 내적 일관성만으로 채점하라.\n"
    "4. 발언 순서(찬성측이 먼저 말함)로 인한 편향을 배제하라.\n"
    "5. 두 에이전트가 실질적으로 동등한 수준이면 동점이 정직한 결과다.\n"
    "6. [TIMEOUT] 또는 [ERROR]가 포함된 응답은 해당 에이전트의 각 항목에 0~5점을 부여하라.\n"
    "7. reasoning에는 각 항목별 핵심 판단 근거와 승패를 가른 결정적 차이를 포함하라.\n\n"
    "⚠️ 반드시 아래 JSON 형식만 출력하세요. 설명, 마크다운 코드블록, 추가 텍스트 절대 금지:\n"
    + _build_score_format()
)

# Stage 1: 서술형 분석 프롬프트 — 숫자/점수 언급 금지로 앵커링 편향 차단
JUDGE_ANALYSIS_PROMPT = """당신은 AI 토론 전문 분석가입니다. 아래 토론 전문을 읽고 서술형으로 분석하세요.
숫자나 점수를 절대 언급하지 마세요. 오직 논거, 반박, 전략의 강점과 약점을 서술하세요.

분석 포인트:
1. 각 에이전트의 논거 명확성과 근거 타당성
2. 상대 주장에 대한 반박의 정확성
3. 전체 토론 흐름에서의 전략적 접근"""

# Stage 2: 분석 결과 기반 채점 프롬프트
JUDGE_SCORING_PROMPT = (
    "당신은 AI 토론 채점관입니다. 제공된 분석 결과를 바탕으로 채점하세요.\n\n"
    "채점 기준:\n"
    "- argumentation (최대 40점): 논거의 명확성, 근거의 타당성\n"
    "- rebuttal (최대 35점): 상대 주장 반박의 정확성, 논리적 일관성\n"
    "- strategy (최대 25점): 토론 흐름 파악, 전략적 전개\n\n"
    "⚠️ 반드시 아래 JSON 형식만 출력하세요. 설명, 마크다운 코드블록, 추가 텍스트 절대 금지:\n"
    + _build_score_format()
)


class DebateJudge:
    """LLM 2-stage 방식으로 토론 전체를 판정하는 심판 클래스.

    Stage 1: 서술형 분석 (점수 언급 금지 — 앵커링 편향 차단)
    Stage 2: 분석 결과 기반 JSON 채점
    """

    def __init__(
        self,
        client: "InferenceClient | None" = None,
        judge_model_override: str | None = None,
    ) -> None:
        self._owns_client = client is None
        self.client = client if client is not None else InferenceClient()
        self.judge_model_override = judge_model_override

    async def aclose(self) -> None:
        """소유한 InferenceClient를 닫는다. 외부 주입 클라이언트는 닫지 않는다."""
        if self._owns_client:
            await self.client.aclose()

    async def judge(
        self,
        match: DebateMatch,
        turns: list[DebateTurnLog],
        topic: DebateTopic,
        agent_a_name: str = "에이전트 A",
        agent_b_name: str = "에이전트 B",
        trace_id: str | None = None,
        orchestration_mode: str | None = None,
    ) -> dict:
        """LLM으로 토론 판정. 스코어카드 dict 반환."""
        model_id = self.judge_model_override or settings.debate_judge_model or settings.debate_orchestrator_model
        if not model_id:
            raise ValueError(
                "judge 모델 미설정: DEBATE_JUDGE_MODEL 또는 DEBATE_ORCHESTRATOR_MODEL "
                "환경 변수를 설정하세요. 모델 미설정 시 silent draw가 발생해 ELO 변동이 누락됩니다."
            )
        return await self._judge_with_model(
            match,
            turns,
            topic,
            agent_a_name,
            agent_b_name,
            model_id=model_id,
            trace_id=trace_id,
            orchestration_mode=orchestration_mode,
        )

    async def _judge_with_model(
        self,
        match: DebateMatch,
        turns: list[DebateTurnLog],
        topic: DebateTopic,
        agent_a_name: str,
        agent_b_name: str,
        model_id: str,
        trace_id: str | None = None,
        orchestration_mode: str | None = None,
    ) -> dict:
        """지정된 model_id로 2-stage LLM 판정을 수행하고 스코어카드·점수·승패를 반환한다.

        Stage 1: 서술형 분석 (온도 0.3, 점수 언급 금지 — 앵커링 편향 차단)
        Stage 2: 분석 결과 기반 채점 (JSON 출력)
        """
        debate_log = self._format_debate_log(turns, topic, agent_a_name, agent_b_name)
        provider = _infer_provider(model_id)
        api_key = _platform_api_key(provider)

        judge_input_tokens = 0
        judge_output_tokens = 0
        raw_content = ""
        fallback_reason: str | None = None
        try:
            # stage1+stage2 합산 시간을 단일 타임아웃으로 제한
            async with asyncio.timeout(settings.debate_judge_timeout_seconds):
                # Stage 1: 서술형 분석 — 숫자/점수 없이 논거·반박·전략 강약점 서술
                analysis_messages = [
                    {"role": "system", "content": JUDGE_ANALYSIS_PROMPT},
                    {"role": "user", "content": debate_log},
                ]
                analysis_result = await self.client.generate_byok(
                    provider=provider,
                    model_id=model_id,
                    api_key=api_key,
                    messages=analysis_messages,
                    max_tokens=settings.debate_judge_max_tokens,
                    temperature=0.3,
                )
                judge_input_tokens += analysis_result.get("input_tokens", 0)
                judge_output_tokens += analysis_result.get("output_tokens", 0)
                analysis_content = analysis_result.get("content", "")
                if not analysis_content:
                    logger.warning("Judge Stage 1 returned empty content for match %s", match.id)

                # Stage 2: 분석 결과 기반 채점 — JSON 출력
                # debate_log 재전송 생략: Stage 1이 이미 전체 대화를 분석했으므로 분석 결과만 전달
                scoring_messages = [
                    {"role": "system", "content": JUDGE_SCORING_PROMPT},
                    {"role": "user", "content": f"[분석 결과]\n{analysis_content}"},
                ]
                scoring_result = await self.client.generate_byok(
                    provider=provider,
                    model_id=model_id,
                    api_key=api_key,
                    messages=scoring_messages,
                    max_tokens=settings.debate_judge_max_tokens,
                    temperature=settings.debate_judge_temperature,
                )
            judge_input_tokens += scoring_result.get("input_tokens", 0)
            judge_output_tokens += scoring_result.get("output_tokens", 0)
            raw_content = scoring_result.get("content", "")
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
            logger.error(
                "Judge response parse error | trace_id=%s mode=%s err=%s raw=%.500s",
                trace_id,
                orchestration_mode,
                exc,
                raw_content,
            )
            # 파싱 실패 시 각 항목 최대값의 절반으로 균등 점수 (무승부 폴백)
            half_scores = {k: v // 2 for k, v in SCORING_CRITERIA.items()}
            scorecard = {
                "agent_a": half_scores,
                "agent_b": half_scores,
                "reasoning": "심판 채점 오류로 인해 동점 처리되었습니다.",
            }
            fallback_reason = "parse_error"
        except Exception as exc:
            # httpx.HTTPError, ConnectionError, asyncio.TimeoutError 등 네트워크 오류
            # 파싱 오류와 동일하게 무승부 폴백 처리 — 완료된 매치를 error로 전환하지 않음
            logger.error(
                "Judge request error | trace_id=%s mode=%s err=%s",
                trace_id,
                orchestration_mode,
                exc,
                exc_info=True,
            )
            half_scores = {k: v // 2 for k, v in SCORING_CRITERIA.items()}
            scorecard = {
                "agent_a": half_scores,
                "agent_b": half_scores,
                "reasoning": "판정 요청 오류로 인해 동점 처리되었습니다.",
            }
            fallback_reason = "request_error"
        # Judge 반환 점수를 SCORING_CRITERIA 범위로 클램핑 — LLM 오버슈팅 방어
        for key, max_val in SCORING_CRITERIA.items():
            scorecard["agent_a"][key] = max(0, min(scorecard["agent_a"].get(key, 0), max_val))
            scorecard["agent_b"][key] = max(0, min(scorecard["agent_b"].get(key, 0), max_val))

        score_a = sum(scorecard["agent_a"].values())
        score_b = sum(scorecard["agent_b"].values())

        penalty_a = match.penalty_a or 0
        penalty_b = match.penalty_b or 0
        final_a = max(0, score_a - penalty_a)
        final_b = max(0, score_b - penalty_b)

        # 점수차 >= debate_draw_threshold → 승/패, 미만 → 무승부
        diff = abs(final_a - final_b)
        winner_id = (match.agent_a_id if final_a > final_b else match.agent_b_id) if diff >= settings.debate_draw_threshold else None

        return {
            "scorecard": scorecard,
            "score_a": final_a,
            "score_b": final_b,
            "penalty_a": penalty_a,
            "penalty_b": penalty_b,
            "winner_id": winner_id,
            "input_tokens": judge_input_tokens,
            "output_tokens": judge_output_tokens,
            "model_id": model_id,
            "fallback_reason": fallback_reason,
            # fallback 판정(parse_error/request_error)은 신뢰도가 낮으므로 ELO 변동 억제 권고
            "elo_suppressed": fallback_reason is not None,
        }

    def _format_debate_log(
        self,
        turns: list[DebateTurnLog],
        topic: DebateTopic,
        agent_a_name: str = "에이전트 A",
        agent_b_name: str = "에이전트 B",
    ) -> str:
        """턴 로그를 Judge LLM 입력용 텍스트로 포맷한다.

        벌점 정보와 위반 횟수 요약을 포함하여 Judge가 공정한 채점을 할 수 있도록 한다.

        Args:
            turns: DebateTurnLog 목록.
            topic: 토론 주제.
            agent_a_name: 에이전트 A 이름.
            agent_b_name: 에이전트 B 이름.

        Returns:
            Judge LLM에 전달할 포맷된 토론 전문 문자열.
        """
        lines = [f"토론 주제: {topic.title}", f"설명: {topic.description or '없음'}", ""]

        violation_counts: dict[str, dict[str, int]] = {"agent_a": {}, "agent_b": {}}

        for turn in turns:
            label = f"{agent_a_name} (찬성)" if turn.speaker == "agent_a" else f"{agent_b_name} (반대)"
            penalty_key = turn.speaker
            lines.append(f"[턴 {turn.turn_number}] {label} ({turn.action}):")
            lines.append(f"주장: {turn.claim}")
            if turn.evidence:
                lines.append(f"근거: {turn.evidence}")
            raw = turn.raw_response or {}
            if raw.get("tool_used"):
                lines.append(f"도구 사용: {raw['tool_used']}")
            if turn.penalty_total > 0:
                ko_items = ", ".join(
                    f"{PENALTY_KO_LABELS.get(k, k)} {v}점"
                    for k, v in (turn.penalties or {}).items()
                    if v
                )
                lines.append(f"벌점: -{turn.penalty_total}점 ({ko_items})")
                for violation_key in (turn.penalties or {}):
                    counts = violation_counts.get(penalty_key, {})
                    counts[violation_key] = counts.get(violation_key, 0) + 1
                    violation_counts[penalty_key] = counts
            lines.append("")

        lines.append("[벌점 요약]")
        lines.append(self._format_violation_summary(agent_a_name, violation_counts.get("agent_a", {})))
        lines.append(self._format_violation_summary(agent_b_name, violation_counts.get("agent_b", {})))

        return "\n".join(lines)

    def _format_violation_summary(self, name: str, violations: dict[str, int]) -> str:
        """에이전트 이름과 위반 횟수 dict를 받아 Judge용 요약 문자열 반환."""
        if not violations:
            return f"{name}: 위반 없음"
        items = ", ".join(
            f"{PENALTY_KO_LABELS.get(k, k)} {v}회"
            for k, v in violations.items()
            if v
        )
        return f"{name}: {items}"
