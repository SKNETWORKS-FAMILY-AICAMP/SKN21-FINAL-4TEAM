"""Ollama 로컬 토론 에이전트.

사용법:
  # 1. 의존성 설치
  pip install websockets httpx

  # 2. 실행 (토큰 직접 지정)
  python ollama_agent.py --agent-id <UUID> --token <JWT>

  # 3. 실행 (로그인 자동 처리)
  python ollama_agent.py --agent-id <UUID> --nickname <닉네임> --password <비밀번호>

  # 4. 모델 지정 (기본값: Ollama 첫 번째 모델)
  python ollama_agent.py --agent-id <UUID> --token <JWT> --model llama3.2

  # 5. 옵션 확인
  python ollama_agent.py --help

에이전트 등록은 웹 UI(설정 → 내 에이전트 → 새 에이전트)에서 provider=local로 생성하면 된다.
"""

import argparse
import asyncio
import json
import logging
import re
import sys

import httpx
import websockets
import websockets.exceptions

# ── 로그 설정 ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ollama_agent")

# ── 토론 응답 JSON 스키마 지시문 ─────────────────────────────────────────────
_SCHEMA_INSTRUCTION = """⚠️ 중요: 반드시 한국어로만 답변하고, 아래 JSON 형식만 출력하세요.
다른 텍스트나 설명을 절대 추가하지 마세요.

{
  "action": "argue" | "rebut" | "concede" | "question" | "summarize",
  "claim": "<한국어 주요 주장 (2~5문장)>",
  "evidence": "<한국어 근거/데이터/예시>" | null,
  "tool_used": null,
  "tool_result": null
}

action 가이드:
- argue: 새 근거를 들어 주장 강화
- rebut: 상대방 주장의 논리적 허점 지적
- concede: 상대방 일부 인정 후 핵심 주장 유지
- question: 상대방 주장의 전제/근거에 의문 제기
- summarize: 논의 정리 및 자신의 입장 확인 (마지막 턴에 적합)"""


# ── Ollama 호출 ──────────────────────────────────────────────────────────────

async def list_ollama_models(ollama_url: str) -> list[str]:
    """Ollama에 설치된 모델 목록 반환."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{ollama_url}/api/tags")
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]


async def call_ollama(
    model: str,
    messages: list[dict],
    ollama_url: str,
    timeout: float,
) -> str:
    """Ollama /api/chat 호출 → 응답 텍스트 반환."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{ollama_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.7,
                    "num_predict": 512,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


# ── 응답 파싱 ────────────────────────────────────────────────────────────────

def parse_llm_response(raw: str) -> tuple[str, str, str | None]:
    """LLM 응답에서 (action, claim, evidence) 추출.

    직접 JSON 파싱 → JSON 블록 추출 → 폴백(전체 텍스트) 순으로 시도.
    """
    # 1. 직접 파싱
    try:
        parsed = json.loads(raw.strip())
        action = str(parsed.get("action", "argue"))
        claim = str(parsed.get("claim", "")).strip()
        evidence = parsed.get("evidence")
        if claim:
            return action, claim, evidence if evidence else None
    except (json.JSONDecodeError, AttributeError):
        pass

    # 2. 텍스트 안의 JSON 블록 추출
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            action = str(parsed.get("action", "argue"))
            claim = str(parsed.get("claim", "")).strip()
            evidence = parsed.get("evidence")
            if claim:
                return action, claim, evidence if evidence else None
        except (json.JSONDecodeError, AttributeError):
            pass

    # 3. 폴백: 원문 텍스트 그대로 claim으로
    logger.warning("JSON 파싱 실패, 원문을 claim으로 사용")
    return "argue", raw.strip()[:500], None


# ── 메시지 구성 ──────────────────────────────────────────────────────────────

