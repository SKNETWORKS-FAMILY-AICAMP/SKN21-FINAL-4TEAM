# engine.py 모듈 명세

> 비동기 백그라운드 태스크로 토론 매치를 실행하는 핵심 엔진

**파일 경로:** `backend/app/services/debate/engine.py`
**최종 수정일:** 2026-03-12

---

## 모듈 목적

비동기 백그라운드 태스크로 토론 매치를 실행하는 핵심 엔진이다. LLM 호출(또는 WebSocket) 기반 턴 실행, 코드 기반 벌점 부여, 오케스트레이터 검토 병렬화, 최종 판정, ELO/시즌 갱신, SSE 이벤트 발행의 전 과정을 조율한다. 매치 시작·완료 시점에 알림 훅(`NotificationService`)을 별도 세션으로 호출한다.

---

## 주요 상수

| 상수 | 값 | 설명 |
|---|---|---|
| `RESPONSE_SCHEMA_INSTRUCTION` | 문자열 | 에이전트 LLM에 주입하는 JSON 응답 형식 지시문. `_execute_turn()` 내 user 메시지 끝에 추가됨 |
| `PENALTY_SCHEMA_VIOLATION` | `5` | `validate_response_schema()` 실패 시 부여 (JSON 파싱 불가 또는 필드 누락) |
| `PENALTY_REPETITION` | `3` | `detect_repetition()`이 단어 중복 70% 이상 감지 시 부여 |
| `PENALTY_TIMEOUT` | `5` | 턴 타임아웃 초과 또는 LLM 호출 에러 시 부여 |
| `PENALTY_FALSE_SOURCE` | `7` | `tool_result`를 실제 도구 호출 없이 허위로 반환한 경우 |
| `PENALTY_TOKEN_LIMIT` | `3` | `finish_reason="length"` (응답 절삭) 시 부여 |

> 코드 기반 벌점은 LLM 검토 이전에 즉시 적용된다. LLM 기반 벌점은 `debate_orchestrator.LLM_VIOLATION_PENALTIES`를 참조한다.

---

## 모듈 수준 함수

### 공개 함수

| 함수 | 시그니처 | 설명 |
|---|---|---|
| `detect_repetition` | `(new_claim: str, previous_claims: list[str], threshold: float = 0.7) -> bool` | 단어 집합 유사도로 동어반복 감지. `overlap / max(len_new, len_prev) >= threshold`이면 True. threshold=0.7은 오탐율 고려값 |
| `validate_response_schema` | `(response_text: str) -> dict \| None` | 에이전트 응답 JSON 파싱 및 스키마 검증. `action`, `claim` 필수. 유효하면 dict, 아니면 None |
| `run_debate` | `(match_id: str) -> None` | 매치 실행 진입점. `create_async_engine`으로 독립 DB 세션 생성 후 알림 훅 2개 실행 및 `_execute_match` 호출 |

### 내부 함수

| 함수 | 시그니처 | 설명 |
|---|---|---|
| `_log_orchestrator_usage` | `(db, user_id, model_str, input_tokens, output_tokens, model_cache, usage_batch) -> None` | 오케스트레이터 LLM 토큰을 `token_usage_logs`에 기록. `model_cache`로 반복 SELECT 방지. `usage_batch` 지정 시 배치 모드로 일괄 INSERT |
| `_resolve_api_key` | `(agent: DebateAgent, force_platform: bool = False) -> str` | API 키 해결. 우선순위: BYOK 복호화 → 플랫폼 환경변수 → 빈 문자열. `force_platform=True`이면 BYOK 무시. 테스트 매치에서 항상 True로 전달됨 |
| `_publish_turn_event` | `(match_id: str, turn: DebateTurnLog, review_result=None) -> None` | `turn` 타입 SSE 이벤트 발행 |
| `_publish_review_event` | `(match_id: str, turn_number: int, speaker: str, review: dict) -> None` | `turn_review` 타입 SSE 이벤트 발행 |
| `_apply_review_to_turn` | `(turn, review, claims, penalty_total, update_last_claim=False) -> int` | 리뷰 결과를 `DebateTurnLog`에 반영하고 누적 벌점 반환. `update_last_claim=True`는 parallel 모드에서 이미 append된 `claims[-1]`을 차단본으로 패치 |
| `_handle_forfeit` | `(db, match, loser_agent, winner_agent, side) -> None` | 몰수패 처리. 상태 갱신, ELO 계산, 시즌 갱신, `forfeit` SSE 이벤트 발행 포함 |
| `_finalize_match` | `(db, match, judgment, agent_a, agent_b, orchestrator, model_cache, usage_batch, use_optimized) -> None` | 판정 결과 DB 저장 및 후속 처리 전체 조율 |
| `_run_turn_loop` | `(db, match, topic, agent_a, agent_b, version_a, version_b, key_a, key_b, client, orchestrator, model_cache, usage_batch, parallel) -> tuple[list[str], list[str], int, int]` | 턴 루프 실행. `parallel=True`이면 롤링 병렬 모드 |
| `_execute_match` | `(db: AsyncSession, match_id: str) -> None` | 매치 전체 흐름 조율. pending → in_progress → 턴 루프 → 판정 → completed |
| `_run_match_with_client` | `(db, match, topic, agent_a, agent_b, version_a, version_b, key_a, key_b, client) -> None` | `InferenceClient`가 주입된 상태에서 멀티에이전트/1v1 분기 처리 |
| `_execute_turn` | `(db, client, match, topic, turn_number, speaker, agent, version, api_key, my_claims, opponent_claims, my_accumulated_penalty) -> DebateTurnLog` | 단일 턴 실행. LLM 스트리밍 또는 WebSocket 요청 후 코드 기반 벌점 부여 |
| `_build_messages` | `(system_prompt, topic, turn_number, speaker, my_claims, opponent_claims) -> list[dict]` | 에이전트에게 보낼 메시지 컨텍스트 구성. 최근 4턴 히스토리 포함. 턴 단계별 전략 힌트 추가 |
| `_load_turns` | `(db: AsyncSession, match_id) -> list[DebateTurnLog]` | 매치의 전체 턴 로그 조회 (turn_number, speaker ASC) |
| `_execute_multi_and_finalize` | `(match, topic, db, client, orchestrator, agent_a, agent_b) -> None` | 2v2/3v3 라운드 로빈 실행 및 결과 처리. 기존 `_execute_turn()` 재사용 |

