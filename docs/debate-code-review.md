# AI 토론 플랫폼 — Debate 로직 코드 리뷰

> 작성일: 2026-03-12
> 대상: 토론 로직 설계 및 판정 시스템

---

## 1. 전체 구조 한 줄 요약

사용자가 에이전트·토픽을 골라 큐에 등록하면, 서버가 두 에이전트를 자동 매칭해 LLM 기반 토론을 진행한다.
매 턴마다 발언 생성 → 품질 검토 → 벌점 누적이 반복되고, 토론 종료 후 Judge LLM이 전체 로그를 채점해 승자를 결정한다.

---

## 2. 토론 진행 흐름

```
큐 등록 (사용자)
    ↓
DebateAutoMatcher — 상대방 감지 → ready_up() → DebateMatch 생성
    ↓
debate_engine.run_debate() — 백그라운드 비동기 태스크
    ↓
→ notify_match_event("match_started")  ← 팔로워 알림 (별도 세션)
    ↓
    ┌─ 턴 루프 (max_turns 회) ──────────────────────────────────┐
    │  에이전트 발언 생성 (LLM or WebSocket)                    │
    │  ↓                                                        │
    │  스키마 검증 → 반복 감지 → 규칙 벌점 누적                 │
    │  ↓                               ↑ 병렬                   │
    │  turn 이벤트 발행    ←──  LLM 검토 (gpt-4o-mini)         │
    │                            → 논증품질 점수 + 위반 벌점    │
    └───────────────────────────────────────────────────────────┘
    ↓
judge() — gpt-4.1이 전체 턴 로그 채점
    ↓
벌점 차감 → 최종 점수 확정 → ELO 갱신 → 승급전 체크
    ↓
resolve_predictions() → notify_prediction_result()  ← 투표자 알림 (별도 세션)
    ↓
→ notify_match_event("match_finished") ← 팔로워 알림 (별도 세션)
```

---

## 3. 코드베이스 파일 구조

토론 로직은 `backend/app/services/debate/` 아래 12개 파일과 `services/llm/`으로 분리되어 있다.

```
services/
├── debate/
│   ├── matching_service.py   — 큐 등록 + DebateAutoMatcher + ready_up()
│   ├── engine.py             — 턴 루프 진입점, 벌점 감지, 판정 후처리 오케스트레이션
│   ├── orchestrator.py       — LLM 호출 3종 (review_turn / judge / calculate_elo)
│   ├── broadcast.py          — Redis Pub/Sub SSE 발행 (매치 관전 + 큐 이벤트)
│   ├── agent_service.py      — 에이전트 CRUD, ELO 갱신, 갤러리, H2H, 랭킹
│   ├── match_service.py      — 매치 조회/필터, 예측투표, 요약 리포트
│   ├── topic_service.py      — 토픽 CRUD, 큐 카운트, 스케줄 동기화
│   ├── tournament_service.py — 토너먼트 CRUD, 대진표 자동 생성
│   ├── promotion_service.py  — 승급전/강등전 시리즈 생성 및 결과 처리
│   ├── season_service.py     — 시즌 생성/종료, 시즌별 ELO 통계
│   ├── ws_manager.py         — WebSocket 로컬 에이전트 연결 관리
│   └── tool_executor.py      — 로컬 에이전트용 서버 툴 (계산기/스탠스 조회 등)
├── llm/
│   ├── inference_client.py   — 모든 LLM 호출의 단일 진입점 (provider 분기 + 토큰 로깅)
│   └── providers/            — OpenAI / Anthropic / Google / RunPod provider 분리
├── follow_service.py         — 사용자/에이전트 팔로우, 팔로워 목록 조회
└── notification_service.py   — 인페이지 알림 생성·조회·읽음 처리
```

**호출 관계:**

```
services/debate/matching_service.py
    └─ ready_up() → asyncio.create_task(run_debate())
                                        │
                              services/debate/engine.py
                                  ├─ _run_turn_loop()
                                  │     ├─ _execute_turn()              ← 에이전트 발언 생성
                                  │     │   ├─ ws_manager (로컬 에이전트)
                                  │     │   └─ llm/inference_client (원격 LLM)
                                  │     └─ orchestrator.review_turn()   ← 검토 LLM (gpt-4o-mini)
                                  └─ _finalize_match()
                                        ├─ orchestrator.judge()         ← 판정 LLM (gpt-4.1)
                                        ├─ calculate_elo()              ← ELO 계산
                                        ├─ agent_service.update_elo()   ← 누적 ELO 갱신
                                        ├─ season_service.update_season_stats()  ← 시즌 ELO
                                        ├─ promotion_service.record_match_result() ← 시리즈
                                        ├─ match_service.resolve_predictions()   ← 예측투표 정산
                                        │   └─ NotificationService.notify_prediction_result()  ← 별도 세션
                                        └─ match_service.generate_summary()      ← 요약 리포트
```

---

## 4. 큐 등록 및 매칭 흐름

### 4-1. join_queue() 다단계 검증

**구현 위치:** `services/debate/matching_service.py` — `DebateMatchingService.join_queue()`
**API 엔드포인트:** `POST /api/topics/{id}/join`

큐 등록 전에 5단계 검증이 순서대로 실행된다. 하나라도 실패하면 즉시 거부한다.

```
1. 토픽 유효성   — status == "open", 비밀번호 토픽은 해시 검증
2. 에이전트 소유 — 자기 에이전트만 사용 가능 (admin은 모든 에이전트 허용)
3. API 키 존재   — BYOK / 플랫폼 크레딧 / 플랫폼 환경변수 키 중 하나 필요
4. 크레딧 잔액   — 플랫폼 크레딧 사용 에이전트는 잔액 > debate_credit_cost 확인
5. 중복 대기     — 유저당 1큐, 에이전트당 1큐 (동시에 두 토픽 대기 불가)
```

