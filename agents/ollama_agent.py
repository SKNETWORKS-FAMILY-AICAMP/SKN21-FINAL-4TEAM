"""Ollama 로컬 토론 에이전트.

사용법:
  # 설정 파일로 실행 (권장)
  python ollama_agent.py --config my_agent.json

  # CLI 인자로 직접 실행
  python ollama_agent.py --agent-id <UUID> --nickname <닉네임> --password <비밀번호>

  # 전략 프로필 지정
  python ollama_agent.py --config my_agent.json --strategy aggressive

  # 툴 사용 + 체인-오브-쏘트 활성화
  python ollama_agent.py --config my_agent.json --use-tools --chain-of-thought

  # 사용 가능 Ollama 모델 확인
  python ollama_agent.py --list-models

  # 전략 프로필 설명 보기
  python ollama_agent.py --list-strategies

설정 파일 예시 (config.json):
  {
    "agent_id": "xxxx-...",
    "nickname": "내닉네임",
    "password": "내비밀번호",
    "model": "exaone3.5:7.8b",
    "strategy": "analytical",
    "use_tools": false,
    "chain_of_thought": false,
    "temperature": 0.7
  }
"""

import argparse
import asyncio
import io
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import websockets
import websockets.exceptions

# Windows 콘솔이 cp949일 때 UTF-8 문자 출력 실패를 방지
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 로그 설정 ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ollama_agent")

# ── 토론 JSON 스키마 지시문 ───────────────────────────────────────────────────
_SCHEMA_INSTRUCTION = """\
[출력 형식] 반드시 아래 JSON만 출력하세요. 다른 텍스트 없이.
{
  "action": "argue" | "rebut" | "concede" | "question" | "summarize",
  "claim": "<한국어 주요 주장 2~5문장>",
  "evidence": "<한국어 근거/데이터/예시 또는 null>",
  "tool_used": null,
  "tool_result": null
}
action: argue=새 주장, rebut=반박, concede=부분인정, question=의문제기, summarize=정리(마지막턴)"""

# 툴 사용 시 1단계(툴 결정) 스키마
_TOOL_DECISION_SCHEMA = """\
[출력 형식] 반드시 아래 JSON만 출력하세요.
{
  "use_tool": true | false,
  "tool_name": "calculator" | "stance_tracker" | "opponent_summary" | "turn_info" | null,
  "tool_input": "<calculator는 수식, 나머지는 빈 문자열>",
  "reason": "<툴을 사용하거나 사용하지 않는 이유 한 줄>"
}
사용 가능 툴:
- calculator: 수치 계산 (예: "15 * 1.3 + 200")
- stance_tracker: 내가 이전에 한 주장 목록 조회 (일관성 확인)
- opponent_summary: 상대방 주장 요약 조회
- turn_info: 현재 턴 번호, 남은 턴, 누적 벌점 조회"""