---

## 허용 action 값

`validate_response_schema()`가 검증하는 에이전트 응답 action 종류:

| action | 의미 |
|---|---|
| `argue` | 새로운 주장 또는 추가 근거 제시 |
| `rebut` | 상대 논거 직접 반박 |
| `concede` | 상대 논거 일부 인정, 핵심 입장 유지 |
| `question` | 상대 전제/근거 의문 제기 |
| `summarize` | 논점 정리/마무리 압축 |

---

## 호출 흐름

### run_debate() 전체 흐름

```
run_debate(match_id)
  │
  ├─ 1. [알림 훅 — 매치 시작 직전]
  │      async with session_factory() as notify_db:
  │          NotificationService(notify_db).notify_match_event(match_id, "match_started")
  │          notify_db.commit()
  │      (실패 시 warning 로그 후 계속 진행)
  │
  ├─ 2. async with session_factory() as db:
  │       _execute_match(db, match_id)
  │         ├─ DebateMatch, DebateTopic, DebateAgent, DebateAgentVersion 배치 조회
  │         ├─ local 에이전트 있으면 WS 연결 대기
  │         │   └─ 타임아웃 시 _handle_forfeit() → return
  │         ├─ 크레딧 차감 (credit_system_enabled 시)
  │         ├─ match.status = "in_progress", started_at 갱신, commit
  │         ├─ SSE "started" 이벤트 발행
  │         └─ async with InferenceClient() as client:
  │               _run_match_with_client(...)
  │                 ├─ 멀티에이전트 포맷이면 _execute_multi_and_finalize() → return
  │                 └─ _run_turn_loop(parallel=orchestrator.optimized)
  │                     └─ [턴 루프 — 아래 참조]
  │                 → orchestrator.judge()
  │                 → _finalize_match()
  │                     [판정 후처리 — 아래 참조]
  │
  ├─ 3. [정상 완료 후 — else 블록]
  │      [알림 훅 — 매치 완료]
  │      async with session_factory() as notify_db:
  │          NotificationService(notify_db).notify_match_event(match_id, "match_finished")
  │          notify_db.commit()
  │      (실패 시 warning 로그 후 계속 진행)
  │
  └─ 4. engine.dispose()
```

> 알림 훅은 두 지점 모두 핵심 경로 세션(`db`)과 **별도 세션**을 사용한다. 알림 실패가 매치 실행을 중단시키지 않도록 `try/except`로 감싸져 있다.

### 턴 루프 흐름 (parallel=True — 롤링 병렬 모드)

```
for turn_num in 1..max_turns:
  1. (이전 턴 B 리뷰 태스크가 있으면) await prev_b_review_task → _apply_review_to_turn()
  2. _execute_turn(agent_a) → turn_a 생성
  3. claims_a.append(turn_a.claim)
  4. _publish_turn_event(turn_a)  ← B 스트리밍 직전에 A 이벤트 먼저 발행
  5. asyncio.create_task(orchestrator.review_turn(agent_a))  ← 백그라운드 시작
  6. _execute_turn(agent_b) → turn_b 생성  ← A 검토와 병렬 실행
  7. claims_b.append(turn_b.claim)
  8. _publish_turn_event(turn_b)  ← A 검토 완료를 기다리지 않아 지연 없음
  9. asyncio.create_task(orchestrator.review_turn(agent_b))  ← 다음 턴 A와 병렬
  10. await review_a_task → _apply_review_to_turn() + _publish_review_event()

루프 종료 후: await prev_b_review_task (마지막 B 리뷰 수집)
```

### 판정 후처리 흐름 (_finalize_match)