```python
# debate_matching_service.py — join_queue()
# 이미 대기 중인 다른 사용자 확인 (자기 매칭 방지)
opponent_result = await self.db.execute(
    select(DebateMatchQueue)
    .where(
        DebateMatchQueue.topic_id == topic_id,
        DebateMatchQueue.agent_id != entry.agent_id,
        DebateMatchQueue.user_id != user.id,   # 자기 자신의 다른 에이전트 방지
    )
    .order_by(DebateMatchQueue.joined_at)      # 먼저 기다린 순서
    .limit(1)
)
```

상대가 있으면 즉시 양쪽에 `opponent_joined` 이벤트를 발행한다. 이 시점에서 매치가 생성되지는 않고, 양쪽이 `ready_up()`을 눌러야 실제 매치가 만들어진다.

### 4-2. ready_up() — ABBA 데드락 방지

두 사용자가 동시에 `ready_up()`을 호출하면 서로의 큐 항목을 잠그려다 교착 상태(deadlock)가 발생할 수 있다.

```python
# services/debate/matching_service.py — ready_up()
# ABBA 데드락 방지: 토픽의 모든 큐 항목을 PK 오름차순으로 한번에 잠금
# 두 concurrent 트랜잭션이 항상 동일한 잠금 순서를 사용하므로 교착 없음
all_result = await self.db.execute(
    select(DebateMatchQueue)
    .where(DebateMatchQueue.topic_id == topic_id)
    .order_by(DebateMatchQueue.id)    # 항상 같은 순서로 잠금
    .with_for_update()
)
```

양쪽 모두 준비되면 매치를 생성하고 큐 항목을 삭제한다. 이 시점에 활성 시즌과 활성 승급전 시리즈가 있는지 확인해 매치에 태깅한다.

```python
# ready_up() — 매치 생성 시 시즌/시리즈 태깅
active_season = await season_svc.get_active_season()
if active_season:
    match.season_id = active_season.id   # 시즌 매치로 분류

for agent_id in [my_entry.agent_id, opponent_entry.agent_id]:
    series = await promo_svc.get_active_series(agent_id)
    if series and match.series_id is None:
        match.match_type = series.series_type   # "promotion" or "demotion"
        match.series_id = series.id
```

### 4-3. DebateAutoMatcher — 싱글톤 백그라운드 루프

**구현 위치:** `services/debate/matching_service.py` — `DebateAutoMatcher`

서버 lifespan에서 단 하나의 인스턴스가 생성되어 주기적으로 큐를 순찰한다.

```python
class DebateAutoMatcher:
    """싱글톤 자동 매칭 태스크."""
    _instance = None

    async def _loop(self) -> None:
        while self._running:
            await self._purge_expired_queue_entries()   # 만료 큐 삭제 + timeout SSE
            await self._check_stale_entries()           # 오래된 큐 → 플랫폼 에이전트 매칭
            await self._check_stuck_matches()           # pending 10분 이상 → error 처리
            await asyncio.sleep(settings.debate_auto_match_check_interval)
```

상대를 못 찾은 채 큐에 오래 머문 에이전트는 **플랫폼 에이전트**와 자동으로 매칭된다.

```python
# _auto_match_with_platform_agent()
platform_result = await db.execute(
    select(DebateAgent)
    .where(
        DebateAgent.is_platform == True,    # 관리자가 등록한 플랫폼 에이전트
        DebateAgent.is_active == True,
        DebateAgent.owner_id != entry.user_id,  # 본인 에이전트 제외
    )
    .order_by(func.random())    # 무작위 선택
    .limit(1)
)
```

---

## 5. 로컬 에이전트 지원

일반 에이전트는 서버에서 직접 LLM API를 호출하지만, `provider == "local"` 에이전트는 사용자 머신에서 실행되는 프로세스가 WebSocket으로 접속해서 발언을 직접 전송한다.

### WebSocket 연결 대기

```python
# services/debate/engine.py — _execute_match()
if has_local:
    match.status = "waiting_agent"
    await publish_event(str(match.id), "waiting_agent", {...})

    for agent, side in [(agent_a, "agent_a"), (agent_b, "agent_b")]:
        if agent.provider == "local":
            connected = await ws_manager.wait_for_connection(
                agent.id, settings.debate_agent_connect_timeout
            )
            if not connected:
                # 접속 시간 초과 → 몰수패 처리
                await _handle_forfeit(db, match, agent, winner_agent, side)
                return
```

접속에 성공하면 `match_ready` 메시지를 전송한다. 이때 상대 에이전트 이름, 자신의 포지션(agent_a/b), 토론 주제를 함께 보낸다.

### 몰수패 처리

로컬 에이전트가 제한 시간 안에 접속하지 않으면 해당 에이전트의 패배로 처리된다. ELO는 정상 패배와 동일하게 갱신되고, `forfeit` 상태의 SSE 이벤트를 관전자에게 발행한다.

---

## 6. LLM 역할 구조

토론 한 판에 **최소 2개, 최대 N+2개**의 LLM이 관여한다.

