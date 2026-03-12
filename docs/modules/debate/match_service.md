# match_service.py 모듈 명세

**파일 경로:** `backend/app/services/debate/match_service.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

완료/진행 중 매치 조회, 예측투표 생성·집계·정산, 하이라이트 관리, 요약 리포트 생성을 담당한다. `DebateSummaryService`도 같은 파일에 포함되어 있다.

---

## 모듈 수준 함수

### `calculate_token_cost(tokens: int, cost_per_1m: Decimal) -> Decimal`
토큰 수와 백만 토큰당 비용으로 실제 비용 산출. `engine.py`도 이 함수를 임포트해 사용한다.

---

## DebateMatchService

생성자: `__init__(self, db: AsyncSession)`

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `get_match` | `(match_id: str) -> dict \| None` | 매치 상세 조회. 에이전트 배치 조회(N+1 방지) + 턴 카운트 포함 |
| `get_match_turns` | `(match_id: str) -> list[DebateTurnLog]` | 턴 로그 전체 (turn_number ASC) |
| `get_scorecard` | `(match_id: str) -> dict \| None` | 스코어카드 조회. `match.scorecard`가 None이면 None 반환 |
| `list_matches` | `(topic_id, agent_id, status, skip, limit, search, date_from, date_to, include_test) -> tuple[list[dict], int]` | 매치 목록 페이지네이션. 테스트 매치 기본 제외. 에이전트/토픽명 통합 검색. N+1 방지를 위해 에이전트 배치 조회 |
| `create_prediction` | `(match_id: str, user_id: UUID, prediction: str) -> dict` | 예측투표 생성. `in_progress` 상태 + `debate_prediction_cutoff_turns` 이내만 허용. 중복 시 IntegrityError 처리 |
| `get_prediction_stats` | `(match_id: str, user_id: UUID) -> dict` | 예측 집계(a_win/b_win/draw/total) + 내 투표 결과 반환 |
| `resolve_predictions` | `(match_id, winner_id, agent_a_id, agent_b_id) -> None` | 판정 후 `is_correct` 일괄 UPDATE |
| `get_summary_status` | `(match_id: str) -> dict` | 요약 상태 반환: `unavailable` / `generating` / `ready` |
| `toggle_featured` | `(match_id: str, featured: bool) -> dict` | 하이라이트 설정/해제. 완료 매치만 가능 (관리자 전용) |
| `list_featured` | `(limit: int = 5) -> tuple[list[dict], int]` | 하이라이트 매치 목록 (featured_at DESC). 테스트 매치 제외 |

### `_agent_from_map(agents_map: dict, agent_id) -> dict` (내부)
배치 조회된 `agents_map`에서 에이전트 요약 반환. 삭제된 에이전트는 `"[삭제됨]"` 표시.

---

## DebateSummaryService

생성자: `__init__(self, db: AsyncSession)`

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `generate_summary` | `(match_id: str) -> None` | 매치 완료 후 비동기 호출. 이미 `summary_report`가 있으면 스킵. `debate_summary_model`로 LLM 호출 후 `summary_report` JSONB에 저장. 토큰 사용량 기록 포함 |

### `generate_summary_task(match_id: str) -> None` (모듈 수준 standalone)
백그라운드 태스크 진입점. 앱 공유 `async_session`으로 독립 세션에서 `DebateSummaryService.generate_summary()` 호출.

---

## SUMMARY_SYSTEM_PROMPT 응답 형식

```json
{
  "key_arguments": ["핵심 논거 1", "핵심 논거 2", "핵심 논거 3"],
  "winning_points": ["승부 포인트 1", "승부 포인트 2"],
  "rule_violations": ["[에이전트명] 턴N: 위반유형(심각도) - 세부내용"],
  "overall_summary": "전체 토론 요약 (3-4문장)"
}
```

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.models.debate_agent` | `DebateAgent` |
| `app.models.debate_match` | `DebateMatch`, `DebateMatchPrediction` (지연 임포트) |
| `app.models.debate_topic` | `DebateTopic` |
| `app.models.debate_turn_log` | `DebateTurnLog` |
| `app.models.llm_model` | `LLMModel` — 요약 모델 조회 |
| `app.models.token_usage_log` | `TokenUsageLog` — 요약 LLM 토큰 기록 |
| `app.core.config` | `settings.debate_prediction_cutoff_turns`, `debate_summary_enabled`, `debate_summary_model` |
| `app.services.llm.inference_client` | `InferenceClient` — 요약 LLM 호출 |

---

## 호출 흐름

```
API 라우터 (api/debate_matches.py)
  → DebateMatchService.get_match()
  → DebateMatchService.create_prediction()
  → DebateMatchService.get_prediction_stats()
  → DebateMatchService.get_summary_status()

engine.py (_finalize_match)
  → DebateMatchService.resolve_predictions()
  → asyncio.create_task(generate_summary_task(match_id))

API 라우터 (api/admin/debate/matches.py)
  → DebateMatchService.toggle_featured()
  → DebateMatchService.list_featured()
```

---

## 에러 처리

| 상황 | 예외 | 설명 |
|---|---|---|
| 매치 미존재 | `ValueError("Match not found")` | HTTP 404 |
| 진행 중이 아닌 매치에 예측 | `ValueError("투표는 진행 중인 매치에서만...")` | HTTP 400 |
| 예측 기한 초과 | `ValueError("투표 시간이 지났습니다...")` | HTTP 400 |
| 중복 예측 | `ValueError("이미 예측에 참여했습니다")` | HTTP 409 (IntegrityError로도 처리) |
| 미완료 매치 하이라이트 설정 | `ValueError("완료된 매치만 하이라이트로...")` | HTTP 400 |

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
