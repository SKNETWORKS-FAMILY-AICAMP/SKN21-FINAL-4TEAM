# ws_manager.py 모듈 명세

**파일 경로:** `backend/app/services/debate/ws_manager.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

로컬(자체 WebSocket 클라이언트) 에이전트의 WebSocket 연결 관리를 담당하는 싱글톤 클래스다. 턴 요청/응답 흐름, 툴 요청 중계, Redis 프레즌스 기반 멀티 워커 지원, 자동 재연결 처리를 포함한다.

---

## 주요 상수

| 상수 | 값 | 설명 |
|---|---|---|
| `_PRESENCE_PREFIX` | `"debate:agent:"` | Redis 프레즌스 키 접두사 |
| `_PRESENCE_TTL` | `60` | 프레즌스 키 TTL (초). heartbeat 갱신 주기보다 길게 설정 |
| `_PUBSUB_CHANNEL` | `"debate:agent:messages"` | 멀티 워커 메시지 전달용 Redis pub/sub 채널 |

---

## WSConnectionManager

싱글톤. `get_instance()`로 접근.

생성자: `__init__(self)` (내부 상태: `_connections`, `_pending_turns`, `_agent_active_turn`, `_pubsub_task`)

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `get_instance` | `() -> WSConnectionManager` | 싱글톤 인스턴스 반환 |
| `connect` | `(agent_id: UUID, ws: WebSocket) -> None` | WebSocket 등록 + Redis 프레즌스 설정. 기존 stale 연결 정리 후 새 연결 등록. pending Queue 보존 |
| `disconnect` | `(agent_id: UUID) -> None` | 연결 해제 + Redis 프레즌스 삭제 + 활성 Queue에 `_disconnect` 신호 전달 |
| `is_connected` | `(agent_id: UUID) -> bool` | 로컬 메모리 기반 연결 상태 확인 |
| `request_turn` | `(match_id, agent_id, request: WSTurnRequest, tool_executor, tool_context) -> WSTurnResponse` | 턴 요청 전송. `turn_response` 수신까지 `tool_request` 처리 루프 실행. 타임아웃은 caller의 `asyncio.wait_for()` 담당 |
| `handle_message` | `(agent_id: UUID, data: dict) -> None` | 수신 메시지 처리. `turn_response`/`tool_request`는 활성 Queue에 전달. `pong`은 프레즌스 갱신 |
| `send_match_ready` | `(agent_id: UUID, msg: WSMatchReady) -> None` | `match_ready` 전송. 로컬 연결 없으면 Redis pub/sub으로 다른 워커에 전달 |
| `send_error` | `(agent_id: UUID, message: str, code: str \| None) -> None` | 에러 메시지 전송 (연결 없으면 무시) |
| `send_ping` | `(agent_id: UUID) -> None` | ping 전송. 실패 시 `disconnect()` 호출 |
| `check_presence` | `(agent_id: UUID) -> bool` | 메모리 + Redis 이중 확인. 다른 워커에 연결된 에이전트도 감지 |
| `wait_for_connection` | `(agent_id: UUID, wait_timeout: float) -> bool` | 에이전트 접속 대기. 지수 백오프(0.5→1→2→최대 5초) 폴링 |
| `start_pubsub_listener` | `() -> None` | Redis pub/sub 리스너 시작 (lifespan에서 호출) |
| `stop_pubsub_listener` | `() -> None` | Redis pub/sub 리스너 중지 |
| `_cleanup_stale_connection` | `(agent_id, stale_ws) -> None` | stale WebSocket 안전 종료. pending Queue 보존 |
| `_handle_tool_request` | `(agent_id, data, tool_executor, tool_context) -> None` | tool_request 처리 후 tool_result 전송 |
| `_set_presence` | `(agent_id, connected: bool) -> None` | Redis 프레즌스 키 설정/삭제. `setex(key, 60, "1")` 또는 `delete(key)` |
| `_publish_to_agent` | `(agent_id, payload: dict) -> None` | Redis pub/sub으로 다른 워커의 에이전트에 메시지 전달 |
| `_pubsub_loop_with_restart` | `() -> None` | pub/sub 루프. 예외 종료 시 지수 백오프(1→2→…최대 60초)로 자동 재시작 |
| `_pubsub_loop` | `() -> None` | Redis pub/sub 수신 루프. `target_agent_id` 기반 로컬 에이전트에 페이로드 전달 |

---

## 내부 상태

| 속성 | 타입 | 설명 |
|---|---|---|
| `_connections` | `dict[UUID, WebSocket]` | agent_id → WebSocket 매핑 |
| `_pending_turns` | `dict[str, asyncio.Queue]` | `"{match_id}:{turn_number}:{speaker}"` → Queue |
| `_agent_active_turn` | `dict[UUID, str]` | agent_id → 현재 활성 턴 key (툴 메시지 라우팅용) |
| `_pubsub_task` | `asyncio.Task \| None` | Redis pub/sub 리스너 태스크 |

---

## 턴 요청/응답 흐름

```
engine._execute_turn()
  → ws_manager.request_turn(match_id, agent_id, WSTurnRequest, tool_executor, ctx)
      1. key = "{match_id}:{turn_number}:{speaker}"
      2. asyncio.Queue 생성, _pending_turns[key] 등록
      3. ws.send_json(WSTurnRequest) 또는 Redis pub/sub 발행
      4. 메시지 루프:
         - turn_response → WSTurnResponse 반환
         - tool_request → _handle_tool_request() → tool_result 전송 → 루프 계속
         - _disconnect → ConnectionError 발생
      5. finally: Queue 및 active_turn 정리
```

---

## Redis 키 구조

| 키 패턴 | 용도 |
|---|---|
| `debate:agent:{agent_id}:connected` | 프레즌스 (TTL 60초, 값 "1") |
| `debate:agent:messages` | 멀티 워커 메시지 pub/sub 채널 |

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `starlette.websockets` | `WebSocket`, `WebSocketState` |
| `app.schemas.debate_ws` | `WSMatchReady`, `WSTurnRequest`, `WSTurnResponse` |
| `app.services.debate.tool_executor` | `DebateToolExecutor`, `ToolContext` |
| `app.core.redis` | `redis_client` (지연 임포트) |

---

## 호출 흐름

```
API 라우터 (api/debate_ws.py)
  → WSConnectionManager.get_instance()
  → connect(agent_id, ws)         # JWT 인증 후 연결 등록
  → handle_message(agent_id, data) # 수신 메시지 처리 루프
  → disconnect(agent_id)           # 연결 종료

engine.py (_execute_turn, local 에이전트)
  → wait_for_connection(agent_id, timeout)
  → send_match_ready(agent_id, WSMatchReady)
  → request_turn(match_id, agent_id, WSTurnRequest, tool_executor, ctx)

main.py (lifespan)
  → start_pubsub_listener()
  → stop_pubsub_listener()
```

---

## 에러 처리

| 상황 | 동작 |
|---|---|
| 로컬 연결 없고 Redis 프레즌스도 없음 | `ConnectionError` 발생 |
| 에이전트 턴 중 연결 해제 | `_disconnect` 신호 → `ConnectionError` 발생 |
| send_json 실패 | `logger.warning` 후 무시 (send_error는 `contextlib.suppress` 사용) |
| Redis 프레즌스 업데이트 실패 | `logger.debug` 후 무시 |
| pub/sub 루프 크래시 | 지수 백오프 후 자동 재시작 |

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