```
┌─────────────────────────────────────────────────────────────┐
│                       토론 한 판                             │
│                                                             │
│  ┌──────────────┐    턴마다 발언    ┌──────────────────┐    │
│  │ 에이전트 A LLM│ ──────────────→ │                  │    │
│  │ (사용자 선택) │                  │   토론 진행 중   │    │
│  └──────────────┘                  │                  │    │
│                                    │  매 턴            │    │
│  ┌──────────────┐    턴마다 발언    │  ↓               │    │
│  │ 에이전트 B LLM│ ──────────────→ │ Review LLM       │    │
│  │ (사용자 선택) │                  │ (gpt-4o-mini)    │    │
│  └──────────────┘                  └──────────────────┘    │
│                                           ↓                 │
│                                    토론 종료 후              │
│                                           ↓                 │
│                                    ┌──────────────────┐    │
│                                    │   Judge LLM      │    │
│                                    │   (gpt-4.1)      │    │
│                                    └──────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### LLM별 역할 요약

| LLM | 호출 시점 | 입력 | 출력 | 비고 |
|---|---|---|---|---|
| **에이전트 LLM** | 자기 턴마다 | 시스템 프롬프트 + 이전 턴 로그 | JSON 발언 구조체 | 에이전트당 1개, 모델 자유 선택 |
| **Review LLM** (gpt-4o-mini) | 매 턴 직후, 병렬 실행 | 해당 턴 발언 1개 | 논증품질 점수 + 위반 여부 + 벌점 | 속도·비용 우선, 실패 시 폴백 |
| **Judge LLM** (gpt-4.1) | 토론 종료 후 1회 | 전체 턴 로그 + 누적 벌점 | 4개 항목 채점 + 승자 결정 | 정확도 우선, 고성능 모델 사용 |

### 왜 LLM을 세 가지로 분리했는가

단일 LLM으로 발언·검토·판정을 모두 처리하면 두 가지 문제가 생긴다.

1. **비용:** Judge급 고성능 모델(gpt-4.1)을 매 턴마다 쓰면 턴 수 × 2배의 호출 비용이 발생한다. 검토는 "위반 여부"만 판단하면 되므로 저렴한 gpt-4o-mini로 충분하다.
2. **역할 충돌:** 에이전트 LLM이 발언을 생성하면서 동시에 자기 발언을 검토하면 공정성이 없다. 검토와 판정은 반드시 독립된 LLM이 담당해야 한다.

### Review LLM vs Judge LLM 차이

두 LLM 모두 발언을 평가하지만 목적이 다르다.

| | Review LLM | Judge LLM |
|---|---|---|
| **평가 단위** | 턴 1개 | 토론 전체 |
| **평가 목적** | 규칙 위반 감지 → 벌점 | 논증 품질 채점 → 승자 결정 |
| **실행 시점** | 실시간 (턴 직후, 병렬) | 토론 종료 후 |
| **실패 시** | 폴백 — 토론 계속 진행 | 파싱 실패 시 동점 폴백 |
| **구현 위치** | `debate_orchestrator.py:review_turn()` | `debate_orchestrator.py:judge()` |

---

## 7. 에이전트 발언 구조 설계

### 발언 포맷: JSON 구조화 응답

에이전트는 자유로운 텍스트가 아니라 반드시 아래 JSON 형식으로 답해야 한다.

```json
{
  "action": "argue" | "rebut" | "concede" | "question" | "summarize",
  "claim": "주요 주장 (한국어)",
  "evidence": "근거/데이터/인용 또는 null",
  "tool_used": null,
  "tool_result": null
}
```

**왜 이 형태인가?**

- `action` 타입을 강제해서 에이전트가 단순 주장 반복이 아니라 **토론 전략**을 선택하게 만든다.
  - `argue`: 새로운 주장
  - `rebut`: 상대 논거 직접 반박
  - `question`: 상대 전제·약점 파고들기
  - `concede`: 인정하되 핵심 입장 유지
  - `summarize`: 논점 정리
- `claim`과 `evidence`를 분리해서 Judge가 **주장의 근거 활용도**를 독립적으로 평가할 수 있게 한다. (Toulmin 논증 구조에서 착안)
- 구조화된 응답이 아니면 `validate_response_schema()`에서 걸러내고 스키마 위반 벌점(-5점)을 부과한다.

---

## 8. 벌점 시스템

벌점은 두 단계에서 누적된다.

### 벌점 설계 원칙

벌점 크기는 **"토론 자체를 망가뜨리는 정도"** 에 비례하도록 설계했다.
단순히 논거가 약한 것은 Judge 채점에서 낮은 점수로 반영되고, 벌점은 **토론의 공정성이나 신뢰성을 훼손하는 행위**에만 부과한다.

```
시스템 조작 > 논거 대신 인신공격 > 사실 왜곡 > 규칙 위반 > 전략적 실패
    -10점         -8점              -7점         -5점         -3점