# ── 전략 프로필 ───────────────────────────────────────────────────────────────
STRATEGIES: dict[str, dict[str, Any]] = {
    "aggressive": {
        "description": "공격적 반박 스타일 — 상대 논리의 허점을 날카롭게 집중 공략",
        "temperature": 0.85,
        "system_prompt": (
            "당신은 공격적인 토론 전문가입니다. 상대방의 논리적 허점과 근거 부재를 날카롭게 지적하고 "
            "강한 어조로 반박합니다.\n"
            "핵심 전술:\n"
            "- rebut action을 최대한 활용하여 상대의 주장을 논리적으로 해체하세요\n"
            "- 상대 주장의 내부 모순을 찾아 직접 공격하세요\n"
            "- 자신의 주장을 강한 확신의 어조로 표현하세요\n"
            "- evidence에 구체적 수치, 통계, 반례를 적극 제시하세요\n"
            "- 절대 상대의 의견을 무비판적으로 수용하지 마세요"
        ),
    },
    "analytical": {
        "description": "논리 분석 스타일 — 데이터와 체계적 논거 중심의 이성적 토론",
        "temperature": 0.65,
        "system_prompt": (
            "당신은 논리적이고 분석적인 토론 참가자입니다. 체계적인 논거와 검증 가능한 근거를 바탕으로 "
            "주장을 전개합니다.\n"
            "핵심 전술:\n"
            "- 각 주장을 '전제 → 논거 → 결론' 구조로 명확하게 구성하세요\n"
            "- 상대방 주장을 먼저 객관적으로 이해한 후 논리적 약점을 반박하세요\n"
            "- evidence에 인과관계, 통계, 학술적 근거를 명시하세요\n"
            "- question action으로 상대방의 전제와 논거의 타당성을 검증하세요\n"
            "- 감정적 표현을 자제하고 논리와 사실에 집중하세요"
        ),
    },
    "balanced": {
        "description": "균형 스타일 — 상대방을 인정하면서 핵심 주장을 견고하게 유지",
        "temperature": 0.72,
        "system_prompt": (
            "당신은 균형 잡힌 토론 참가자입니다. 상대방의 타당한 주장은 인정하되 자신의 핵심 논지를 "
            "일관되게 유지합니다.\n"
            "핵심 전술:\n"
            "- concede action으로 상대의 일부 주장을 인정한 뒤 'but' 전환으로 핵심 주장을 강화하세요\n"
            "- 상대방의 주장에서 배울 점과 동의하기 어려운 점을 명확히 구분하세요\n"
            "- 극단적 주장보다 합리적이고 수용 가능한 근거를 제시하세요\n"
            "- 토론 전체의 흐름을 파악하고 전략적으로 action을 선택하세요"
        ),
    },
    "socratic": {
        "description": "소크라테스 스타일 — 질문으로 상대 전제를 흔들어 자기모순 유도",
        "temperature": 0.78,
        "system_prompt": (
            "당신은 소크라테스식 문답법을 구사하는 토론가입니다. 직접 반박 대신 날카로운 질문으로 "
            "상대방이 스스로 자신의 논리적 모순을 인식하도록 유도합니다.\n"
            "핵심 전술:\n"
            "- question action을 주로 사용하여 상대방의 전제와 근거에 의문을 제기하세요\n"
            "- '그렇다면 ~는 어떻게 설명하시겠습니까?' 형식의 질문으로 상대를 압박하세요\n"
            "- 상대방이 당연하게 여기는 전제가 실제로 성립하는지 검증을 요구하세요\n"
            "- 마지막 턴에는 전체 토론에서 드러난 상대방의 모순을 정리하여 summarize하세요"
        ),
    },
    "custom": {
        "description": "커스텀 스타일 — --system-prompt 또는 설정 파일의 system_prompt 사용",
        "temperature": 0.72,
        "system_prompt": "",  # 사용자가 직접 지정
    },
}


# ── 설정 데이터클래스 ─────────────────────────────────────────────────────────
@dataclass
class AgentConfig:
    agent_id: str = ""
    token: str = ""
    nickname: str = ""
    password: str = ""
    server: str = "http://localhost:8000"
    model: str = ""
    ollama_url: str = "http://localhost:11434"
    strategy: str = "analytical"
    system_prompt: str = ""       # 비어 있으면 strategy 프로필 사용
    temperature: float = 0.72
    num_predict: int = 600
    timeout: int = 55
    use_tools: bool = False
    chain_of_thought: bool = False
    reconnect: bool = True

    def effective_system_prompt(self) -> str:
        """최종 시스템 프롬프트. custom이 있으면 우선, 없으면 strategy 프로필 사용."""
        if self.system_prompt.strip():
            return self.system_prompt.strip()
        profile = STRATEGIES.get(self.strategy, STRATEGIES["analytical"])
        return profile["system_prompt"]

    def effective_temperature(self) -> float:
        """최종 temperature. config 기본값이 0.72(초기값)이면 strategy 기본값 사용."""
        if self.temperature != 0.72:
            return self.temperature
        profile = STRATEGIES.get(self.strategy, STRATEGIES["analytical"])
        return float(profile.get("temperature", 0.72))


