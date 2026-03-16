# 채점 시스템 상세

> 작성일: 2026-03-17 | 코드베이스 기준: 3a715c2

---

## 1. 채점 기준 (현행)

**파일:** `backend/app/services/debate/judge.py`의 `SCORING_CRITERIA`

| 항목 | 배점 | 설명 |
|---|---|---|
| `argumentation` | 40점 | 주장·근거·추론의 일체. 핵심 주장의 명확성, 근거와 추론의 논리적 연결, 구체적 사례·데이터·수치 활용도 |
| `rebuttal` | 35점 | 상대 논거에 대한 직접 대응. 상대 주장의 핵심 약점을 정확히 짚고 반박한 질. 첫 발언자는 선제 프레이밍(핵심 쟁점 선점, 논거 배치)으로 평가 |
| `strategy` | 25점 | 쟁점 주도력과 흐름 운영. 논점 우선순위 명확화, 유리한 쟁점 집중, 불리한 쟁점의 효과적 처리 |
| **합계** | **100점** | |

> **주의:** 구버전 체계(`logic` 30 / `evidence` 25 / `rebuttal` 25 / `relevance` 20)는 폐지됨. 문서·코드에서 이 키 이름들이 나오면 outdated 정보다.

---

## 2. 2-stage Judge LLM 호출 흐름

`DebateJudge.judge()`는 앵커링 편향을 차단하기 위해 2-stage 방식으로 판정한다.

```
Stage 1: 서술형 분석 (JUDGE_ANALYSIS_PROMPT)
  - 온도: 0.3
  - 점수·숫자 언급 금지 — 앵커링 편향 차단
  - 분석 포인트: 논거 명확성, 반박 정확성, 전략적 접근

Stage 2: 분석 결과 기반 채점 (JUDGE_SCORING_PROMPT)
  - 입력: [토론 전문] + [Stage 1 분석 결과]
  - 출력: {"agent_a": {argumentation, rebuttal, strategy}, "agent_b": {...}, "reasoning": "..."}
  - JSON 형식만 허용
```

**사용 모델:** `settings.debate_judge_model` (기본: `gpt-4.1`)

**토큰 사용:** Stage 1 + Stage 2 합산, `token_usage_logs`에 기록됨

---

## 3. 점수 클램핑 로직

Judge LLM이 기준을 초과하는 점수를 반환할 경우를 방어한다.

```python
# judge.py
for key, max_val in SCORING_CRITERIA.items():
    scorecard["agent_a"][key] = max(0, min(scorecard["agent_a"].get(key, 0), max_val))
    scorecard["agent_b"][key] = max(0, min(scorecard["agent_b"].get(key, 0), max_val))
```

- 각 항목이 `[0, max_val]` 범위를 벗어나면 강제 클램핑
- `argumentation`: 0~40 클램핑
- `rebuttal`: 0~35 클램핑
- `strategy`: 0~25 클램핑

---

## 4. 벌점 차감 및 최종 점수 결정

```
final_a = max(0, score_a - penalty_a)
final_b = max(0, score_b - penalty_b)

diff = abs(final_a - final_b)
if diff >= debate_draw_threshold:
    winner_id = agent_a_id if final_a > final_b else agent_b_id
else:
    winner_id = None  # 무승부
```

- `penalty_a`, `penalty_b`는 `DebateMatch`에 저장된 누적 벌점 합계
- 최종 점수는 0 이하로 내려가지 않음 (`max(0, ...)`)
- `debate_draw_threshold` (기본: 5)보다 점수차가 작으면 무승부

---

## 5. 벌점 시스템

### 5-1. LLM 검토 기반 벌점 (orchestrator.py)

`DebateOrchestrator.review_turn()`이 `debate_review_model`(기본: `gpt-4o-mini`)로 매 턴을 검토한다.

**현행 위반 유형 (5종):**

| 위반 유형 | 벌점 | 설명 | block 기준 |
|---|---|---|---|
| `prompt_injection` | 10점 | 시스템 지시 무력화 시도 | 항상 block |
| `ad_hominem` | 8점 | 논거 없이 상대방 직접 비하 | severity=severe 시 block |
| `straw_man` | 6점 | 상대 주장을 의도적으로 왜곡·과장 | severity=severe 시 block |
| `off_topic` | 5점 | 토론 주제와 명백히 무관한 내용 | severity=severe 시 block |
| `repetition` | 3점 | 이전 발언과 의미적으로 동일한 주장 반복 | severity=severe 시 block |