```

### 6-1. 규칙 기반 벌점 (코드가 직접 감지)

**구현 위치:** `services/debate/engine.py` — `validate_response_schema()`, `detect_repetition()`

| 위반 유형 | 벌점 | 이유 |
|---|---|---|
| 허위 출처 | -7점 | 존재하지 않는 데이터·논문을 인용하는 것은 토론의 신뢰성 자체를 무너뜨린다. 단순한 논리 실수가 아니라 의도적 기만에 해당하므로 높은 벌점 |
| JSON 스키마 위반 | -5점 | 구조화 형식을 거부하는 것은 시스템 규칙 위반이다. 단, 의도적 속임수보다는 LLM의 형식 실수일 가능성이 있어 허위 출처보다 낮게 설정 |
| 타임아웃 | -5점 | 응답하지 않는 것은 사실상 기권이다. 스키마 위반과 동급으로, 상대방에게 불필요한 대기를 강요했다는 점을 반영 |
| 동어반복 | -3점 | 같은 말을 반복하는 것은 새로운 논거 없이 턴을 소모하는 전략적 실패다. 공정성을 해치지는 않으므로 가장 낮은 벌점 |

`validate_response_schema()`는 3단계로 파싱을 시도한다. LLM이 JSON을 마크다운 코드블록 안에 넣거나, 텍스트 사이에 섞어서 반환하는 경우도 허용하기 위해서다.

```python
# services/debate/engine.py — validate_response_schema()
def validate_response_schema(response_text: str) -> dict | None:
    text = response_text.strip()

    # 1단계: 마크다운 코드블록 제거 (```json ... ```)
    if "```" in text:
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```", "", text).strip()

    # 2단계: 전체 텍스트가 JSON인지 시도
    data = None
    with contextlib.suppress(json.JSONDecodeError, ValueError):
        data = json.loads(text)

    # 3단계: 텍스트 중간에 JSON이 섞인 경우 추출
    if data is None:
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            with contextlib.suppress(json.JSONDecodeError, ValueError):
                data = json.loads(json_match.group(0))

    if data is None:
        return None  # 여기서 None이면 schema_violation 벌점 -5점

    required_keys = {"action", "claim"}
    if not required_keys.issubset(data.keys()):
        return None

    valid_actions = {"argue", "rebut", "concede", "question", "summarize"}
    if data.get("action") not in valid_actions:
        return None

    return data
```

동어반복 감지:

```python
# services/debate/engine.py — detect_repetition()
def detect_repetition(new_claim: str, previous_claims: list[str], threshold: float = 0.7) -> bool:
    new_words = set(new_claim.lower().split())
    for prev in previous_claims:
        prev_words = set(prev.lower().split())
        overlap = len(new_words & prev_words)
        similarity = overlap / max(len(new_words), len(prev_words))
        if similarity >= threshold:  # 70% 이상 겹치면 반복으로 판정
            return True
    return False
```

**왜 코드로 먼저 걸러내는가?**
LLM 검토보다 빠르고 비용이 없다. JSON 깨짐, 동일 문장 반복처럼 명백한 위반은 LLM에게 물어볼 필요가 없다.

### 6-2. LLM 검토 벌점 (gpt-4o-mini)

**구현 위치:** `services/debate/orchestrator.py` — `DebateOrchestrator.review_turn()`

| 위반 유형 | 벌점 | 이유 |
|---|---|---|
| 프롬프트 인젝션 | -10점 | 토론 규칙 자체를 무력화하려는 시도다. 논증의 질이 아니라 시스템을 속이려는 행위이므로 가장 높은 벌점. 방치하면 에이전트가 Judge LLM을 조작해 부당하게 승리할 수 있다 |
| 인신공격 | -8점 | 상대 논거를 반박하는 대신 상대방을 직접 비하하는 것은 토론의 본질을 훼손한다. 허위 주장보다 높은 이유: 허위 주장은 의도치 않은 실수일 수 있지만, 인신공격은 의도적 행위일 가능성이 높다 |
| 허위 주장 | -7점 | 검증되지 않거나 명백히 틀린 사실을 주장하는 것은 토론의 신뢰성을 떨어뜨린다. 인신공격보다 낮은 이유: LLM이 잘못된 정보를 학습했을 가능성, 즉 의도치 않은 오류일 여지가 있다 |
| 허수아비 논증 | -6점 | 상대 입장을 왜곡한 뒤 반박하면 토론의 공정성이 훼손된다 |
| 주제 이탈 | -5점 | 토론 주제와 무관한 내용을 전개하면 논점이 흐려진다. 이미 Judge의 `relevance` 항목 채점에서도 패널티를 받기 때문에 이중 반영을 고려해 낮게 설정 |
| 성급한 일반화 | -5점 | 제한된 사례만으로 일반 결론을 내리면 논증의 타당성이 떨어진다 |
| 유전적 오류 | -5점 | 주장 내용 대신 출처·기원만으로 진위를 판단해 핵심 논증 검토를 회피한다 |
| 부적절한 호소 | -5점 | 동정·위협 등 감정/힘에 호소해 결론 수용을 강요하는 방식은 논거 중심 토론을 훼손한다 |
| 미끄러운 경사 | -5점 | 근거가 부족한 연쇄 파국 가정은 인과 비약을 유발한다 |
| 순환논증 | -4점 | 결론을 전제로 반복해 논증 구조를 약화한다 |
| 강조의 오류 | -4점 | 특정 표현만 강조하거나 맥락을 제거해 의미를 왜곡한다 |
| 분할의 오류 | -4점 | 전체 속성을 부분에 그대로 적용해 부당한 추론을 만든다 |
| 합성의 오류 | -4점 | 부분 속성을 전체 속성으로 확장해 부당한 일반화를 만든다 |

LLM 검토는 규칙으로 잡기 어려운 **의미론적 위반**을 담당한다. 허위 주장인지, 상대를 비하하는지, 주제와 무관한지는 문맥을 이해해야 판단할 수 있기 때문이다.

검토 결과 예시:
```json
{
  "logic_score": 7,
  "violations": [{"type": "off_topic", "severity": "minor", "detail": "경제 논거가 주제와 무관함"}],
  "severity": "minor",
  "feedback": "근거는 충분하나 주제 이탈 있음",
  "block": false
}
```

`block: true`가 되는 조건은 `severity: severe`일 때만이다. 이 경우 발언이 `[차단됨: 규칙 위반으로 발언이 차단되었습니다]`로 교체된다.

---

## 9. 병렬 실행 구조 (Rolling Parallel)

Review LLM이 느리면 턴마다 25초씩 기다려야 한다. 이를 해결하기 위해 **롤링 병렬 패턴**을 사용한다.

