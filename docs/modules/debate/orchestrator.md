# DebateOrchestrator

> 턴별 LLM 발언 검토 + 최종 판정 + ELO 계산을 담당하는 토론 오케스트레이터

**파일 경로:** `backend/app/services/debate/orchestrator.py`
**최종 수정일:** 2026-03-12

---

## 모듈 목적

세 가지 역할을 담당한다.

- **턴 검토** — 매 턴마다 경량 LLM(`debate_review_model`, 기본: `gpt-4o-mini`)으로 발언을 검토하여 논리 점수·위반 감지·벌점 산출·차단 여부를 반환한다.
- **최종 판정** — 모든 턴 완료 후 고정밀 LLM(`debate_judge_model`, 기본: `gpt-4.1`)으로 채점 스코어카드를 생성하고 승패를 결정한다. A/B 라벨 스왑으로 발언 순서 편향을 제거한다.
- **ELO 계산** — 모듈 수준 함수 `calculate_elo`가 표준 ELO + 점수차 배수 공식으로 매치 후 양측 레이팅을 반환한다.

`DebateOrchestrator` 단일 클래스에 위 세 역할이 통합되어 있으며, `optimized` 플래그로 모델 선택 경로를 분기한다.

---

## 주요 상수

| 상수 | 설명 |
|---|---|
| `PENALTY_KO_LABELS` | 벌점 키 → 한국어 라벨 매핑 (Judge LLM 프롬프트에 영문 파라미터 노출 방지용) |
| `SCORING_CRITERIA` | `{"logic": 30, "evidence": 25, "rebuttal": 25, "relevance": 20}` — 채점 항목별 최대 점수 |
| `JUDGE_SYSTEM_PROMPT` | Judge LLM 시스템 프롬프트. 100점 만점 채점, JSON 형식 응답 강제 |
| `LLM_VIOLATION_PENALTIES` | `{"prompt_injection": 10, "ad_hominem": 8, "false_claim": 7, "straw_man": 6, "off_topic": 5, "hasty_generalization": 5, "genetic_fallacy": 5, "appeal": 5, "slippery_slope": 5, "circular_reasoning": 4, "accent": 4, "division": 4, "composition": 4}` |
| `REVIEW_SYSTEM_PROMPT` | Review LLM 시스템 프롬프트. logic_score/violations/severity/feedback/block 포함 JSON 응답 강제 |

### PENALTY_KO_LABELS 항목

| 키 | 한국어 라벨 | 탐지 경로 |
|---|---|---|
| `schema_violation` | JSON 형식 위반 | engine.py 코드 기반 |
| `token_limit` | 토큰 제한 초과 | engine.py 코드 기반 |
| `repetition` | 주장 반복 | engine.py 코드 기반 |
| `llm_prompt_injection` | 프롬프트 인젝션(LLM) | review_turn() |
| `llm_ad_hominem` | 인신공격(LLM) | review_turn() |
| `llm_straw_man` | 허수아비 논증(LLM) | review_turn() |
| `llm_circular_reasoning` | 순환논증(LLM) | review_turn() |
| `llm_hasty_generalization` | 성급한 일반화(LLM) | review_turn() |
| `llm_accent` | 강조의 오류(LLM) | review_turn() |
| `llm_genetic_fallacy` | 유전적 오류(LLM) | review_turn() |
| `llm_appeal` | 부적절한 호소(LLM) | review_turn() |
| `llm_slippery_slope` | 미끄러운 경사(LLM) | review_turn() |
| `llm_division` | 분할의 오류(LLM) | review_turn() |
| `llm_composition` | 합성의 오류(LLM) | review_turn() |
| `llm_off_topic` | 주제 이탈(LLM) | review_turn() |
| `llm_false_claim` | 허위 주장(LLM) | review_turn() |

---

## 모듈 수준 함수

### `calculate_elo(rating_a: int, rating_b: int, result: str, score_diff: int = 0) -> tuple[int, int]`

표준 ELO + 판정 점수차 배수 공식으로 매치 후 양측 레이팅을 반환한다.

- `result`: `'a_win'` / `'b_win'` / `'draw'`
- `score_diff`: `abs(score_a - score_b)`, 0~100 범위
- 공식: `E_a = 1 / (1 + 10^((rating_b - rating_a) / 400))`, `mult = 1.0 + (score_diff / scale) × weight` (상한: `max_mult`)
- 설정값 참조: `debate_elo_k_factor`, `debate_elo_score_diff_scale`, `debate_elo_score_diff_weight`, `debate_elo_score_mult_max`
- 반환: `(new_rating_a, new_rating_b)` — 제로섬 (`delta_a + delta_b = 0`) 유지
- 호출자: `engine.py`의 `_finalize_match`

