"""토론 엔진 순수 헬퍼 함수. 외부 I/O 없는 유틸리티 모음."""

import contextlib
import json
import logging
import re

from app.core.config import settings
from app.core.encryption import decrypt_api_key
from app.models.debate_agent import DebateAgent
from app.models.debate_topic import DebateTopic

logger = logging.getLogger(__name__)


# 에이전트 LLM에 주입하는 응답 형식 지시문 — _execute_turn() 내 user 메시지 끝에 추가됨
# 에이전트가 임의 텍스트 대신 구조화 JSON을 반환하도록 강제.
# validate_response_schema()가 이 형식을 검증하며, 불일치 시 파싱 실패로 처리.
RESPONSE_SCHEMA_INSTRUCTION = """⚠️ 중요: 반드시 한국어로만 답변하세요. 영어 사용 금지.

다음 형식의 JSON만 응답하세요 (다른 텍스트 없이):
{
  "action": "argue" | "rebut" | "concede" | "question" | "summarize",
  "claim": "<한국어로 작성한 주요 주장>",
  "evidence": "<한국어로 작성한 근거/데이터/인용>" | null,
  "tool_used": null,
  "tool_result": null
}

action 선택 기준 (상황에 맞는 전략을 자유롭게 선택하세요):
- "argue"  : 새로운 주장이나 추가 근거를 제시할 때
- "rebut"  : 상대방의 구체적 논거·데이터를 직접 논리적으로 반박할 때
- "question": 상대방 주장의 전제·근거에 의문을 제기하거나 약점을 파고들 때
- "concede": 상대방 논거 중 타당한 부분을 인정하되 자신의 핵심 입장은 유지할 때
- "summarize": 논점을 정리하거나 마무리 단계에서 핵심을 압축할 때"""

# 코드 기반 벌점 — LLM 검토 이전에 즉시 적용 (debate_engine 단독 처리)
# LLM 기반 벌점은 debate_orchestrator.LLM_VIOLATION_PENALTIES 참조
PENALTY_REPETITION = 3         # detect_repetition()이 단어 중복 70%+ 감지 시 부여
PENALTY_FALSE_SOURCE = 7       # tool_result를 실제 도구 호출 없이 허위로 반환한 경우


def detect_repetition(new_claim: str, previous_claims: list[str], threshold: float = 0.7) -> bool:
    """단순 단어 집합 유사도로 동어반복 감지.

    overlap / max(len_new, len_prev) >= threshold(0.7)이면 반복 판정.
    공백 분리 단어 기준이므로 어휘 수준 비교만 수행 (의미적 유사도 미포함).
    허용 오탐율을 고려해 threshold를 0.7로 설정 — 0.6이면 정상 발언도 자주 차단됨.
    """
    # 비교 대상이 없으면 반복으로 볼 수 없음 — 첫 번째 발언은 항상 통과
    if not previous_claims:
        return False
    new_words = set(new_claim.lower().split())
    # 빈 발언은 단어가 없으므로 유사도 계산 불가 — 반복 판정 제외
    if not new_words:
        return False
    # 모든 이전 발언과 비교해 하나라도 threshold를 초과하면 즉시 반복 판정
    for prev in previous_claims:
        prev_words = set(prev.lower().split())
        # 이전 발언이 비어있으면 분모가 0이 되므로 스킵
        if not prev_words:
            continue
        overlap = len(new_words & prev_words)
        similarity = overlap / max(len(new_words), len(prev_words))
        if similarity >= threshold:
            return True
    return False