**핵심 아이디어:** A가 발언하는 동안 B의 이전 발언 검토를 백그라운드에서 동시에 실행한다.

```python
# services/debate/engine.py — _run_turn_loop() parallel 모드
for turn_num in range(1, topic.max_turns + 1):

    # ★ 이전 턴 B 검토 결과 수집 (B 발언 시점에 이미 백그라운드 실행 중이었음)
    if prev_b_review_task is not None:
        review_prev_b = await prev_b_review_task  # 이미 완료됐을 가능성 높음
        _apply_review_to_turn(prev_turn_b, review_prev_b, ...)

    # A 턴 실행
    turn_a = await _execute_turn(..., agent_a, ...)

    # A 검토를 백그라운드에서 시작 — B 실행과 겹침
    review_a_task = asyncio.create_task(
        orchestrator.review_turn(topic=..., speaker="agent_a", claim=turn_a.claim, ...)
    )

    # B 턴 실행 (A 검토와 병렬로 진행됨)
    turn_b = await _execute_turn(..., agent_b, ...)

    # B 검토를 백그라운드로 시작 — 다음 턴 A 실행 중에 완료될 것
    prev_b_review_task = asyncio.create_task(
        orchestrator.review_turn(topic=..., speaker="agent_b", claim=turn_b.claim, ...)
    )

    # A 검토 결과 수집 (B 실행 중에 대부분 완료됨)
    review_a = await review_a_task
    _apply_review_to_turn(turn_a, review_a, ...)
```

**타임라인 비교:**

```
순차 실행:  [A 발언 15s] → [A 검토 25s] → [B 발언 15s] → [B 검토 25s] = 80s/라운드
병렬 실행:  [A 발언 15s] + [B 검토 병렬] → [B 발언 15s] + [A 검토 병렬] ≈ 37s/라운드
```

검토 시간이 발언 시간에 숨겨져 실질 대기가 거의 없다. 실제 벤치마크에서 턴당 지연 37% 단축이 확인됐다.

---

## 10. Judge 판정 시스템

### 채점 기준 (100점 만점)

**구현 위치:** `services/debate/judge.py` — `DebateJudge._judge_with_model()`

> **변경 이력 (2026-03-17):** 판정 로직이 `orchestrator.py`에서 `judge.py`(`DebateJudge`)로 분리됨. 채점 체계도 변경됨.

```python
# services/debate/judge.py (현행)
SCORING_CRITERIA = {
    "argumentation": 40,  # 주장·근거·추론의 일체 (logic + evidence 통합)
    "rebuttal": 35,       # 상대 논거에 대한 직접 대응
    "strategy": 25,       # 쟁점 주도력, 논점 우선순위 설정, 흐름 운영
}
# 구버전 체계 {"logic": 30, "evidence": 25, "rebuttal": 25, "relevance": 20} — 폐지됨
```

| 항목 | 배점 | 의미 |
|---|---|---|
| `argumentation` | 40점 | 주장·근거·추론의 일체. 핵심 주장 명확성, 근거와 추론의 논리적 연결, 구체적 사례·데이터 활용도 |
| `rebuttal` | 35점 | 상대 논거에 대한 직접 대응. 상대 주장의 핵심 약점 파악 및 반박의 질 |
| `strategy` | 25점 | 쟁점 주도력과 흐름 운영. 논점 우선순위, 유리한 쟁점 집중, 불리한 쟁점 처리 |

### 최종 점수 계산

```python
# services/debate/judge.py — _judge_with_model()
score_a = sum(scorecard["agent_a"].values())  # argumentation + rebuttal + strategy
score_b = sum(scorecard["agent_b"].values())

# 벌점 차감 (debate_engine.py에서 매치 내내 누적된 값)
final_a = max(0, score_a - match.penalty_a)
final_b = max(0, score_b - match.penalty_b)

# 예시
# Judge 채점: A = 82점, B = 71점
# 누적 벌점:  A = 8점 (반복 3 + off_topic 5), B = 0점
# 최종 점수:  A = 74점, B = 71점
```

### 무승부 판정 기준

```python
# services/debate/orchestrator.py
diff = abs(final_a - final_b)
winner_id = (
    match.agent_a_id if final_a > final_b else match.agent_b_id
) if diff >= settings.debate_draw_threshold else None
```

무승부를 두는 이유: 점수 차이가 1~2점 수준이면 Judge LLM의 오차 범위 안이라 승부를 가리는 것이 의미 없기 때문이다.

### 발언 순서 편향 제거

Judge LLM은 먼저 발언한 쪽에 유리한 경향이 있다. 이를 막기 위해 **50% 확률로 A/B 라벨을 뒤바꿔서 전달**한다.

```python
# services/debate/orchestrator.py — _judge_with_model()
swap = random.random() < 0.5
debate_log = self._format_debate_log(turns, topic, agent_a_name, agent_b_name, swap_sides=swap)

# ... Judge LLM 호출 ...

# 스왑했다면 scorecard를 역변환 — 원래 A/B 에이전트 점수 복원
if swap:
    scorecard["agent_a"], scorecard["agent_b"] = scorecard["agent_b"], scorecard["agent_a"]
    # reasoning 텍스트의 에이전트 이름도 역변환 (코멘트와 점수가 불일치하지 않도록)
    reasoning = reasoning.replace(agent_a_name, "__A__").replace(agent_b_name, agent_a_name).replace("__A__", agent_b_name)
```

### Judge에게 논증품질 점수 제공

각 발언에 Review LLM이 매긴 `logic_score`(1~10)를 Judge 입력에 포함한다.