### `_infer_provider(model_id: str) -> str` (내부)

모델 ID 접두사로 provider를 추론한다. `claude` → `anthropic`, `gemini` → `google`, 나머지 → `openai`.

### `_platform_api_key(provider: str) -> str` (내부)

provider에 맞는 플랫폼 환경변수 API 키를 반환한다. `settings.anthropic_api_key` / `settings.google_api_key` / `settings.openai_api_key` 순서로 분기.

---

## 클래스: DebateOrchestrator

### 생성자

```python
def __init__(self, optimized: bool = True, client: InferenceClient | None = None) -> None
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `optimized` | `bool` | `True`: 경량 review 모델 + 고정밀 judge 모델 분리. `False`: `debate_orchestrator_model` 단일 모델 사용 |
| `client` | `InferenceClient \| None` | 외부 주입 시 커넥션 풀 재사용. `None`이면 내부에서 새로 생성하고 소유권 보유 |

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `aclose` | `() -> None` | 클라이언트를 자신이 소유(`_owns_client=True`)한 경우에만 닫기 |
| `review_turn` | `(topic, speaker, turn_number, claim, evidence, action, opponent_last_claim, recent_history) -> dict` | 단일 턴 LLM 품질 검토. API 키 없거나 타임아웃·파싱 실패 시 폴백 dict 반환 (토론 중단 없음) |
| `judge` | `(match, turns, topic, agent_a_name, agent_b_name) -> dict` | 토론 전체 판정. `optimized=True`이면 `debate_judge_model` 사용, `False`이면 `debate_orchestrator_model` 사용 |
| `_call_review_llm` | `(model_id, api_key, messages) -> tuple[dict, int, int]` | LLM 호출 → 마크다운 코드블록 제거 → JSON 파싱 → `(review_dict, input_tokens, output_tokens)` 반환. 실패 시 예외 전파 (호출자 폴백 처리) |
| `_build_review_result` | `(review, input_tokens, output_tokens, skipped) -> dict` | 파싱된 review dict를 최종 결과 dict로 변환. `LLM_VIOLATION_PENALTIES`로 벌점 산출. `skipped` 전달 시만 포함 |
| `_review_fallback` | `() -> dict` | 검토 실패 시 안전 폴백 반환 (`logic_score=5`, 위반 없음, `block=False`) |
| `_judge_with_model` | `(match, turns, topic, agent_a_name, agent_b_name, model_id) -> dict` | 지정 모델로 LLM 판정. 50% 확률 A/B 라벨 스왑으로 발언 순서 편향 제거. 파싱 실패 시 균등 반점 폴백 |
| `_format_debate_log` | `(turns, topic, agent_a_name, agent_b_name, swap_sides) -> str` | 턴 로그를 Judge LLM용 텍스트 블록으로 변환. 논증품질 점수·벌점·벌점 요약 섹션 포함 |
| `_format_violation_summary` | `(name, violations) -> str` | 에이전트 이름과 위반 횟수 dict를 Judge용 요약 문자열로 변환 |

### `review_turn` 반환 dict 구조

```python
{
    "logic_score": int,           # 1-10, LLM 평가 논리 점수
    "violations": list[dict],     # [{"type": str, "severity": "minor|severe", "detail": str}, ...]
    "feedback": str,              # 관전자용 한줄평 (30자 이내, 한국어)
    "block": bool,                # True이면 원문 차단 → blocked_claim으로 교체
    "penalties": dict[str, int],  # 위반 유형 → 벌점 (LLM_VIOLATION_PENALTIES 기반)
    "penalty_total": int,         # 벌점 합계
    "blocked_claim": str | None,  # block=True이면 "[차단됨: 규칙 위반으로 발언이 차단되었습니다]"
    "input_tokens": int,
    "output_tokens": int,
    "skipped": bool,              # optimized 모드에서만 포함 (False = 검토 수행됨)
}
```

### `judge` 반환 dict 구조

```python
{
    "scorecard": dict,      # {"agent_a": {logic, evidence, rebuttal, relevance}, "agent_b": {...}, "reasoning": str}
    "score_a": int,         # 벌점 차감 후 최종 점수 (0 이상)
    "score_b": int,
    "penalty_a": int,       # match.penalty_a
    "penalty_b": int,       # match.penalty_b
    "winner_id": UUID | None,  # 점수차 < debate_draw_threshold이면 None (무승부)
    "input_tokens": int,
    "output_tokens": int,
}
```

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `settings` | `app.core.config` | 모델 ID, 타임아웃, 토큰 상한, ELO 파라미터 읽기 |
| `DebateMatch` | `app.models.debate_match` | `penalty_a`, `penalty_b`, `agent_a_id`, `agent_b_id` 참조 |
| `DebateTopic` | `app.models.debate_topic` | `title`, `description` 참조 (Judge 프롬프트 구성) |
| `DebateTurnLog` | `app.models.debate_turn_log` | 턴별 발언·검토 결과·벌점 참조 |
| `InferenceClient` | `app.services.llm.inference_client` | LLM API 호출 (`generate_byok`) |

### 관련 설정값 (`config.py`)

| 설정 키 | 설명 |
|---|---|
| `debate_review_model` | 턴 검토 경량 모델 (`optimized=True`일 때) |
| `debate_turn_review_model` | 턴 검토 모델 (`optimized=False`일 때) |
| `debate_orchestrator_model` | 폴백 기본 모델 |
| `debate_judge_model` | 최종 판정 고정밀 모델 (`optimized=True`일 때) |
| `debate_turn_review_timeout` | `review_turn` LLM 호출 타임아웃 (초) |
| `debate_review_max_tokens` | review LLM 최대 출력 토큰 |
| `debate_judge_max_tokens` | judge LLM 최대 출력 토큰 |
| `debate_draw_threshold` | 무승부 판정 최소 점수차 기준 |
| `debate_elo_k_factor` | ELO K 팩터 |
| `debate_elo_score_diff_scale` | 점수차 배수 스케일 |
| `debate_elo_score_diff_weight` | 점수차 배수 가중치 |
| `debate_elo_score_mult_max` | 점수차 배수 상한 |

---

## 호출 흐름

### 턴 검토 흐름 (병렬 실행)

```
engine.py (_run_turn_loop)
  → asyncio.gather(
      orchestrator.review_turn(turn_a),   # 이전 턴 A 검토
      _execute_turn(agent_b),             # 다음 턴 B 실행 (병렬 — 지연 37% 단축)
    )
      → review_turn()
          → _call_review_llm(model_id, api_key, messages)
              → InferenceClient.generate_byok(provider, model_id, api_key, messages)
          → _build_review_result(review, input_tokens, output_tokens)
          [실패] → _review_fallback()
