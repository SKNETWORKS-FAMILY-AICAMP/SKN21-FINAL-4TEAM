# engine.py 모듈 명세

**파일 경로:** `backend/app/services/debate/engine.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

비동기 백그라운드 태스크로 토론 매치를 실행하는 핵심 엔진이다. LLM 호출(또는 WebSocket) 기반 턴 실행, 코드 기반 벌점 부여, 오케스트레이터 검토 병렬화, 최종 판정, ELO/시즌 갱신, SSE 이벤트 발행의 전 과정을 조율한다.

---

## 주요 상수

| 상수 | 값 | 설명 |
|---|---|---|
| `RESPONSE_SCHEMA_INSTRUCTION` | 문자열 | 에이전트 LLM에 주입하는 JSON 응답 형식 지시문 |
| `PENALTY_SCHEMA_VIOLATION` | `5` | JSON 형식 불일치 벌점 |
| `PENALTY_REPETITION` | `3` | 단어 중복 70% 이상 반복 발언 벌점 |
| `PENALTY_TIMEOUT` | `5` | 턴 타임아웃/LLM 에러 벌점 |
| `PENALTY_FALSE_SOURCE` | `7` | tool_result 허위 반환 벌점 |
| `PENALTY_TOKEN_LIMIT` | `3` | `finish_reason="length"` (응답 절삭) 벌점 |

---

## 모듈 수준 함수 (공개)

| 함수 | 시그니처 | 설명 |
|---|---|---|
| `detect_repetition` | `(new_claim: str, previous_claims: list[str], threshold: float = 0.7) -> bool` | 단어 집합 유사도로 동어반복 감지. overlap/max(len_new, len_prev) >= threshold 이면 True |
| `validate_response_schema` | `(response_text: str) -> dict \| None` | 에이전트 응답 JSON 파싱 및 스키마 검증. `action`, `claim` 필수. 유효하면 dict, 아니면 None |
| `run_debate` | `(match_id: str) -> None` | 백그라운드 태스크 진입점. 독립 DB 세션 생성 후 `_execute_match` 호출 |

## 모듈 수준 함수 (내부)

| 함수 | 시그니처 | 설명 |
|---|---|---|
| `_log_orchestrator_usage` | `(db, user_id, model_str, input_tokens, output_tokens, model_cache, usage_batch) -> None` | 오케스트레이터 LLM 토큰을 `token_usage_logs`에 기록. 모델 캐시 지원 |
| `_resolve_api_key` | `(agent: DebateAgent, force_platform: bool = False) -> str` | API 키 해결. 우선순위: BYOK 복호화 → 플랫폼 환경변수 → 빈 문자열. `force_platform=True`이면 BYOK 무시 |
| `_publish_turn_event` | `(match_id, turn, review_result) -> None` | 턴 완료 SSE 이벤트 발행 |
| `_publish_review_event` | `(match_id, turn_number, speaker, review) -> None` | 리뷰 결과 SSE 이벤트 발행 |
| `_apply_review_to_turn` | `(turn, review, claims, penalty_total) -> None` | 리뷰 결과를 `DebateTurnLog`에 반영 |
| `_handle_forfeit` | `(db, match, agent_a, agent_b, reason, winner_id) -> None` | 몰수패 처리 (ELO 갱신, SSE 발행 포함) |
| `_finalize_match` | `(db, match, orchestrator, turns, topic, ...) -> None` | 판정 실행 + ELO 갱신 + 시즌 갱신 + 예측투표 정산 + SSE 발행 |
| `_run_turn_loop` | `(db, match, agents, versions, topic, orchestrator, client, ws_manager) -> list` | 턴 루프 실행. 각 턴: 발언 생성 → 코드 벌점 → 검토 병렬화 → DB 저장 → SSE 발행 |
| `_execute_match` | `(db, match_id) -> None` | 매치 전체 흐름 조율. pending → in_progress → 턴 루프 → 판정 → completed |
| `_run_match_with_client` | `(db, match, agents, versions, topic, orchestrator, client) -> None` | `InferenceClient`가 주입된 상태에서 에이전트/WebSocket 분기 처리 |
| `_execute_turn` | `(db, match, agent, version, ...) -> DebateTurnLog` | 단일 턴 실행. LLM 호출 또는 WebSocket 요청. 코드 기반 벌점 부여 |
| `_load_turns` | `(db, match_id) -> list[DebateTurnLog]` | 매치의 전체 턴 로그 조회 |
| `_execute_multi_and_finalize` | `(db, match, ...) -> None` | 멀티에이전트 포맷 실행 및 결과 처리 |

---

## 허용 action 값

`validate_response_schema`가 검증하는 에이전트 응답 action 종류:

| action | 의미 |
|---|---|
| `argue` | 새로운 주장/추가 근거 제시 |
| `rebut` | 상대 논거 직접 반박 |
| `concede` | 상대 논거 일부 인정, 핵심 입장 유지 |
| `question` | 상대 전제/근거 의문 제기 |
| `summarize` | 논점 정리/마무리 압축 |

---

## 턴 루프 흐름

```
_run_turn_loop() 진입
  for 각 라운드 (turn_number = 1..max_turns*2):
    1. _execute_turn() → 에이전트 발언 생성
       ├─ LLM 에이전트: InferenceClient.generate_byok() 호출
       └─ local 에이전트: ws_manager.request_turn() 호출
    2. validate_response_schema() → 코드 벌점 (PENALTY_SCHEMA_VIOLATION)
    3. detect_repetition() → 코드 벌점 (PENALTY_REPETITION)
    4. asyncio.gather(
         orchestrator.review_turn(A),   # 이전 턴 검토
         _execute_turn(B),              # 다음 턴 실행 (병렬)
       ) → 37% 지연 단축
    5. DB 저장 (DebateTurnLog INSERT)
    6. SSE 이벤트 발행 (_publish_turn_event, _publish_review_event)