def load_config_file(path: str) -> dict:
    """JSON 설정 파일 로드."""
    p = Path(path)
    if not p.exists():
        logger.error("설정 파일을 찾을 수 없습니다: %s", path)
        sys.exit(1)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error("설정 파일 JSON 오류: %s", e)
        sys.exit(1)


# ── Ollama 호출 ──────────────────────────────────────────────────────────────
async def list_ollama_models(ollama_url: str) -> list[str]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{ollama_url}/api/tags")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]


async def call_ollama(
    model: str,
    messages: list[dict],
    ollama_url: str,
    timeout: float,
    temperature: float = 0.72,
    num_predict: int = 600,
    force_json: bool = True,
) -> str:
    """Ollama /api/chat 호출. force_json=True면 format:json 강제."""
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    if force_json:
        body["format"] = "json"

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{ollama_url}/api/chat", json=body)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


# ── 응답 파싱 ────────────────────────────────────────────────────────────────
def parse_turn_response(raw: str) -> tuple[str, str, str | None]:
    """(action, claim, evidence) 추출. JSON → JSON블록 → 폴백 순."""
    for text in [raw.strip(), re.search(r"\{[\s\S]*\}", raw) and re.search(r"\{[\s\S]*\}", raw).group()]:
        if not text:
            continue
        try:
            d = json.loads(text)
            action = str(d.get("action", "argue"))
            claim = str(d.get("claim", "")).strip()
            evidence = d.get("evidence") or None
            if claim:
                return action, claim, evidence
        except (json.JSONDecodeError, AttributeError):
            pass
    logger.warning("JSON 파싱 실패, 원문을 claim으로 사용")
    return "argue", raw.strip()[:500], None


def parse_tool_decision(raw: str) -> dict:
    """툴 결정 JSON 파싱. 파싱 실패 시 use_tool=False 반환."""
    for text in [raw.strip(), re.search(r"\{[\s\S]*\}", raw) and re.search(r"\{[\s\S]*\}", raw).group()]:
        if not text:
            continue
        try:
            d = json.loads(text)
            if isinstance(d.get("use_tool"), bool):
                return d
        except (json.JSONDecodeError, AttributeError):
            pass
    return {"use_tool": False}


# ── 메시지 구성 ──────────────────────────────────────────────────────────────
def build_turn_messages(request: dict, system_prompt: str, tool_result_context: str = "") -> list[dict]:
    """WSTurnRequest + 옵션 툴 결과 → Ollama messages."""
    topic_title = request["topic_title"]
    topic_desc = request.get("topic_description") or "없음"
    turn_number = request["turn_number"]
    max_turns = request["max_turns"]
    speaker = request["speaker"]
    my_claims: list[str] = request.get("my_previous_claims", [])
    opponent_claims: list[str] = request.get("opponent_previous_claims", [])
    is_last = turn_number == max_turns
    side_label = "A (찬성/주장)" if speaker == "agent_a" else "B (반대/반박)"

    context = (
        f"포지션: {side_label} | 주제: {topic_title} | 설명: {topic_desc}\n"
        f"현재 턴: {turn_number}/{max_turns}"
        + (" [마지막 턴 — summarize 권장]" if is_last else "")
        + (f"\n\n[툴 조회 결과]\n{tool_result_context}" if tool_result_context else "")
        + f"\n\n{_SCHEMA_INSTRUCTION}"
    )
    base = (system_prompt + "\n\n" + context) if system_prompt else context
    messages: list[dict] = [{"role": "system", "content": base}]

    # 최근 4턴 이전 대화
    history: list[dict] = []
    for my_c, opp_c in zip(my_claims, opponent_claims):
        history.append({"role": "assistant", "content": my_c})
        history.append({"role": "user", "content": f"[상대방]: {opp_c}"})
    if len(opponent_claims) > len(my_claims):
        for opp_c in opponent_claims[len(my_claims):]:
            history.append({"role": "user", "content": f"[상대방]: {opp_c}"})
    messages.extend(history[-4:])

    if not my_claims and not opponent_claims:
        messages.append({"role": "user", "content": "첫 주장을 한국어로 제시하세요."})
    else:
        messages.append({"role": "user", "content": "한국어로 응답하세요."})
    return messages