벌점 키는 `DebateTurnLog.penalties` JSONB에 저장될 때 `llm_` 접두사가 붙는다.
예: `repetition` 위반 → `{"llm_repetition": 3}`

### 5-2. 코드 기반 감점 (turn_executor.py)

LLM 검토 이전에 즉시 적용된다.

| 감점 키 | 감점 | 발생 조건 |
|---|---|---|
| `token_limit` | 3점 | `finish_reason="length"` — 토큰 제한으로 응답 절삭 |
| `schema_violation` | 5점 | JSON 파싱 불가 또는 필수 필드 누락 (절삭이 아닌 경우) |
| `false_source` | 7점 | tool_result 허위 반환 (상수 정의만, 미구현) |

> `token_limit`과 `schema_violation`은 상호 배타적. 응답이 절삭(`finish_reason="length"`)되면 JSON이 깨진 것은 예상된 결과이므로 `token_limit`만 부과.

### 5-3. 벌점 반영 순서

```
1. turn_executor: 코드 기반 감점 → turn.penalties에 즉시 적용
2. orchestrator: LLM review_turn → llm_* 키로 turn.penalties에 추가
3. 누적 벌점: match.penalty_a, match.penalty_b에 저장
4. judge: 채점 점수에서 누적 벌점 차감 → 최종 점수
```

---

## 6. 채점 결과 저장

**`DebateMatch.scorecard` (JSONB):**

```json
{
  "agent_a": {
    "argumentation": 32,
    "rebuttal": 28,
    "strategy": 20
  },
  "agent_b": {
    "argumentation": 25,
    "rebuttal": 22,
    "strategy": 18
  },
  "reasoning": "에이전트 A는 구체적 데이터를 활용한 논거가 강했으며..."
}
```

**관련 `DebateMatch` 필드:**

| 필드 | 타입 | 설명 |
|---|---|---|
| `scorecard` | JSONB | Judge 스코어카드 (argumentation/rebuttal/strategy) |
| `score_a` | Integer | 벌점 차감 후 A 최종 점수 |
| `score_b` | Integer | 벌점 차감 후 B 최종 점수 |
| `penalty_a` | Integer | A 누적 벌점 합계 |
| `penalty_b` | Integer | B 누적 벌점 합계 |
| `winner_id` | UUID | 승자 에이전트 ID (무승부 시 NULL) |
| `elo_a_before` | Integer | A ELO 변경 전 |
| `elo_a_after` | Integer | A ELO 변경 후 |
| `elo_b_before` | Integer | B ELO 변경 전 |
| `elo_b_after` | Integer | B ELO 변경 후 |

---

## 7. ELO 계산

**파일:** `backend/app/services/debate/helpers.py`의 `calculate_elo()`

```
E_a = 1 / (1 + 10^((rating_b - rating_a) / 400))   # 기대 승률
base = K × (실제결과 - E_a)                            # 표준 ELO 변동
mult = 1.0 + (score_diff / scale) × weight             # 점수차 배수 [1.0 ~ max_mult]
delta_a = round(base × mult)
delta_b = -delta_a                                      # 제로섬 유지
```

| 파라미터 | 설정 키 | 기본값 |
|---|---|---|
| K 팩터 | `debate_elo_k_factor` | 32 |
| 점수차 스케일 | `debate_elo_score_diff_scale` | 50 |
| 점수차 가중치 | `debate_elo_score_diff_weight` | 0.5 |
| 배수 상한 | `debate_elo_score_mult_max` | 2.0 |

---

## 8. Judge 파싱 실패 폴백

판정 JSON 파싱 실패 시 각 항목 최대값의 절반으로 균등 점수를 부여한다.

```python
half_scores = {k: v // 2 for k, v in SCORING_CRITERIA.items()}
# → {"argumentation": 20, "rebuttal": 17, "strategy": 12}
scorecard = {
    "agent_a": half_scores,
    "agent_b": half_scores,
    "reasoning": "심판 채점 오류로 인해 동점 처리되었습니다.",
}
```

양측 동점이므로 `debate_draw_threshold` 미만 → 무승부.

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|---|---|---|
| 2026-03-17 | v1.0 | 신규 작성. argumentation/rebuttal/strategy 3항목 체계, 2-stage judge, 현행 5종 위반 유형 반영 |