def build_messages(request: dict, system_prompt: str) -> list[dict]:
    """WSTurnRequest → Ollama messages 구성."""
    topic_title = request["topic_title"]
    topic_desc = request.get("topic_description") or "없음"
    turn_number = request["turn_number"]
    max_turns = request["max_turns"]
    speaker = request["speaker"]
    my_claims: list[str] = request.get("my_previous_claims", [])
    opponent_claims: list[str] = request.get("opponent_previous_claims", [])

    side_label = "A (찬성/주장)" if speaker == "agent_a" else "B (반대/반박)"
    is_last = turn_number == max_turns

    context = (
        f"당신은 한국어 AI 토론 참가자입니다. 포지션: {side_label}\n\n"
        f"토론 주제: {topic_title}\n"
        f"설명: {topic_desc}\n"
        f"현재 턴: {turn_number} / {max_turns}"
        + (" (마지막 턴 — summarize 권장)" if is_last else "")
        + f"\n\n{_SCHEMA_INSTRUCTION}"
    )

    base_system = (system_prompt.strip() + "\n\n" + context) if system_prompt.strip() else context
    messages: list[dict] = [{"role": "system", "content": base_system}]

    # 최근 4턴 이전 대화 히스토리
    history: list[dict] = []
    for my_c, opp_c in zip(my_claims, opponent_claims):
        history.append({"role": "assistant", "content": my_c})
        history.append({"role": "user", "content": f"[상대방]: {opp_c}"})
    if len(opponent_claims) > len(my_claims):
        for opp_c in opponent_claims[len(my_claims):]:
            history.append({"role": "user", "content": f"[상대방]: {opp_c}"})
    messages.extend(history[-4:])

    if not my_claims and not opponent_claims:
        messages.append({"role": "user", "content": "먼저 시작하세요. 주제에 대한 첫 주장을 한국어로 제시하세요."})
    else:
        messages.append({"role": "user", "content": "당신의 차례입니다. 한국어로 응답하세요."})

    return messages


# ── 턴 처리 ──────────────────────────────────────────────────────────────────

async def handle_turn(
    ws,
    request: dict,
    model: str,
    ollama_url: str,
    system_prompt: str,
    turn_timeout: int,
) -> None:
    """단일 턴 처리: Ollama 호출 → turn_response 전송."""
    match_id = request["match_id"]
    turn_number = request["turn_number"]
    speaker = request["speaker"]

    logger.info("▶ Turn %d 시작 (speaker=%s)", turn_number, speaker)

    messages = build_messages(request, system_prompt)
    ollama_timeout = max(turn_timeout - 8, 10)  # 여유 8초 (네트워크 + 서버 처리)

    try:
        raw = await asyncio.wait_for(
            call_ollama(model, messages, ollama_url, timeout=float(ollama_timeout)),
            timeout=float(ollama_timeout + 2),
        )
        logger.debug("Ollama 응답 (raw): %s", raw[:200])

        action, claim, evidence = parse_llm_response(raw)
        logger.info("✓ Turn %d 완료: [%s] %.80s%s", turn_number, action, claim, "..." if len(claim) > 80 else "")

    except asyncio.TimeoutError:
        logger.warning("✗ Turn %d Ollama 타임아웃 (%ds 초과)", turn_number, ollama_timeout)
        action = "argue"
        claim = "[TIMEOUT: Ollama 응답 시간 초과]"
        evidence = None

    except httpx.HTTPError as e:
        logger.error("✗ Turn %d Ollama HTTP 오류: %s", turn_number, e)
        action = "argue"
        claim = f"[ERROR: Ollama 연결 실패 — {e}]"
        evidence = None

    response = {
        "type": "turn_response",
        "match_id": match_id,
        "action": action,
        "claim": claim,
        "evidence": evidence,
        "tool_used": None,
        "tool_result": None,
    }
    await ws.send(json.dumps(response, ensure_ascii=False))


# ── 인증 ─────────────────────────────────────────────────────────────────────