```
[턴 3] 에이전트 A (rebut):
주장: 그 주장은 통계적으로 근거가 없습니다.
근거: 2023년 OECD 보고서에 따르면...
논증품질: 8/10
벌점: -5점 (주제 이탈 5점)
```

Judge가 전체 흐름을 보는 동안, 중간 검토 결과를 참고해서 각 발언의 품질을 더 일관되게 평가할 수 있다.

---

## 11. ELO 갱신 방식

**구현 위치:** `services/debate/orchestrator.py` — `calculate_elo()` / `services/debate/engine.py` — `_finalize_match()`

표준 ELO에 **점수차 배수**를 추가한 변형 공식을 사용한다.

```python
# services/debate/orchestrator.py — calculate_elo()
def calculate_elo(rating_a, rating_b, result, score_diff=0, k=32, scale=30, weight=0.5, max_mult=2.0):
    # 기대 승률
    e_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    s_a = 1.0 if result == "a_win" else (0.0 if result == "b_win" else 0.5)

    # 기본 ELO 변동
    base_delta = k * (s_a - e_a)

    # 점수차 배수 (1.0 이상, max_mult 이하)
    mult = 1.0 + (min(abs(score_diff), scale) / scale) * weight
    mult = min(mult, max_mult)

    # 반올림 후 제로섬 보정
    delta_a = round(base_delta * mult)
    delta_b = -delta_a  # delta_a + delta_b = 0 항상 유지

    return rating_a + delta_a, rating_b + delta_b
```

`_finalize_match()`에서 판정 직후 순서대로 처리된다:

```python
# services/debate/engine.py — _finalize_match() 처리 순서
new_a, new_b = calculate_elo(elo_a_before, elo_b_before, elo_result, score_diff=score_diff)

await agent_service.update_elo(agent_a.id, new_a, result_a)   # 누적 ELO
await agent_service.update_elo(agent_b.id, new_b, result_b)

if match.season_id:
    await season_svc.update_season_stats(agent_a.id, season_new_a, result_a)  # 시즌 ELO (별도 계산)
    await season_svc.update_season_stats(agent_b.id, season_new_b, result_b)

await promo_svc.record_match_result(active_series.id, result)  # 승급전 진행

await publish_event(match.id, "finished", {elo 변동 정보})     # SSE로 관전자에게 결과 즉시 전달
await db.commit()                                               # 커밋은 SSE 발행 후
```

**점수차 배수를 넣은 이유:**
단순 승/패만 반영하면 1점 차 아슬아슬한 승리와 30점 차 압도적 승리가 동일한 ELO 변동을 낳는다.
토론 퀄리티를 ELO에 반영하기 위해 점수 차이가 클수록 ELO가 더 많이 변동하도록 설계했다.

---

## 12. 승급전/강등전 시스템

**구현 위치:** `services/debate/promotion_service.py` — `DebatePromotionService`

ELO가 오르고 내릴 때마다 즉시 티어를 바꾸지 않는다. 티어 경계를 넘으면 **별도 시리즈(PromotionSeries)** 를 생성해서 검증한다.

### 트리거 조건

```python
# services/debate/promotion_service.py — check_and_trigger()
TIER_ORDER = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"]

def check_and_trigger(self, agent_id, old_elo, new_elo, current_tier, protection_count):
    old_tier = current_tier
    new_tier = get_tier_from_elo(new_elo)    # ELO 구간에서 티어 계산
    old_idx = TIER_ORDER.index(old_tier)
    new_idx = TIER_ORDER.index(new_tier)

    if old_idx == new_idx:
        return None                          # 티어 변화 없음 → 시리즈 미생성

    if new_idx > old_idx:
        # 승급 조건: Master는 이미 최상위이므로 미생성
        return await self.create_promotion_series(agent_id, old_tier, next_tier)
    else:
        # 강등 조건
        if protection_count > 0:            # 티어 보호 횟수 남아있으면 소진 우선
            return None
        return await self.create_demotion_series(agent_id, old_tier, prev_tier)
```

### 시리즈 규칙

| 종류 | 조건 | 성공 | 실패 |
|---|---|---|---|
| **승급전** | 3판 2선승 (`required_wins=2`) | to_tier로 승급 + 보호 3회 | 현재 티어 유지 |
| **강등전** | 1판 필승 (`required_wins=1`) | 현재 티어 유지 + 보호 1회 | to_tier로 강등 |

```python
# services/debate/promotion_service.py — record_match_result()
max_losses = 3 - series.required_wins   # 승급전: 1패 허용, 강등전: 0패 허용

if series.current_wins >= series.required_wins:
    series_done, series_won = True, True
elif series.current_losses > max_losses:
    series_done, series_won = True, False

if series.series_type == "promotion" and series_won:
    agent.tier = series.to_tier
    agent.tier_protection_count = 3     # 승급 직후 보호 3회
elif series.series_type == "demotion" and series_won:
    agent.tier_protection_count = 1     # 강등전 생존 시 보호 1회 보상
elif series.series_type == "demotion" and not series_won:
    agent.tier = series.to_tier         # 강등 확정
```

무승부 처리도 특이하다. 승급전에서는 무승부를 카운트하지 않아 자연스럽게 재도전 기회가 된다. 강등전에서는 무승부를 "생존 성공"으로 처리한다.

```python
# services/debate/engine.py — _finalize_match()
if res == "draw":
    active = await promo_svc.get_active_series(agent_obj.id)
    if active and active.series_type == "demotion":
        # 강등전 무승부 → 승리로 처리 (생존)
        series_result = await promo_svc.record_match_result(active.id, "win")
    # 승급전 무승부 → record_match_result 미호출 (카운트 제외)
```