def build_cot_messages(request: dict, system_prompt: str) -> list[dict]:
    """체인-오브-쏘트 1단계 — 상황 분석 프롬프트."""
    topic_title = request["topic_title"]
    turn_number = request["turn_number"]
    max_turns = request["max_turns"]
    speaker = request["speaker"]
    my_claims: list[str] = request.get("my_previous_claims", [])
    opponent_claims: list[str] = request.get("opponent_previous_claims", [])
    side_label = "A (찬성)" if speaker == "agent_a" else "B (반대)"

    opp_summary = "\n".join(f"  - 턴{i+1}: {c[:200]}" for i, c in enumerate(opponent_claims[-3:])) or "  (없음)"
    my_summary = "\n".join(f"  - 턴{i+1}: {c[:200]}" for i, c in enumerate(my_claims[-3:])) or "  (없음)"

    analysis_prompt = (
        f"토론 주제: {topic_title}\n"
        f"내 포지션: {side_label} | 현재 턴: {turn_number}/{max_turns}\n\n"
        f"[내 이전 주장]\n{my_summary}\n\n"
        f"[상대방 이전 주장]\n{opp_summary}\n\n"
        "다음을 짧게 분석하세요 (한국어, 자유 형식, JSON 아님):\n"
        "1. 상대방 주장의 핵심 논점과 가장 취약한 부분\n"
        "2. 내가 사용할 최선의 전략 (argue/rebut/concede/question/summarize)\n"
        "3. 활용할 수 있는 가장 강력한 논거 또는 반례"
    )
    base = (system_prompt + "\n\n당신은 토론 분석가입니다.") if system_prompt else "당신은 토론 분석가입니다."
    return [
        {"role": "system", "content": base},
        {"role": "user", "content": analysis_prompt},
    ]


def build_tool_decision_messages(request: dict, system_prompt: str) -> list[dict]:
    """툴 사용 여부 결정 프롬프트."""
    turn_number = request["turn_number"]
    max_turns = request["max_turns"]
    available_tools: list[str] = request.get("available_tools", [])
    speaker = request["speaker"]
    side_label = "A (찬성)" if speaker == "agent_a" else "B (반대)"

    tool_desc = ", ".join(available_tools) if available_tools else "없음"
    prompt = (
        f"토론 주제: {request['topic_title']} | 포지션: {side_label} | 턴: {turn_number}/{max_turns}\n"
        f"사용 가능 툴: {tool_desc}\n\n"
        f"{_TOOL_DECISION_SCHEMA}\n\n"
        "지금 어떤 툴을 사용할지 JSON으로 결정하세요. "
        "툴이 도움이 되지 않으면 use_tool: false로 하세요."
    )
    base = (system_prompt + "\n\n당신은 토론 에이전트입니다.") if system_prompt else "당신은 토론 에이전트입니다."
    return [
        {"role": "system", "content": base},
        {"role": "user", "content": prompt},
    ]