```

### 최종 판정 흐름

```
engine.py (_finalize_match)
  → orchestrator.judge(match, turns, topic, ...)
      → _judge_with_model(match, turns, topic, agent_a_name, agent_b_name, model_id)
          → _format_debate_log(turns, topic, ..., swap_sides)  # 50% 확률 A/B 스왑
          → InferenceClient.generate_byok(provider, model_id, api_key, messages)
          → scorecard 파싱 + 스왑 역변환 (이름 교체 포함)
          → 벌점 차감 → 승패 결정
  → calculate_elo(rating_a, rating_b, result, score_diff)
```

---

## 에러 처리

| 상황 | 처리 방식 |
|---|---|
| API 키 미설정 | `review_turn` 즉시 `_review_fallback()` 반환 (LLM 호출 시도 없음) |
| `review_turn` 타임아웃 (`debate_turn_review_timeout` 초과) | `TimeoutError` 포착 → `_review_fallback()` 반환. 토론 진행 중단 없음 |
| `review_turn` JSON 파싱 실패 | `json.JSONDecodeError` / `KeyError` / `ValueError` 포착 → `_review_fallback()` 반환 |
| `review_turn` 네트워크·API 장애 | `Exception` 포착 → `_review_fallback()` 반환 |
| `_judge_with_model` 파싱 실패 | 각 항목 최대값의 절반으로 균등 점수 → 무승부 폴백. `swap=False` 강제 |
| `scorecard` 구조 오류 (`agent_a`/`agent_b`가 dict 아님) | `ValueError("Invalid scorecard structure")` → 파싱 실패로 처리 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-12 | 규칙 준수 전면 재작성. 클래스 섹션 분리, 반환 dict 구조 명시, 에러 처리 표 추가, 관련 설정값 표 보강 |
| 2026-03-11 | 실제 코드 기반으로 초기 재작성 |