async def get_token(api_base: str, nickname: str, password: str) -> str:
    """닉네임/비밀번호로 로그인 → JWT 토큰 반환."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{api_base}/api/auth/login",
            json={"nickname": nickname, "password": password},
        )
        if resp.status_code == 401:
            logger.error("로그인 실패: 닉네임 또는 비밀번호가 올바르지 않습니다")
            sys.exit(1)
        resp.raise_for_status()
        return resp.json()["access_token"]


# ── 메인 에이전트 루프 ────────────────────────────────────────────────────────

async def run_agent(
    ws_base: str,
    agent_id: str,
    token: str,
    model: str,
    ollama_url: str,
    system_prompt: str,
    turn_timeout: int,
    reconnect: bool,
) -> None:
    """WebSocket 연결 + 메시지 처리 루프."""
    ws_url = f"{ws_base}/ws/agent/{agent_id}?token={token}"
    display_url = f"{ws_base}/ws/agent/{agent_id}"

    attempt = 0
    while True:
        attempt += 1
        try:
            logger.info("서버 연결 중 (시도 #%d): %s", attempt, display_url)
            async with websockets.connect(
                ws_url,
                ping_interval=None,       # 서버가 ping 전송을 담당
                max_size=10 * 1024 * 1024,
                open_timeout=15,
            ) as ws:
                attempt = 0
                logger.info("✅ 연결 성공! 에이전트 ID: %s | 모델: %s", agent_id, model)
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
                            "🥊 매치 시작! 주제: [%s] | 상대: %s | 내 포지션: %s",
                            msg["topic_title"],
                            msg["opponent_name"],
                            msg["your_side"],
                        )

                    elif msg_type == "turn_request":
                        await handle_turn(ws, msg, model, ollama_url, system_prompt, turn_timeout)

                    elif msg_type == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        logger.debug("pong 전송")

                    elif msg_type == "error":
                        code = msg.get("code", "")
                        message = msg.get("message", "")
                        logger.error("서버 에러 [%s]: %s", code, message)
                        # 인증 오류는 재연결 불가
                        if code in ("4001", "4003", "4004"):
                            logger.error("인증/권한 오류 — 에이전트를 종료합니다")
                            return

                    elif msg_type == "tool_result":
                        # 이 에이전트는 툴을 직접 요청하지 않으므로 무시
                        logger.debug("tool_result 수신 (무시): %s", msg.get("tool_name"))

                    else:
                        logger.debug("알 수 없는 메시지: %s", msg_type)

        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning("연결 끊김: code=%s reason=%s", e.code, e.reason)
            if e.code == 4001:
                logger.error("인증 실패 — 토큰을 확인하세요")
                return
            if e.code in (4003, 4004):
                logger.error("권한/에이전트 오류 — 에이전트 ID를 확인하세요")
                return

        except websockets.exceptions.InvalidURI as e:
            logger.error("잘못된 WebSocket URL: %s", e)
            return

        except OSError as e:
            logger.error("네트워크 오류: %s", e)

        except Exception as e:
            logger.error("예상치 못한 오류: %s", e, exc_info=True)

        if not reconnect:
            break

        wait = min(5 * attempt, 60)
        logger.info("%d초 후 재연결 시도...", wait)
        await asyncio.sleep(wait)

    logger.info("에이전트 종료")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Ollama 로컬 토론 에이전트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 토큰으로 직접 실행
  python ollama_agent.py --agent-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx --token eyJ...

  # 닉네임/비밀번호로 자동 로그인
  python ollama_agent.py --agent-id xxxxxxxx-... --nickname myname --password mypass

  # Ollama 모델 지정 + 서버 주소 변경
  python ollama_agent.py --agent-id ... --token ... --model llama3.2 --server http://54.180.202.169:8000

  # 사용 가능한 Ollama 모델 확인
  python ollama_agent.py --list-models
        """,
    )

    p.add_argument("--agent-id", metavar="UUID", help="로컬 에이전트 UUID (웹 UI에서 확인)")
    p.add_argument("--token", metavar="JWT", help="JWT 액세스 토큰")
    p.add_argument("--nickname", metavar="NAME", help="로그인 닉네임 (--token 대신 사용)")
    p.add_argument("--password", metavar="PASS", help="로그인 비밀번호 (--token 대신 사용)")
    p.add_argument(
        "--server",
        default="http://localhost:8000",
        metavar="URL",
        help="백엔드 서버 주소 (기본값: http://localhost:8000)",
    )
    p.add_argument(
        "--model",
        metavar="NAME",
        help="Ollama 모델 이름 (기본값: 첫 번째 설치 모델)",
    )
    p.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        metavar="URL",
        help="Ollama 서버 주소 (기본값: http://localhost:11434)",
    )
    p.add_argument(
        "--system-prompt",
        default="",
        metavar="TEXT",
        help="에이전트 시스템 프롬프트 (선택)",
    )
    p.add_argument(
        "--system-prompt-file",
        metavar="PATH",
        help="시스템 프롬프트 파일 경로 (--system-prompt 우선)",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=55,
        metavar="SEC",
        help="턴 응답 타임아웃 초 (기본값: 55, 서버 타임아웃보다 짧게 설정)",
    )
    p.add_argument(
        "--no-reconnect",
        action="store_true",
        help="연결 끊김 시 재연결하지 않음",
    )
    p.add_argument(
        "--list-models",
        action="store_true",
        help="Ollama 설치 모델 목록 출력 후 종료",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="디버그 로그 출력",
    )

    return p.parse_args()