def validate_response_schema(response_text: str) -> dict | None:
    """응답 JSON 파싱 및 스키마 검증. 유효하면 dict, 아니면 None."""
    text = response_text.strip()

    # 1단계: 마크다운 코드블록 제거
    if "```" in text:
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```", "", text).strip()

    # 2단계: JSON 파싱 시도 (전체 텍스트가 JSON인 경우)
    data = None
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        data = json.loads(text)

    # 3단계: 텍스트 중간에 JSON이 포함된 경우 추출
    if data is None:
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            with contextlib.suppress(json.JSONDecodeError, ValueError):
                data = json.loads(json_match.group(0))

    if data is None:
        return None

    required_keys = {"action", "claim"}
    # action과 claim은 에이전트 발언의 필수 필드 — 하나라도 없으면 턴 처리 불가
    if not required_keys.issubset(data.keys()):
        return None

    valid_actions = {"argue", "rebut", "concede", "question", "summarize"}
    # RESPONSE_SCHEMA_INSTRUCTION에 정의된 5개 액션만 허용 — 임의 값 거부
    if data.get("action") not in valid_actions:
        return None

    # claim이 비어있으면 실패
    if not str(data.get("claim", "")).strip():
        return None

    # tool_used, tool_result, evidence 기본값 보장
    data.setdefault("evidence", None)
    data.setdefault("tool_used", None)
    data.setdefault("tool_result", None)

    return data


def _resolve_api_key(agent: DebateAgent, force_platform: bool = False) -> str:
    """에이전트 API 키 반환. 우선순위: BYOK 복호화 → 플랫폼 환경변수 → 빈 문자열.

    force_platform=True이면 BYOK를 무시하고 플랫폼 환경변수 키를 직접 사용.
    테스트 매치(is_test=True)에서 호출 시 항상 True로 전달됨.
    """
    if agent.provider == "local":
        return ""

    # 플랫폼 강제 모드 (테스트 매치 또는 platform credits 에이전트)
    if force_platform or getattr(agent, "use_platform_credits", False):
        match agent.provider:
            case "openai":
                return settings.openai_api_key or ""
            case "anthropic":
                return settings.anthropic_api_key or ""
            case "google":
                return settings.google_api_key or ""
            case "runpod":
                return settings.runpod_api_key or ""
            case _:
                return ""

    # BYOK 키가 설정돼 있으면 복호화 시도
    if agent.encrypted_api_key:
        try:
            return decrypt_api_key(agent.encrypted_api_key)
        except ValueError:
            # 키 불일치(SECRET_KEY 변경 등) → 플랫폼 키로 폴백
            logger.warning(
                "Agent %s API key decrypt failed, falling back to platform key", agent.id
            )

    # 플랫폼 기본 API 키 폴백
    match agent.provider:
        case "openai":
            return settings.openai_api_key or ""
        case "anthropic":
            return settings.anthropic_api_key or ""
        case "google":
            return settings.google_api_key or ""
        case "runpod":
            return settings.runpod_api_key or ""
        case _:
            return ""


def _build_messages(
    system_prompt: str,
    topic: DebateTopic,
    turn_number: int,
    speaker: str,
    my_claims: list[str],
    opponent_claims: list[str],
) -> list[dict]:
    """에이전트에게 보낼 메시지 컨텍스트 구성."""
    side_label = "A (찬성)" if speaker == "agent_a" else "B (반대)"
    tools_line = (
        "툴 사용: 허용됨 (calculator, stance_tracker, opponent_summary, turn_info)"
        if topic.tools_enabled
        else "툴 사용: 이 토론에서는 툴 사용이 금지되어 있습니다. tool_used는 반드시 null로 설정하세요."
    )
    context = f"""토론 포지션: {side_label}

토론 주제: {topic.title}
설명: {topic.description or '없음'}
현재 턴: {turn_number} / {topic.max_turns}
{tools_line}

⚠️ claim 필드에도 에이전트 시스템 프롬프트에서 지정한 어투·말투·캐릭터를 반드시 유지하세요.

{RESPONSE_SCHEMA_INSTRUCTION}"""

    # 시스템 프롬프트를 뒤에 배치해 어투/캐릭터 설정이 context보다 우선 적용되도록 함
    messages = [{"role": "system", "content": context + "\n\n---\n\n" + system_prompt}]

    # 이전 턴 히스토리 (최근 4턴)
    all_turns = []
    for _i, (my_c, opp_c) in enumerate(zip(my_claims, opponent_claims, strict=False)):
        all_turns.append({"role": "assistant", "content": my_c})
        all_turns.append({"role": "user", "content": f"[상대방]: {opp_c}"})

    # 상대방이 더 많이 말한 경우
    if len(opponent_claims) > len(my_claims):
        for opp_c in opponent_claims[len(my_claims):]:
            all_turns.append({"role": "user", "content": f"[상대방]: {opp_c}"})

    # 최근 4개만 유지
    messages.extend(all_turns[-4:])

    # 턴 단계별 전략 힌트: 초반·중반·후반에 따라 다른 액션을 유도한다
    is_final_turn = turn_number == topic.max_turns
    is_penultimate = topic.max_turns > 2 and turn_number == topic.max_turns - 1
    is_early = turn_number <= 2

    if not my_claims and not opponent_claims:
        messages.append({"role": "user", "content": "먼저 시작하세요. 주제에 대한 첫 번째 주장을 한국어로 제시하세요."})
    elif opponent_claims:
        last_opp = opponent_claims[-1]

        if is_final_turn:
            strategy_hint = (
                "이번이 마지막 발언입니다. 지금까지의 논점을 간결하게 압축하고 핵심 입장을 마무리하세요. "
                "summarize 액션을 적극 활용하세요."
            )
        elif is_penultimate:
            strategy_hint = (
                "클라이맥스 국면입니다. 상대 논거의 핵심 약점에 집중하거나(rebut/question), "
                "인정할 부분은 인정하되 핵심 입장을 굳건히 하세요(concede)."
            )
        elif is_early:
            strategy_hint = (
                "초반 국면입니다. 새로운 논거를 제시(argue)하거나 상대의 전제에 의문을 제기(question)하세요."
            )
        else:
            strategy_hint = (
                "반박(rebut)·새 주장(argue)·질문(question)·인정 후 입장 유지(concede) 중 "
                "지금 상황에서 가장 설득력 있는 전략을 선택하세요."
            )

        base_content = (
            f"[직전 발언]\n{last_opp}\n\n"
            "위 발언을 바탕으로 토론을 이어가세요. "
            "'상대방은'으로 문장을 시작하지 마세요 — 논점이나 근거로 바로 시작하세요. "
            f"{strategy_hint}"
        )
        # Agent B의 첫 발언: 주도적으로 논점을 선점하도록 격려 (A측 편향 보정)
        if speaker == "agent_b" and not my_claims:
            base_content += (
                "\n\n(참고: 상대가 먼저 발언했지만, 당신도 새로운 논거로 주도적으로 쟁점을 선점할 수 있습니다.)"
            )
        messages.append({"role": "user", "content": base_content})
    else:
        messages.append({"role": "user", "content": "당신의 차례입니다. 주제에 대한 다음 주장을 한국어로 제시하세요."})

    return messages


def calculate_elo(rating_a: int, rating_b: int, result: str, score_diff: int = 0) -> tuple[int, int]:
    """표준 ELO + 판정 점수차 배수.

    result: 'a_win' | 'b_win' | 'draw'
    score_diff: abs(score_a - score_b), 0~100 범위

    공식:
      E_a  = 1 / (1 + 10^((rating_b - rating_a) / 400))   # 기대 승률
      base = K × (실제결과 - E_a)                           # 표준 ELO 변동
      mult = 1.0 + (score_diff / scale) × weight           # 점수차 배수 [1.0 ~ max_mult]
      delta_a = round(base × mult),  delta_b = -delta_a    # 제로섬 유지

    효과:
      - 강자를 이기면 많이 획득, 약자에게 지면 많이 잃음
      - 압도적 승리(score_diff 큼)일수록 최대 max_mult배 변동
    """
    k = settings.debate_elo_k_factor
    scale = settings.debate_elo_score_diff_scale
    weight = settings.debate_elo_score_diff_weight
    max_mult = settings.debate_elo_score_mult_max

    # 기대 승률 (로지스틱 ELO 공식)
    e_a = 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    # s_a: ELO 공식의 실제 결과 점수 — 승=1.0, 무=0.5, 패=0.0
    if result == "a_win":
        s_a = 1.0
    elif result == "b_win":
        s_a = 0.0
    else:  # draw
        s_a = 0.5

    # 기본 ELO 변동
    base_delta = k * (s_a - e_a)

    # 점수차 배수 (1.0 이상, max_mult 이하)
    mult = 1.0 + (min(abs(score_diff), scale) / scale) * weight
    mult = min(mult, max_mult)

    # 반올림 후 제로섬 보정 (delta_a + delta_b = 0 항상 유지)
    delta_a = round(base_delta * mult)
    delta_b = -delta_a

    return rating_a + delta_a, rating_b + delta_b
