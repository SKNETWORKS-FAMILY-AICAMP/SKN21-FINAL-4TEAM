# Deep Interview Spec: 토론 점수 산정 시스템 개선

## Metadata
- Interview ID: scoring-system-improvement-001
- Rounds: 11
- Final Ambiguity Score: 12%
- Type: brownfield
- Generated: 2026-03-12
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown

| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| Goal Clarity | 0.91 | 35% | 0.319 |
| Constraint Clarity | 0.85 | 25% | 0.213 |
| Success Criteria | 0.86 | 25% | 0.215 |
| Context Clarity | 0.87 | 15% | 0.131 |
| **Total Clarity** | | | **0.878** |
| **Ambiguity** | | | **~12%** |

---

## Goal

4개 항목을 순서대로 개선한다. 전면 재설계 아님 — 각 항목은 독립적으로 범위가 제한된 개선이다.

1. **engine ↔ orchestrator 경계 재획정**
2. **프롬프트 기능 과다 분리 + 단순화**
3. **편향 제거 방식 재설계**
4. **벌점 체계 간소화**

---

## 항목별 상세 스펙

### 항목 1: engine ↔ orchestrator 경계 재획정

**목표:** engine.py가 모델 ID를 전혀 모르게 만든다.

**현재 문제:**
- `engine.py:405-406`, `1432-1434` — judge 모델 ID 선택 로직 중복 (orchestrator가 해야 할 일)
- `engine.py:556` — review 모델 ID 선택 로직
- `engine.py:580, 666, 706` — `_log_orchestrator_usage()` 직접 호출 (orchestrator 내부 구현에 의존)

**완료 기준:**
- engine.py는 `orchestrator.review_turn()` / `orchestrator.judge()` 만 호출
- 어떤 모델 ID를 쓰는지, 토큰 로깅 방식은 orchestrator 내부 결정
- engine.py에서 `settings.debate_review_model`, `settings.debate_judge_model` 참조 제거

**변경 대상 파일:**
- `backend/app/services/debate/engine.py`
- `backend/app/services/debate/orchestrator.py`

---

### 항목 2: 프롬프트 기능 과다 분리 + 단순화

**목표:** 각 프롬프트가 단일 책임을 갖도록 불필요한 지시 제거 + 코드 관리 개선.

**REVIEW_SYSTEM_PROMPT 변경:**
- 유지: logic_score 평가, 위반 탐지(간소화된 목록), severity, block 결정
- 제거 또는 이동: `feedback` 필드 (관전자 한줄평) — review LLM 호출에서 빼고 engine이 생성하거나 제거 검토
- 위반 유형 목록 축소 (항목 4 참조)

**JUDGE_SYSTEM_PROMPT 변경:**
- 제거: "JSON 형식 위반 2회 이상 → relevance 위반횟수×2점 감점" 하드코딩 → `_judge_with_model` 후처리 코드로 이동
- 제거: 논증품질 점수 활용 지침 중 복잡한 수식 표현 (단순 참고 지시로 대체)
- 유지: 채점 4개 항목 기준, 편향 배제 지시 (항목 3 반영), JSON 형식 강제

**구조 분리:**
- 프롬프트를 조립 함수 (`build_review_prompt()`, `build_judge_prompt()`) 또는 별도 상수 블록으로 분리
- 파일 분리까지는 선택 사항 (코드 내 관리 가능하면 유지)

**완료 기준:**
- 프롬프트에 비즈니스 로직(점수 계산·벌점 공식)이 없음
- 각 프롬프트의 책임이 단일하게 읽힘

---

### 항목 3: 편향 제거 방식 재설계

**목표:** 근거 없는 랜덤 스왑을 제거하고 실질적 편향(장황함·주제 편향)을 프롬프트로 대응한다.

**제거:**
- `random.random() < 0.5` 스왑 로직
- `scorecard["agent_a"], scorecard["agent_b"] = ...` 역변환
- reasoning 텍스트 이름 교체 로직 (`_pa`, `_pb` placeholder 치환)
- `_format_debate_log`의 `swap_sides` 파라미터

**추가 (JUDGE_SYSTEM_PROMPT):**
- **장황함 편향 대응:** "발언 길이가 아닌 논증 밀도를 평가하라. 더 긴 발언이 더 나은 논증이 아니다. 핵심 논거의 수와 근거의 구체성을 기준으로 삼아라."
- **주제 편향 대응:** "에이전트의 입장(찬성/반대)이나 토론 주제에 대한 개인적 견해와 무관하게, 제시된 논증의 내적 일관성과 근거만으로 채점하라."
- **독립 채점 지시:** "각 에이전트를 상대방과 비교하기 전에 절대 기준으로 먼저 평가한 후 비교하라."

**완료 기준:**
- `swap` 관련 코드 0줄
- Judge 프롬프트에 위 3개 지시 포함

---

### 항목 4: 벌점 체계 간소화

**목표:** 실질적 의미가 있는 벌점만 남기고 나머지 제거.

#### 코드 기반 벌점 (engine.py) 변경

| 벌점 | 현재 | 변경 |
|---|---|---|
| `schema_violation` (5점) | 파싱 실패 시 부과 | **제거** — 폴백으로 이미 처리됨. 이중 처리 |
| `token_limit` (3점) | finish_reason=length 시 부과 | **제거** — 의미 없음 |
| `timeout` (5점) | 타임아웃 시 부과 | **제거** → 재시도 + 부전패로 교체 |
| `false_source` (7점) | WebSocket tool_result 위조 | **유지** — 악의적 행위, 탐지 명확 |
| `repetition` (3점) | 단어 중복 70%+ | **유지** — 코드로 탐지, 명확 |