```
_finalize_match(...)
  1. Judge LLM 토큰 usage_batch에 추가
  2. calculate_elo() → ELO 계산
  3. match.status = "completed", scorecard/score 저장
  4. is_test=False인 경우:
     a. DebateAgentService.update_elo() × 2 (A, B)
     b. match.season_id 있으면 DebateSeasonService.update_season_stats() × 2
     c. DebatePromotionService.record_match_result() (활성 시리즈 있는 경우)
     d. series_updates → SSE "series_update" 이벤트 발행
  5. SSE "finished" 이벤트 발행 (ELO 전후값 포함)
  6. DB UPDATE (elo_a_before/after, elo_b_before/after)
  7. usage_batch 일괄 INSERT + db.commit()
  8. DebateMatchService.resolve_predictions() → 예측투표 정산
  9. match.tournament_id 있으면 DebateTournamentService.advance_round()
  10. debate_summary_enabled이면 asyncio.create_task(generate_summary_task())
```

---

## 의존 모듈

| 모듈 | 가져오는 대상 | 용도 |
|---|---|---|
| `app.core.config` | `settings` | 턴 수, 타임아웃, 토큰 한도, 모델명 등 |
| `app.core.encryption` | `decrypt_api_key` | BYOK 키 복호화 |
| `app.models.debate_agent` | `DebateAgent`, `DebateAgentVersion` | 에이전트/버전 ORM |
| `app.models.debate_match` | `DebateMatch` | 매치 ORM |
| `app.models.debate_topic` | `DebateTopic` | 토픽 ORM |
| `app.models.debate_turn_log` | `DebateTurnLog` | 턴 로그 ORM |
| `app.models.llm_model` | `LLMModel` | 토큰 비용 계산용 모델 조회 |
| `app.models.token_usage_log` | `TokenUsageLog` | 토큰 사용량 기록 |
| `app.models.user` | `User` | 크레딧 차감 |
| `app.schemas.debate_ws` | `WSMatchReady`, `WSTurnRequest` | WebSocket 메시지 스키마 |
| `app.services.debate.agent_service` | `DebateAgentService` | ELO/전적 갱신 |
| `app.services.debate.broadcast` | `publish_event` | SSE 이벤트 발행 |
| `app.services.debate.match_service` | `DebateMatchService`, `generate_summary_task`, `calculate_token_cost` | 예측 정산, 요약 태스크, 비용 계산 |
| `app.services.debate.orchestrator` | `DebateOrchestrator`, `calculate_elo` | 턴 검토 + ELO 공식 |
| `app.services.debate.promotion_service` | `DebatePromotionService` | 승급전/강등전 결과 반영 (지연 임포트) |
| `app.services.debate.season_service` | `DebateSeasonService` | 시즌 ELO 갱신 (지연 임포트) |
| `app.services.debate.tool_executor` | `DebateToolExecutor`, `ToolContext`, `AVAILABLE_TOOLS` | 에이전트 Tool Call 실행 |
| `app.services.debate.tournament_service` | `DebateTournamentService` | 토너먼트 라운드 진행 (지연 임포트) |
| `app.services.debate.ws_manager` | `WSConnectionManager` | 로컬 에이전트 WebSocket |
| `app.services.llm.inference_client` | `InferenceClient` | LLM 스트리밍 호출 |
| `app.services.notification_service` | `NotificationService` | 매치 시작/완료 알림 발송 (지연 임포트) |

---

## 에러 처리

| 상황 | 처리 방식 |
|---|---|
| 턴 타임아웃 (`TimeoutError`) | `[TIMEOUT: No response within time limit]` 클레임으로 대체, `PENALTY_TIMEOUT` 부여 |
| LLM 호출 에러 | `[ERROR: ...]` 클레임으로 대체, `PENALTY_TIMEOUT` 부여 |
| JSON 형식 오류 | `PENALTY_SCHEMA_VIOLATION` 부여, 원문 앞 500자를 claim으로 대체 |
| 토큰 절삭 (`finish_reason="length"`) | `PENALTY_TOKEN_LIMIT` 부여, JSON 파싱 가능이면 정상 처리 |
| 로컬 에이전트 접속 불가 | `_handle_forfeit()` → 상대방 몰수승 처리 후 return |
| 매치 태스크 취소 (`CancelledError`) | `asyncio.shield`로 DB 롤백 후 status=`"error"` 기록, SSE `"error"` 이벤트 발행, 예외 재발생 |
| 매치 전체 크래시 (`Exception`) | DB 롤백, status=`"error"` 기록, SSE `"error"` 이벤트 발행 |
| 알림 훅 실패 | warning 로그 후 계속 진행 (매치 실행 중단하지 않음) |
| 리뷰 태스크 실패 | `orchestrator._review_fallback()` 결과로 대체 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
| 2026-03-12 | v2.1 | run_debate() 알림 훅 2개 명시, NotificationService 의존 모듈 추가, _run_turn_loop 롤링 병렬 패턴 상세화 | Claude |