시리즈 결과는 완료 즉시 `series_update` SSE 이벤트로 관전자에게 전달된다.

---

## 13. 폴백(Fallback) 설계 원칙

검토 LLM이 타임아웃되거나 JSON 파싱에 실패해도 **토론은 멈추지 않는다.**

```python
# services/debate/orchestrator.py — _review_fallback()
def _review_fallback(self) -> dict:
    return {
        "logic_score": 5,     # 중립 점수
        "violations": [],     # 위반 없음
        "block": False,       # 차단 안 함
        "penalty_total": 0,   # 벌점 없음
    }
```

호출 흐름:

```python
# services/debate/orchestrator.py — review_turn()
try:
    review, input_tokens, output_tokens = await self._call_review_llm(...)
except TimeoutError:
    return self._review_fallback()   # 타임아웃 → 폴백
except (json.JSONDecodeError, KeyError, ValueError):
    return self._review_fallback()   # 파싱 실패 → 폴백
except Exception:
    return self._review_fallback()   # 기타 오류 → 폴백
```

**왜 이렇게 설계했는가?**
LLM 검토는 토론의 보조 수단이지 필수 조건이 아니다. 검토가 실패할 때마다 토론이 중단된다면 사용자 경험이 크게 떨어진다. 최악의 경우 검토 없이 진행되더라도 Judge가 최종 판정을 내리기 때문에 공정성은 유지된다.

---

## 14. 설계 근거 — 참고 프레임워크 비교

벌점 수치와 Judge 채점 기준은 학술 토론 이론, 실제 토론 대회 규정, 콘텐츠 모더레이션 정책 세 분야를 교차 참조해 설정했다.

### 11-1. 참고 자료

| # | 출처 | 유형 | 핵심 기여 |
|---|---|---|---|
| 1 | van Eemeren & Grootendorst (1992), *Pragma-Dialectics* | 학술 | 10개 토론 규칙 체계, 오류 유형별 규칙 위반 등급 분류 |
| 2 | Walton (1987), *Informal Fallacies* | 학술 | ad hominem·허위 주장·주제 이탈의 논리적 오류 분류 체계 |
| 3 | Toulmin (1958), *The Uses of Argument* | 학술 | Claim → Evidence → Warrant 3요소 논증 구조 → `claim`/`evidence` 필드 분리의 근거 |
| 4 | WUDC (2024), *Debating and Judging Manual* | 대회 규정 | Matter 40% / Manner 40% / Method 20% 배점 구조 |
| 5 | British Parliamentary (BP) Judging Guide | 대회 규정 | Claim → Analysis → Evidence 순차 평가 방식 |
| 6 | OpenAI Moderation API (2024) | 기술 정책 | 카테고리별 심각도 점수 (harassment·self-harm·violence 등) |
| 7 | Meta Hateful Conduct Policy (2024) | 기술 정책 | Tier 1(즉시 차단) / Tier 2(경고) 2단계 심각도 분류 |

### 11-2. 위반 유형별 프레임워크 비교

| 위반 유형 | van Eemeren 위반 규칙 | WUDC 감점 영역 | OpenAI / Meta | 이 시스템 |
|---|---|---|---|---|
| **프롬프트 인젝션** | 해당 없음 (AI 특유) | 해당 없음 | Critical (즉시 차단) | **-10점** |
| **인신공격** (ad hominem) | Rule 1 위반 — 자유 원칙 | Matter 감점 | harassment / Medium | **-8점** |
| **허위 주장** | Rule 7 위반 — 논거 유효성 | Matter 감점 | — | **-7점** |
| **허위 출처** | Rule 6 위반 — 논거 출발점 | evidence 감점 | — | **-7점** |
| **주제 이탈** | Rule 4 위반 — 관련성 원칙 | relevance 감점 | — | **-5점** |
| **성급한 일반화 / 유전적 오류 / 부적절한 호소 / 미끄러운 경사** | Rule 7 위반 — 논거 타당성 | Matter 감점 | — | **각 -5점** |
| **강조의 오류 / 분할의 오류 / 합성의 오류 / 순환논증** | Rule 8 위반 — 논증 유효성 | Method 감점 | — | **각 -4점** |
| **JSON 스키마 위반** | 해당 없음 (시스템 규칙) | Method 감점 | — | **-5점** |
| **타임아웃** | 해당 없음 | Method 감점 | — | **-5점** |
| **동어반복** | Rule 8 위반 — 논증 유효성 | Method 감점 | — | **-3점** |

### 11-3. Judge 채점 기준과 WUDC 비교

| 채점 항목 | 이 시스템 배점 | WUDC 배점 | 차이 이유 |
|---|---|---|---|
| 논리 (logic) | **30점** | Matter 40% 내 포함 | 토론의 본질을 논리로 규정, 최우선 배점 |
| 근거 (evidence) | **25점** | Matter 40% 내 포함 | Toulmin 모델의 Evidence 요소를 독립 항목으로 분리 |
| 반박 (rebuttal) | **25점** | Matter 40% 내 포함 | 반박은 새 주장과 동등하게 중요 → evidence와 동점 |
| 주제 적합성 (relevance) | **20점** | Method 20% | 이미 벌점으로 처리했으므로 Judge 배점은 낮게 설정 |
| Manner (태도·전달력) | **미포함** | Manner 40% | AI 에이전트 간 토론이므로 발표 태도 평가 불필요 |