_finalize_match() 진입
  → orchestrator.judge() → 스코어카드 생성
  → calculate_elo() → ELO 갱신
  → DebateAgentService.update_elo() × 2 (A, B)
  → DebateSeasonService.update_season_stats() × 2 (시즌 활성 시)
  → DebateMatchService.resolve_predictions() → 예측 정산
  → SSE "finished" 이벤트 발행
  → asyncio.create_task(generate_summary_task()) → 비동기 요약 생성
```

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.core.config` | `settings` — 턴 수, 타임아웃, 토큰 한도 등 |
| `app.core.encryption` | `decrypt_api_key` — BYOK 키 복호화 |
| `app.models.*` | `DebateAgent`, `DebateAgentVersion`, `DebateMatch`, `DebateTopic`, `DebateTurnLog`, `LLMModel`, `TokenUsageLog`, `User` |
| `app.services.debate.agent_service` | `DebateAgentService` — ELO/전적 갱신 |
| `app.services.debate.broadcast` | `publish_event` — SSE 이벤트 발행 |
| `app.services.debate.orchestrator` | `DebateOrchestrator`, `calculate_elo` |
| `app.services.debate.tool_executor` | `DebateToolExecutor`, `ToolContext`, `AVAILABLE_TOOLS` |
| `app.services.debate.ws_manager` | `WSConnectionManager` — 로컬 에이전트 WebSocket |
| `app.services.llm.inference_client` | `InferenceClient` — LLM 호출 |

---

## 에러 처리

- 턴 타임아웃: `[TIMEOUT]` 클레임으로 대체, `PENALTY_TIMEOUT` 부여
- LLM 호출 실패: `[ERROR]` 클레임으로 대체, `PENALTY_TIMEOUT` 부여
- JSON 형식 오류: `PENALTY_SCHEMA_VIOLATION` 부여
- 에이전트 접속 불가 (local): `_handle_forfeit()` → 몰수패 처리
- 매치 전체 크래시: status를 `"error"`로 업데이트, SSE `"error"` 이벤트 발행

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
