# orchestrator.py 모듈 명세

**파일 경로:** `backend/app/services/debate/orchestrator.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

두 가지 핵심 역할을 담당한다. 첫째, 매 턴마다 경량 LLM(`debate_review_model`)으로 발언을 검토하여 위반 감지·벌점 산출·차단 여부를 반환한다. 둘째, 모든 턴 완료 후 고정밀 LLM(`debate_judge_model`)으로 최종 판정을 수행하여 스코어카드를 생성하고 승패를 결정한다. 모듈 수준에 ELO 계산 함수 `calculate_elo`도 포함되어 있다.

---

## 주요 상수

| 상수 | 설명 |
|---|---|
| `PENALTY_KO_LABELS` | 벌점 키 → 한국어 라벨 매핑 (Judge LLM 프롬프트에 영문 파라미터 노출 방지용) |
| `SCORING_CRITERIA` | `{"logic": 30, "evidence": 25, "rebuttal": 25, "relevance": 20}` — 채점 항목별 최대 점수 |
| `JUDGE_SYSTEM_PROMPT` | Judge LLM 시스템 프롬프트. 100점 만점 채점, JSON 형식 응답 강제 |
| `LLM_VIOLATION_PENALTIES` | `{"prompt_injection": 10, "ad_hominem": 8, "false_claim": 7, "off_topic": 5}` |
| `REVIEW_SYSTEM_PROMPT` | Review LLM 시스템 프롬프트. logic_score/violations/severity/feedback/block 포함 JSON 응답 강제 |

### PENALTY_KO_LABELS 항목

| 키 | 한국어 라벨 | 탐지 경로 |
|---|---|---|
| `schema_violation` | JSON 형식 위반 | engine.py 코드 기반 |
| `token_limit` | 토큰 제한 초과 | engine.py 코드 기반 |
| `repetition` | 주장 반복 | engine.py 코드 기반 |
| `llm_prompt_injection` | 프롬프트 인젝션(LLM) | review_turn() |
| `llm_ad_hominem` | 인신공격(LLM) | review_turn() |
| `llm_off_topic` | 주제 이탈(LLM) | review_turn() |
| `llm_false_claim` | 허위 주장(LLM) | review_turn() |

---

## 모듈 수준 함수

### `calculate_elo(rating_a: int, rating_b: int, result: str, score_diff: int = 0) -> tuple[int, int]`
표준 ELO + 판정 점수차 배수 공식.

- `result`: `'a_win'` / `'b_win'` / `'draw'`
- `score_diff`: `abs(score_a - score_b)`, 0~100 범위
- 공식: `E_a = 1 / (1 + 10^((rating_b - rating_a) / 400))`, `mult = 1.0 + (score_diff / scale) × weight`
- 설정값: `debate_elo_k_factor`, `debate_elo_score_diff_scale`, `debate_elo_score_diff_weight`, `debate_elo_score_mult_max`
- 반환: `(new_rating_a, new_rating_b)` — 제로섬 유지

### `_infer_provider(model_id: str) -> str` (내부)
모델 ID 접두사로 provider 추론. `claude` → `anthropic`, `gemini` → `google`, 기타 → `openai`.

### `_platform_api_key(provider: str) -> str` (내부)
provider에 맞는 플랫폼 환경변수 API 키 반환.

---

## DebateOrchestrator

생성자: `__init__(self, optimized: bool = True, client: InferenceClient | None = None)`

- `optimized=True`: 경량 review 모델(`debate_review_model`) + 고정밀 judge 모델(`debate_judge_model`) 분리 사용
- `client` 주입 시 커넥션 풀 재사용 (소유권 미보유)

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `aclose` | `() -> None` | 클라이언트 소유권이 있으면 닫기 |
| `review_turn` | `(topic, speaker, turn_number, claim, evidence, action, opponent_last_claim) -> dict` | 단일 턴 LLM 검토. 실패 시 폴백 dict 반환 (토론 중단 없음) |
| `judge` | `(match, turns, topic, agent_a_name, agent_b_name) -> dict` | 토론 전체 판정. `optimized=True`이면 `debate_judge_model` 사용 |
| `_call_review_llm` | `(model_id, api_key, messages) -> tuple[dict, int, int]` | LLM 호출 → 마크다운 제거 → JSON 파싱 → `(review_dict, input_tokens, output_tokens)` |
| `_build_review_result` | `(review, input_tokens, output_tokens, skipped) -> dict` | 파싱된 review dict를 최종 결과 dict로 변환. `LLM_VIOLATION_PENALTIES`로 벌점 산출 |
| `_review_fallback` | `() -> dict` | 검토 실패 시 안전 폴백 (logic_score=5, 위반 없음, block=False) |
| `_judge_with_model` | `(match, turns, topic, agent_a_name, agent_b_name, model_id) -> dict` | 지정 모델로 LLM 판정. 50% 확률 A/B 라벨 스왑으로 발언 순서 편향 제거 |
| `_format_debate_log` | `(turns, topic, agent_a_name, agent_b_name, swap_sides) -> str` | 턴 로그를 Judge LLM이 읽을 수 있는 텍스트 블록으로 변환. 논증품질 점수 포함 |

### `review_turn` 반환 dict 구조

```python
{
    "logic_score": int,          # 1-10
    "violations": list[dict],    # [{"type": str, "severity": str, "detail": str}, ...]
    "feedback": str,             # 관전자용 한줄평 (30자 이내)
    "block": bool,               # True이면 원문 차단
    "penalties": dict[str, int], # 위반 유형 → 벌점
    "penalty_total": int,
    "blocked_claim": str | None, # block=True이면 대체 텍스트
    "input_tokens": int,
    "output_tokens": int,
    "skipped": bool,             # optimized 모드에서만 포함
}
```

### `judge` 반환 dict 구조

```python
{
    "scorecard": dict,   # {"agent_a": {logic, evidence, rebuttal, relevance}, "agent_b": {...}, "reasoning": str}
    "score_a": int,      # 최종 점수 (벌점 차감 후, 0 이상)
    "score_b": int,
    "penalty_a": int,
    "penalty_b": int,
    "winner_id": UUID | None,   # 점수차 < debate_draw_threshold이면 None (무승부)
    "input_tokens": int,
    "output_tokens": int,
}
```

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.core.config` | `settings` — 모델 ID, 타임아웃, ELO 파라미터 등 |
| `app.models.debate_match` | `DebateMatch` |
| `app.models.debate_topic` | `DebateTopic` |
| `app.models.debate_turn_log` | `DebateTurnLog` |
| `app.services.llm.inference_client` | `InferenceClient` |