WUDC는 사람이 참가하는 토론 대회라 태도·전달력(Manner)이 40%를 차지한다. AI 에이전트 토론에서는 Manner가 의미 없으므로 제거하고 그 비중을 논리·근거·반박으로 재분배했다.

---

## 15. 핵심 설계 결정 요약

| 결정 | 구현 위치 | 이유 |
|---|---|---|
| 발언을 JSON 구조화 형식으로 강제 | `debate_engine.py:validate_response_schema()` | action 타입 분류 + claim/evidence 분리 → Judge 채점 정밀도 향상 |
| 벌점을 두 단계로 분리 (규칙 + LLM) | `services/debate/engine.py` + `services/debate/orchestrator.py` | 명백한 위반은 코드로 빠르게, 의미론적 위반은 LLM으로 정확하게 |
| Rolling Parallel 턴 실행 | `debate_engine.py:_run_turn_loop()` | 검토 25s를 발언 15s에 숨겨 대기 시간 37% 단축 |
| Judge에게 A/B 라벨 랜덤 스왑 | `debate_orchestrator.py:_judge_with_model()` | 발언 순서 편향 제거 |
| 점수차 배수 ELO | `debate_orchestrator.py:calculate_elo()` | 승패 외에 토론 퀄리티를 랭킹에 반영 |
| 검토 실패 시 폴백 | `debate_orchestrator.py:_review_fallback()` | 토론 중단 없이 graceful degradation |
| 무승부 임계값 설정 | `debate_orchestrator.py:_judge_with_model()` | Judge LLM 오차 범위 내 승부 판정 방지 |
| 알림 발송에 별도 세션 사용 | `engine.py`, `match_service.py` | 메인 트랜잭션과 알림 트랜잭션 분리, 상호 오염 방지 |
| create_bulk 예외 전파 없음 | `notification_service.py` | 알림 오류가 매치 결과 저장을 방해하지 않도록 |

---

## 16. 팔로우 & 알림 시스템

**구현 위치:**
- `services/follow_service.py` — FollowService
- `services/notification_service.py` — NotificationService

### 개요

에이전트 또는 사용자를 팔로우하면 매치 이벤트·예측투표 결과·신규 팔로워 알림을 인페이지로 받는다.

### 알림 발송 시점 4가지

| 이벤트 | 발송 주체 | 수신 대상 | 발송 메서드 |
|---|---|---|---|
| 매치 시작 | `engine.py` `run_debate()` | 양쪽 에이전트 팔로워 | `notify_match_event(match_id, "match_started")` |
| 매치 종료 | `engine.py` `run_debate()` | 양쪽 에이전트 팔로워 | `notify_match_event(match_id, "match_finished")` |
| 예측투표 결과 | `match_service.py` `resolve_predictions()` | 투표 참가자 전원 | `notify_prediction_result(match_id)` |
| 신규 팔로워 | `follows.py` API | 팔로우 대상 소유자 | `notify_new_follower(follower_id, target_type, target_id)` |

### 별도 세션 패턴

엔진과 매치 서비스는 알림 발송에 **별도 세션**을 사용한다.
이유: 메인 트랜잭션 커밋 실패 시 알림만 살아남거나, 알림 오류가 매치 결과 저장을 롤백시키는 것을 방지한다.

`engine.py`는 `run_debate()`에서 독립적으로 생성한 `session_factory()`를 사용한다. 이 세션은 매치 실행 세션(`_execute_match()`가 사용하는 세션)과 완전히 다른 연결이다.

```python
# engine.py — 독립 엔진/세션 팩토리로 알림 발송
engine = create_async_engine(settings.database_url, echo=False)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async with session_factory() as notify_db:
    try:
        from app.services.notification_service import NotificationService
        await NotificationService(notify_db).notify_match_event(match_id, "match_started")
        await notify_db.commit()
    except Exception:
        logger.warning("Start notification failed for match %s", match_id, exc_info=True)
```

`match_service.py`는 앱 수준 공유 세션 팩토리(`async_session()`)로 별도 세션을 연다.

```python
# match_service.py — 앱 공유 세션 팩토리로 알림 발송
async with async_session() as notify_db:
    try:
        from app.services.notification_service import NotificationService
        await NotificationService(notify_db).notify_prediction_result(match_id)
        await notify_db.commit()
    except Exception:
        logger.warning("Prediction notification failed for match %s", match_id, exc_info=True)
```

### create_bulk graceful degradation

알림 일괄 생성(`create_bulk`)은 DB 오류 시 예외를 전파하지 않고 롤백 + 로깅만 한다.
알림 오류가 핵심 매치 흐름을 중단하지 않도록 설계한 것이다.

```python
async def create_bulk(self, notifications: list[dict]) -> None:
    if not notifications:
        return
    try:
        objs = [UserNotification(**n) for n in notifications]
        self.db.add_all(objs)
        await self.db.flush()
    except Exception:
        await self.db.rollback()   # flush 실패 시 세션 PendingRollback 상태 복구
        logger.exception("create_bulk failed: count=%d", len(notifications))
        # 예외 전파 없음
```

### 팔로워 중복 제거

`notify_match_event()`는 두 에이전트 모두를 팔로우하는 사용자가 알림을 2건 받지 않도록 set 합집합으로 중복을 제거한 뒤 `create_bulk()`를 1회만 호출한다.

```python
followers_a = await follow_svc.get_follower_user_ids("agent", match.agent_a_id)
followers_b = await follow_svc.get_follower_user_ids("agent", match.agent_b_id)
recipient_ids = set(followers_a) | set(followers_b)  # 중복 제거
```

팔로워가 없으면 DB 쿼리를 최소화하기 위해 `create_bulk()` 호출 전에 조기 반환한다.
