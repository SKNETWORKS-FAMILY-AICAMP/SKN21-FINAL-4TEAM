# broadcast.py 모듈 명세

**파일 경로:** `backend/app/services/debate/broadcast.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

Redis Pub/Sub 기반 SSE 브로드캐스트를 담당한다. 매치 관전자에게 토론 진행 이벤트를 실시간으로 전달하는 매치 채널과, 매칭 큐 대기자에게 상태 변경을 알리는 큐 채널 두 가지로 구성된다.

---

## 주요 상수

| 상수 | 값 | 설명 |
|---|---|---|
| `_TERMINAL_EVENTS` | `{"matched", "timeout", "cancelled"}` | 큐 채널 스트림 종료 이벤트 |
| `_MATCH_TERMINAL_EVENTS` | `{"finished", "error", "forfeit"}` | 매치 채널 스트림 종료 이벤트 |
| `_PRESENCE_PREFIX` (없음) | — | 관전자 수 추적 Redis 키 패턴: `debate:viewers:{match_id}` |

---

## 함수 목록

### 매치 관전 (SSE)

| 함수 | 시그니처 | 설명 |
|---|---|---|
| `publish_event` | `(match_id: str, event_type: str, data: dict) -> None` | 토론 이벤트를 Redis 채널 `debate:match:{match_id}`에 발행. 공유 `redis_client` 사용 |
| `subscribe` | `(match_id: str, user_id: str, max_wait_seconds: int = 600) -> AsyncGenerator[str, None]` | Redis pub/sub 구독 후 SSE 형식 문자열을 yield. 관전자 수 Redis Set으로 추적. 타임아웃 시 error 이벤트 발행 후 종료 |

### 매칭 큐 (SSE)

| 함수 | 시그니처 | 설명 |
|---|---|---|
| `publish_queue_event` | `(topic_id: str, agent_id: str, event_type: str, data: dict) -> None` | 큐 이벤트를 채널 `debate:queue:{topic_id}:{agent_id}`에 발행 |
| `subscribe_queue` | `(topic_id: str, agent_id: str, max_wait_seconds: int = 120) -> AsyncGenerator[str, None]` | 큐 채널 구독. 종료 이벤트 수신 또는 120초 타임아웃 시 스트림 종료 |

### 내부 함수

| 함수 | 시그니처 | 설명 |
|---|---|---|
| `_channel` | `(match_id: str) -> str` | `"debate:match:{match_id}"` 채널명 생성 |
| `_queue_channel` | `(topic_id: str, agent_id: str) -> str` | `"debate:queue:{topic_id}:{agent_id}"` 채널명 생성 |
| `_poll_pubsub` | `(pubsub, terminal_events: set, deadline: float) -> AsyncGenerator[str, None]` | 공통 폴링 루프. 0.05s 즉시 폴링 후 없으면 2.0s 블로킹. terminal_events 수신 또는 deadline 초과 시 종료 |

---

## subscribe 관전자 추적 방식

- 구독 시작: `SADD debate:viewers:{match_id} {user_id}` + `EXPIRE 3600`
- 구독 종료(finally): `SREM debate:viewers:{match_id} {user_id}`
- Redis Set을 사용하므로 같은 사용자가 새로고침해도 중복 카운트되지 않음

---

## SSE 이벤트 형식

```
data: {"event": "<event_type>", "data": {...}}\n\n
: heartbeat\n\n
```

heartbeat는 메시지가 없을 때 2.0초마다 발행되어 연결 유지에 사용된다.

---

## Redis 채널 구조

| 채널 패턴 | 용도 |
|---|---|
| `debate:match:{match_id}` | 매치 관전자용 이벤트 스트림 |
| `debate:queue:{topic_id}:{agent_id}` | 큐 대기자별 이벤트 스트림 |
| `debate:viewers:{match_id}` | 관전자 수 추적 (Set) |

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.core.redis` | `redis_client` (발행용), `pubsub_client` (구독용) |

---

## 호출 흐름

```
engine.py
  → publish_event(match_id, "turn", {...})      # 턴 완료
  → publish_event(match_id, "finished", {...})  # 매치 종료

matching_service.py
  → publish_queue_event(topic_id, agent_id, "opponent_joined", {...})
  → publish_queue_event(topic_id, agent_id, "matched", {...})

API 라우터 (debate_matches.py)
  → subscribe(match_id, user_id)  # SSE 스트리밍 엔드포인트

API 라우터 (debate_topics.py)
  → subscribe_queue(topic_id, agent_id)  # 큐 대기 SSE 엔드포인트
```

---

## 에러 처리

- 관전자 수 추적 Redis 오류: `logger.warning` 후 계속 진행 (토론 중단 없음)
- `_poll_pubsub` JSON 파싱 오류: `logger.warning` 후 계속 폴링
- `max_wait_seconds` 초과: error/timeout 이벤트 발행 후 generator 종료

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