---

## 관련 설정값

| 설정 키 | 기본값 | 설명 |
|---|---|---|
| `debate_review_model` | `"gpt-4o-mini"` | 턴 검토 경량 모델 |
| `debate_judge_model` | `"gpt-4.1"` | 최종 판정 고정밀 모델 |
| `debate_turn_review_timeout` | — | `review_turn` LLM 호출 타임아웃 (초) |
| `debate_review_max_tokens` | — | review LLM 최대 출력 토큰 |
| `debate_judge_max_tokens` | — | judge LLM 최대 출력 토큰 |
| `debate_draw_threshold` | — | 무승부 판정 점수차 기준 |
| `debate_elo_k_factor` | — | ELO K 팩터 |
| `debate_elo_score_diff_scale` | — | ELO 점수차 배수 스케일 |
| `debate_elo_score_diff_weight` | — | ELO 점수차 배수 가중치 |
| `debate_elo_score_mult_max` | — | ELO 점수차 배수 상한 |

---

## 호출 흐름

```
engine.py (_run_turn_loop)
  → asyncio.gather(
      orchestrator.review_turn(turn_a),   # 이전 턴 A 검토
      _execute_turn(turn_b),              # 다음 턴 B 실행 (병렬)
    )

engine.py (_finalize_match)
  → orchestrator.judge(match, turns, topic, ...)
      → _judge_with_model()
          → InferenceClient.generate_byok()
  → calculate_elo(rating_a, rating_b, result, score_diff)
```

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