#### 타임아웃 → 재시도 + 부전패 로직 (신규)

현재 타임아웃 시 벌점 5점 부과 → **아래로 교체:**

```
에이전트 발언 실패(타임아웃·연결 끊김·API 오류) 발생 시:
  1. 즉시 재시도 (최대 N회, 설정값: debate_turn_max_retries, 기본 2)
  2. N회 초과 시:
     a. 해당 에이전트 forfeit(부전패) 처리
     b. 상대 에이전트 walkover(부전승)
     c. 매치 강제 종료 (judge 호출 없음)
     d. ELO: 부전패 처리 (점수차 최대로 계산)
  3. 재시도 중 성공 시 정상 진행 (지연 기록)
```

`config.py` 추가: `debate_turn_max_retries: int = 2`

**도구 사용 에이전트 고려:** 향후 도구 제공 시 `debate_turn_review_timeout` 값이 맥락에 따라 달라져야 함. 지금은 config 값으로만 관리하되 도구 유무에 따라 다른 타임아웃을 줄 수 있도록 인터페이스 여지 확보.

#### LLM 기반 위반 탐지 (orchestrator.py) 변경

**유지 (5종):** 탐지 신뢰도 높고 실질적 의미 있음
| 유형 | 벌점 | 유지 이유 |
|---|---|---|
| `prompt_injection` | 10 | 시스템 무력화 시도, 탐지 명확 |
| `ad_hominem` | 8 | 인신공격, 맥락 명확 |
| `false_claim` | 7 | 허위 주장, 판별 가능 |
| `straw_man` | 6 | 주장 왜곡, 탐지 가능 |
| `off_topic` | 5 | 주제 이탈, 탐지 쉬움 |

**제거 (8종):** 오탐 위험 높거나 실제 토론에서 거의 미탐지
`circular_reasoning`, `hasty_generalization`, `accent`, `genetic_fallacy`, `appeal`, `slippery_slope`, `division`, `composition`

#### PENALTY_KO_LABELS 정리

- 제거: `off_topic` (접두사 없음, 데드 엔트리), `false_claim` (접두사 없음, 데드 엔트리)
- 제거: `schema_violation`, `token_limit` (벌점 폐지)
- 추가: `timeout`은 이제 부전패로 처리되므로 라벨 불필요 — 제거
- 유지: `repetition`, `false_source`
- 유지: `llm_prompt_injection`, `llm_ad_hominem`, `llm_false_claim`, `llm_straw_man`, `llm_off_topic`
- 제거: `llm_circular_reasoning` 등 제거된 8종의 llm_ 항목

---

## Non-Goals

- 전면 재설계 아님 — orchestrator.py 클래스 구조 자체는 유지
- judge를 두 번 호출하는 더블 판정 방식 도입 안 함 (비용 2배)
- 병렬/순차 코드 경로 통합 (엔진 구조 변경은 이번 범위 밖)
- 새 LLM 모델 도입 없음

## Constraints

- 기존 API 인터페이스 유지 (`review_turn`, `judge` 시그니처 변경 최소화)
- `debate_turn_max_retries` config 추가 필요 (기존 config 제거 없음)
- 단위 테스트 통과 유지

## Acceptance Criteria

- [ ] engine.py에서 `settings.debate_review_model`, `settings.debate_judge_model` 참조 0개
- [ ] `random.random()` / `swap_sides` 관련 코드 제거됨
- [ ] JUDGE_SYSTEM_PROMPT에 장황함 편향·주제 편향·독립 채점 지시 포함
- [ ] `PENALTY_KO_LABELS`에 데드 엔트리 없음 (실제 탐지되는 것만 존재)
- [ ] `LLM_VIOLATION_PENALTIES`가 5종으로 축소됨
- [ ] 타임아웃 시 재시도 후 부전패 처리 동작 확인 (단위 테스트)
- [ ] JUDGE_SYSTEM_PROMPT에 하드코딩된 벌점 감점 공식 없음
- [ ] `config.py`에 `debate_turn_max_retries` 추가됨
- [ ] 기존 단위 테스트 모두 통과

## Technical Context

- `backend/app/services/debate/orchestrator.py` — `DebateOrchestrator`, `calculate_elo`, 프롬프트 상수
- `backend/app/services/debate/engine.py` — 턴 루프, 판정, 모델 ID 선택 중복
- `backend/app/core/config.py` — 설정값 관리

## Interview Transcript (요약)

| 라운드 | 질문 핵심 | 답변 |
|---|---|---|
| 1 | 4개 항목 중 우선순위 | 순서대로, 전면 재설계 아님 |
| 2 | 중복 정리 방식 | engine ↔ orchestrator 경계 재획정 |
| 3 | 완료 기준 | engine이 모델 ID를 전혀 모르게 |
| 4 | 프롬프트 문제 본질 | 내용 과다 + 기능 혼합 둘 다 |
| 5 | 분리 방식 | 호출 통합, 불필요한 기능 제거 |
| 6 | 편향 방향 | 장황함 + 주제 편향 대응, 스왑 제거 |
| 7 | 스왑 코드 처리 | 완전 제거 |
| 8 | 어떤 편향이 핵심 | 주제 편향 + 장황함 편향 |
| 9 | 편향 대응 방식 | 둘 다 + 스왑 제거 |
| 10 | 벌점 체계 핵심 문제 | 하드코딩 과다, 의미 없는 벌점 |
| 11 | 위반 탐지·타임아웃 | 탐지 가능한 5종만 유지, 타임아웃은 재시도+부전패로 교체 |