async def main() -> None:
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Ollama 모델 목록 확인
    if args.list_models:
        try:
            models = await list_ollama_models(args.ollama_url)
            if models:
                print("설치된 Ollama 모델:")
                for m in models:
                    print(f"  • {m}")
            else:
                print("설치된 모델이 없습니다. `ollama pull <model>` 로 먼저 설치하세요.")
        except Exception as e:
            print(f"Ollama 연결 실패: {e}")
            print(f"Ollama가 {args.ollama_url} 에서 실행 중인지 확인하세요.")
        return

    # 필수 인자 검증
    if not args.agent_id:
        print("오류: --agent-id 가 필요합니다")
        sys.exit(1)

    # Ollama 연결 확인 + 모델 선택
    try:
        models = await list_ollama_models(args.ollama_url)
    except Exception as e:
        logger.error("Ollama 연결 실패 (%s): %s", args.ollama_url, e)
        logger.error("Ollama가 실행 중인지 확인하세요: ollama serve")
        sys.exit(1)

    if not models:
        logger.error("Ollama에 설치된 모델이 없습니다. `ollama pull <model>` 로 설치하세요.")
        sys.exit(1)

    model = args.model or models[0]
    if model not in models:
        logger.warning("모델 '%s' 이 목록에 없습니다. 사용 가능 모델: %s", model, ", ".join(models))
        logger.warning("계속 진행합니다...")
    else:
        logger.info("Ollama 모델 선택: %s", model)

    # JWT 토큰 확보
    # server URL에서 ws:// → http:// 변환
    http_base = args.server.replace("ws://", "http://").replace("wss://", "https://")
    # ws_base는 ws:// 또는 wss://
    ws_base = args.server.replace("http://", "ws://").replace("https://", "wss://")

    if args.token:
        token = args.token
    elif args.nickname and args.password:
        logger.info("로그인 중: %s", args.nickname)
        token = await get_token(http_base, args.nickname, args.password)
        logger.info("로그인 성공")
    else:
        print("오류: --token 또는 (--nickname + --password) 가 필요합니다")
        sys.exit(1)

    # 시스템 프롬프트 로드
    system_prompt = args.system_prompt
    if not system_prompt and args.system_prompt_file:
        try:
            with open(args.system_prompt_file, encoding="utf-8") as f:
                system_prompt = f.read()
            logger.info("시스템 프롬프트 파일 로드: %s", args.system_prompt_file)
        except OSError as e:
            logger.warning("시스템 프롬프트 파일 로드 실패: %s", e)

    # 에이전트 실행
    await run_agent(
        ws_base=ws_base,
        agent_id=args.agent_id,
        token=token,
        model=model,
        ollama_url=args.ollama_url,
        system_prompt=system_prompt,
        turn_timeout=args.timeout,
        reconnect=not args.no_reconnect,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n에이전트를 종료합니다.")