# ── 세션 (툴 결과 라우팅) ────────────────────────────────────────────────────
class Session:
    """WebSocket 세션. 툴 결과를 비동기 큐로 턴 핸들러에 전달한다."""

    def __init__(self) -> None:
        self._tool_queue: asyncio.Queue = asyncio.Queue()

    def put_tool_result(self, msg: dict) -> None:
        self._tool_queue.put_nowait(msg)

    async def get_tool_result(self, timeout: float = 30.0) -> dict | None:
        try:
            return await asyncio.wait_for(self._tool_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


# ── 턴 처리 ──────────────────────────────────────────────────────────────────
async def handle_turn(ws, request: dict, cfg: AgentConfig, session: Session) -> None:
    """단일 턴 전체 처리. CoT → 툴 → 최종 응답 순."""
    match_id = request["match_id"]
    turn_number = request["turn_number"]
    speaker = request["speaker"]
    available_tools: list[str] = request.get("available_tools", [])

    logger.info(">>> Turn %d 시작 (speaker=%s)", turn_number, speaker)
    t_start = time.monotonic()

    system_prompt = cfg.effective_system_prompt()
    temperature = cfg.effective_temperature()
    ollama_timeout = max(cfg.timeout - 10, 15)
    tool_result_context = ""
    tool_used_name: str | None = None

    try:
        # ── 1단계: 체인-오브-쏘트 (선택) ────────────────────────────────────
        analysis_context = ""
        if cfg.chain_of_thought:
            logger.info("  [CoT] 상황 분석 중...")
            cot_msgs = build_cot_messages(request, system_prompt)
            analysis_raw = await call_ollama(
                cfg.model, cot_msgs, cfg.ollama_url,
                timeout=ollama_timeout / 2,
                temperature=temperature,
                num_predict=400,
                force_json=False,
            )
            analysis_context = analysis_raw.strip()[:600]
            logger.info("  [CoT] 분석 완료: %.80s...", analysis_context)

        # ── 2단계: 툴 사용 결정 (선택) ──────────────────────────────────────
        if cfg.use_tools and available_tools:
            logger.info("  [Tool] 툴 사용 여부 결정 중...")
            tool_msgs = build_tool_decision_messages(request, system_prompt)
            if analysis_context:
                # CoT 분석 결과를 툴 결정에 반영
                tool_msgs[-1]["content"] += f"\n\n[분석 결과]\n{analysis_context}"
            tool_decision_raw = await call_ollama(
                cfg.model, tool_msgs, cfg.ollama_url,
                timeout=ollama_timeout / 2,
                temperature=0.3,  # 결정은 낮은 temperature
                num_predict=200,
            )
            decision = parse_tool_decision(tool_decision_raw)

            if decision.get("use_tool") and decision.get("tool_name") in available_tools:
                tool_name = decision["tool_name"]
                tool_input = decision.get("tool_input", "")
                logger.info("  [Tool] '%s' 사용 요청 (input: %.40s)", tool_name, tool_input)

                # 서버에 tool_request 전송
                await ws.send(json.dumps({
                    "type": "tool_request",
                    "match_id": match_id,
                    "turn_number": turn_number,
                    "tool_name": tool_name,
                    "tool_input": tool_input,
                }, ensure_ascii=False))

                # tool_result 대기 (Session 큐 경유)
                result_msg = await session.get_tool_result(timeout=15.0)
                if result_msg and not result_msg.get("error"):
                    tool_result_context = f"[{tool_name}] {result_msg['result']}"
                    tool_used_name = tool_name
                    logger.info("  [Tool] 결과: %.80s", tool_result_context)
                elif result_msg:
                    logger.warning("  [Tool] 오류: %s", result_msg.get("error"))
            else:
                logger.info("  [Tool] 툴 사용 안 함 (%s)", decision.get("reason", ""))

        # ── 3단계: 최종 응답 생성 ────────────────────────────────────────────
        # CoT 분석 결과를 시스템 프롬프트에 통합
        final_system = system_prompt
        if analysis_context:
            final_system = (
                (system_prompt + "\n\n") if system_prompt else ""
            ) + f"[이전 분석]\n{analysis_context}"

        final_msgs = build_turn_messages(request, final_system, tool_result_context)
        raw = await call_ollama(
            cfg.model, final_msgs, cfg.ollama_url,
            timeout=ollama_timeout,
            temperature=temperature,
            num_predict=cfg.num_predict,
        )
        logger.debug("  Ollama raw: %s", raw[:200])
        action, claim, evidence = parse_turn_response(raw)

    except asyncio.TimeoutError:
        logger.warning("  [TIMEOUT] Turn %d — %ds 초과", turn_number, ollama_timeout)
        action, claim, evidence = "argue", "[TIMEOUT: Ollama 응답 시간 초과]", None
        tool_used_name = None

    except httpx.HTTPError as e:
        logger.error("  [HTTP ERROR] Turn %d — %s", turn_number, e)
        action, claim, evidence = "argue", f"[ERROR: Ollama 연결 실패 — {e}]", None
        tool_used_name = None

    elapsed = time.monotonic() - t_start
    logger.info(
        "<<< Turn %d 완료 (%.1fs) [%s]%s — %.80s%s",
        turn_number, elapsed, action,
        f" [tool:{tool_used_name}]" if tool_used_name else "",
        claim, "..." if len(claim) > 80 else "",
    )

    await ws.send(json.dumps({
        "type": "turn_response",
        "match_id": match_id,
        "action": action,
        "claim": claim,
        "evidence": evidence,
        "tool_used": tool_used_name,
        "tool_result": tool_result_context or None,
    }, ensure_ascii=False))


# ── 인증 ─────────────────────────────────────────────────────────────────────
async def get_token(api_base: str, nickname: str, password: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{api_base}/api/auth/login",
            json={"nickname": nickname, "password": password},
        )
        if resp.status_code == 401:
            logger.error("로그인 실패: 닉네임 또는 비밀번호를 확인하세요")
            sys.exit(1)
        resp.raise_for_status()
        return resp.json()["access_token"]


# ── 메인 에이전트 루프 ────────────────────────────────────────────────────────
async def run_agent(cfg: AgentConfig, token: str) -> None:
    ws_base = cfg.server.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_base}/ws/agent/{cfg.agent_id}?token={token}"
    display_url = f"{ws_base}/ws/agent/{cfg.agent_id}"

    strategy_name = cfg.strategy
    profile = STRATEGIES.get(strategy_name, STRATEGIES["analytical"])
    logger.info("전략: %s | %s", strategy_name, profile["description"])
    logger.info("모델: %s | temperature: %.2f | num_predict: %d",
                cfg.model, cfg.effective_temperature(), cfg.num_predict)
    logger.info("옵션: 툴=%s | CoT=%s", cfg.use_tools, cfg.chain_of_thought)

    attempt = 0
    while True:
        attempt += 1
        session = Session()
        current_turn_task: asyncio.Task | None = None

        try:
            logger.info("서버 연결 중 (시도 #%d): %s", attempt, display_url)
            async with websockets.connect(
                ws_url,
                ping_interval=None,
                max_size=10 * 1024 * 1024,
                open_timeout=15,
            ) as ws:
                attempt = 0
                logger.info("연결 성공! 에이전트 ID: %s", cfg.agent_id)
                logger.info("토론 매치 배정 대기 중...")

                async for raw_msg in ws:
                    try:
                        msg = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        logger.warning("JSON 파싱 실패: %s", str(raw_msg)[:100])
                        continue

                    msg_type = msg.get("type")

                    if msg_type == "match_ready":
                        logger.info(
                            "=== 매치 시작! 주제: [%s] | 상대: %s | 내 포지션: %s ===",
                            msg["topic_title"], msg["opponent_name"], msg["your_side"],
                        )

                    elif msg_type == "turn_request":
                        # 이전 턴 완료 대기 (중복 방지)
                        if current_turn_task and not current_turn_task.done():
                            logger.debug("이전 턴 완료 대기...")
                            await current_turn_task
                        current_turn_task = asyncio.create_task(
                            handle_turn(ws, msg, cfg, session)
                        )

                    elif msg_type == "tool_result":
                        # 턴 핸들러의 큐로 라우팅
                        session.put_tool_result(msg)
                        logger.debug("tool_result 수신 → 큐 전달: %s", msg.get("tool_name"))

                    elif msg_type == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        logger.debug("pong 전송")

                    elif msg_type == "error":
                        code = str(msg.get("code", ""))
                        logger.error("서버 에러 [%s]: %s", code, msg.get("message", ""))
                        if code in ("4001", "4003", "4004"):
                            logger.error("인증/권한 오류 — 종료")
                            return

                    else:
                        logger.debug("알 수 없는 메시지: %s", msg_type)

        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning("연결 끊김: code=%s reason=%s", e.code, e.reason)
            if str(e.code) in ("4001", "4003", "4004"):
                logger.error("인증/권한 오류 — 종료")
                return
        except websockets.exceptions.InvalidURI as e:
            logger.error("잘못된 WebSocket URL: %s", e)
            return
        except OSError as e:
            logger.error("네트워크 오류: %s", e)
        except Exception as e:
            logger.error("예상치 못한 오류: %s", e, exc_info=True)

        if not cfg.reconnect:
            break

        wait = min(5 * attempt, 60)
        logger.info("%d초 후 재연결...", wait)
        await asyncio.sleep(wait)

    logger.info("에이전트 종료")


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Ollama 로컬 토론 에이전트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python ollama_agent.py --config config.json
  python ollama_agent.py --agent-id xxx --nickname name --password pass --strategy aggressive
  python ollama_agent.py --config config.json --use-tools --chain-of-thought
  python ollama_agent.py --list-models
  python ollama_agent.py --list-strategies
        """,
    )
    p.add_argument("--config", metavar="PATH", help="JSON 설정 파일 경로")
    p.add_argument("--agent-id", metavar="UUID")
    p.add_argument("--token", metavar="JWT")
    p.add_argument("--nickname", metavar="NAME")
    p.add_argument("--password", metavar="PASS")
    p.add_argument("--server", default=None, metavar="URL", help="기본값: http://localhost:8000")
    p.add_argument("--model", metavar="NAME", help="Ollama 모델 (기본: 첫 번째 설치 모델)")
    p.add_argument("--ollama-url", default=None, metavar="URL", help="기본값: http://localhost:11434")
    p.add_argument(
        "--strategy",
        choices=list(STRATEGIES.keys()),
        default=None,
        metavar="NAME",
        help=f"전략 프로필: {', '.join(STRATEGIES.keys())}",
    )
    p.add_argument("--system-prompt", default=None, metavar="TEXT", help="커스텀 시스템 프롬프트 (strategy 덮어씀)")
    p.add_argument("--system-prompt-file", metavar="PATH", help="시스템 프롬프트 파일")
    p.add_argument("--temperature", type=float, default=None, help="LLM 온도 (0.0~1.0)")
    p.add_argument("--num-predict", type=int, default=None, metavar="N", help="최대 출력 토큰 수")
    p.add_argument("--timeout", type=int, default=None, metavar="SEC", help="턴 타임아웃 초 (기본: 55)")
    p.add_argument("--use-tools", action="store_true", help="서버 측 툴 사용 활성화")
    p.add_argument("--chain-of-thought", action="store_true", help="응답 전 상황 분석 단계 활성화")
    p.add_argument("--no-reconnect", action="store_true", help="연결 끊김 시 재연결 안 함")
    p.add_argument("--list-models", action="store_true", help="Ollama 모델 목록 출력 후 종료")
    p.add_argument("--list-strategies", action="store_true", help="전략 프로필 설명 출력 후 종료")
    p.add_argument("--debug", action="store_true", help="디버그 로그")
    return p.parse_args()


async def main() -> None:
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # 전략 목록 출력
    if args.list_strategies:
        print("사용 가능한 전략 프로필:")
        for name, profile in STRATEGIES.items():
            temp = profile.get("temperature", 0.72)
            print(f"  {name:<12} (temp={temp}) — {profile['description']}")
        return

    ollama_url = args.ollama_url or "http://localhost:11434"

    # Ollama 모델 목록 출력
    if args.list_models:
        try:
            models = await list_ollama_models(ollama_url)
            if models:
                print("설치된 Ollama 모델:")
                for m in models:
                    print(f"  - {m}")
            else:
                print("설치된 모델 없음. `ollama pull <model>` 로 설치하세요.")
        except Exception as e:
            print(f"Ollama 연결 실패 ({ollama_url}): {e}")
        return

    # ── 설정 조합: 기본값 → 설정 파일 → CLI 인자 ──────────────────────────
    cfg = AgentConfig()

    if args.config:
        file_data = load_config_file(args.config)
        for key, val in file_data.items():
            attr = key.replace("-", "_")
            if hasattr(cfg, attr):
                setattr(cfg, attr, val)

    # CLI 인자가 있으면 설정 파일 값을 덮어씀
    if args.agent_id:
        cfg.agent_id = args.agent_id
    if args.token:
        cfg.token = args.token
    if args.nickname:
        cfg.nickname = args.nickname
    if args.password:
        cfg.password = args.password
    if args.server:
        cfg.server = args.server
    if args.model:
        cfg.model = args.model
    if args.ollama_url:
        cfg.ollama_url = args.ollama_url
    if args.strategy:
        cfg.strategy = args.strategy
    if args.temperature is not None:
        cfg.temperature = args.temperature
    if args.num_predict is not None:
        cfg.num_predict = args.num_predict
    if args.timeout is not None:
        cfg.timeout = args.timeout
    if args.use_tools:
        cfg.use_tools = True
    if args.chain_of_thought:
        cfg.chain_of_thought = True
    if args.no_reconnect:
        cfg.reconnect = False

    # 시스템 프롬프트 파일 로드
    if args.system_prompt:
        cfg.system_prompt = args.system_prompt
        cfg.strategy = "custom"
    elif args.system_prompt_file:
        try:
            cfg.system_prompt = Path(args.system_prompt_file).read_text(encoding="utf-8")
            cfg.strategy = "custom"
        except OSError as e:
            logger.warning("시스템 프롬프트 파일 로드 실패: %s", e)

    # 필수 값 검증
    if not cfg.agent_id:
        print("오류: agent_id 가 필요합니다. --agent-id 또는 config 파일에 설정하세요.")
        sys.exit(1)

    # Ollama 연결 확인 + 모델 선택
    try:
        models = await list_ollama_models(cfg.ollama_url)
    except Exception as e:
        logger.error("Ollama 연결 실패 (%s): %s", cfg.ollama_url, e)
        logger.error("`ollama serve` 로 Ollama를 먼저 실행하세요.")
        sys.exit(1)

    if not models:
        logger.error("설치된 Ollama 모델 없음. `ollama pull <model>` 로 설치하세요.")
        sys.exit(1)

    if not cfg.model:
        cfg.model = models[0]
        logger.info("모델 자동 선택: %s", cfg.model)
    elif cfg.model not in models:
        logger.warning("모델 '%s' 이 목록에 없음. 계속 진행...", cfg.model)

    # 토큰 확보
    token = cfg.token
    if not token:
        if cfg.nickname and cfg.password:
            http_base = cfg.server.replace("ws://", "http://").replace("wss://", "https://")
            logger.info("로그인 중: %s", cfg.nickname)
            token = await get_token(http_base, cfg.nickname, cfg.password)
            logger.info("로그인 성공")
        else:
            print("오류: token 또는 (nickname + password) 가 필요합니다.")
            sys.exit(1)

    await run_agent(cfg, token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n에이전트를 종료합니다.")
