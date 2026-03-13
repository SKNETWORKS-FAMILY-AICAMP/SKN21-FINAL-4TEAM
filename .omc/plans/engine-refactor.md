# 토론 엔진 리팩터링 계획 (Consensus 확정)

> **작성일:** 2026-03-13
> **합의 라운드:** 1회 (Architect REVISE → Critic APPROVE)
> **대상:** `backend/app/services/debate/engine.py` (1,716줄) + `orchestrator.py` (534줄)
> **목표:** 클래스/인터페이스 기반 재설계로 확장성·가독성·테스트 용이성 확보

---

## RALPLAN-DR (Short Mode)

### Principles (원칙)

1. **단일 책임 분리** — 턴 실행, 검토, 판정, ELO/승급전 후처리를 독립 모듈로 분리
2. **개방-폐쇄 원칙** — 새 토론 형식 추가 시 기존 코드 수정 없이 함수 1개 + dict 등록 1줄로 확장
3. **성능 보존** — asyncio.create_task 롤링 병렬 패턴 그대로 유지, 추상화로 인한 오버헤드 0
4. **점진적 마이그레이션** — Phase별 독립 롤백 가능, 매 Phase 완료 후 기존 테스트 전체 통과 검증
5. **외부 계약 불변** — SSE 이벤트명, API 스키마, WebSocket 프로토콜, `run_debate()` 시그니처 변경 금지

### Decision Drivers (결정 요인)

1. **확장 비용**: 새 형식 추가 시 `_run_turn_loop` 286줄 전체 파악 필요 → 30줄 이하 목표
2. **응집도**: `_finalize_match`(120줄)에 7가지 관심사 혼재, multi/1v1 finalize 중복 코드 100줄+
3. **테스트 가능성**: 턴 실행·판정·후처리가 엉켜 있어 단위 테스트 불가능

### Viable Options

#### Option A: 함수 dispatch + 책임 분리 모듈 (선택)

```
debate/
├── engine.py          → 진입점 + 포맷 dispatch + 세션 관리 (~250줄)
├── helpers.py         → 순수 함수 + calculate_elo (신규)
├── turn_executor.py   → TurnExecutor 클래스 (신규)
├── formats.py         → run_turns_1v1(), run_turns_multi() + _FORMAT_RUNNERS dict (신규)
├── finalizer.py       → MatchFinalizer 클래스 (신규)
├── forfeit.py         → ForfeitHandler 클래스 (신규)
└── orchestrator.py    → 기존 유지 (검토/판정 LLM 호출)
```

**Pros:** YAGNI 준수 (포맷 2개에 ABC 불필요), 함수 dispatch로도 30줄 성공 기준 충족, asyncio 패턴 보존 용이, 파일 수 최소화
**Cons:** 포맷 인터페이스 타입 강제 없음 (세 번째 포맷 추가 시 ABC 전환 필요)

#### Option B: 순수 함수 분리만 (탈락)

**Cons:** 새 형식 추가 시 if/elif 분기 잔존, ELO/승급전 중복 코드 잔존, "30줄" 목표 달성 불가

**탈락 근거:** 줄 수 축소만 달성하고 구조적 개선 없음

---

## 구현 단계 (Phase별)

### Phase 1: 헬퍼 + TurnExecutor 추출

**목적:** 순수 함수와 단일 턴 실행 로직을 별도 모듈로 추출. 기존 동작 100% 보존.

**변경 파일:**
- `debate/helpers.py` (신규)
- `debate/turn_executor.py` (신규)
- `debate/engine.py` (import 변경 + re-export 추가)

**helpers.py — 이동 대상:**

```python
# debate/helpers.py
RESPONSE_SCHEMA_INSTRUCTION: str = ...   # engine.py:85에서 이동
PENALTY_REPETITION: int = 3              # engine.py에서 이동
PENALTY_FALSE_SOURCE: int = 7            # engine.py에서 이동

def detect_repetition(new_claim, previous_claims, threshold=0.7) -> bool: ...
def validate_response_schema(response_text) -> dict | None: ...
def _build_messages(system_prompt, topic, turn_number, speaker, my_claims, opponent_claims) -> list[dict]: ...
def _resolve_api_key(agent, force_platform=False) -> str: ...
def calculate_elo(rating_a, rating_b, result, score_diff=0) -> tuple[int, int]: ...
    # orchestrator.py:491에서 이동 (순수 수학 함수 — judge와 분리)
```

**turn_executor.py:**

```python
class TurnExecutor:
    def __init__(self, client: InferenceClient, db: AsyncSession): ...
    async def execute(self, match, topic, turn_number, speaker, agent, version,
                      api_key, my_claims, opponent_claims, my_accumulated_penalty) -> DebateTurnLog: ...
    async def execute_with_retry(self, ...) -> DebateTurnLog | None: ...
    # 현재 _execute_turn + _execute_turn_with_retry 이동
```

**engine.py re-export (하위 호환):**

```python
# engine.py에 추가 (테스트·외부 import 보호)
from app.services.debate.helpers import (
    detect_repetition, validate_response_schema, _build_messages,
    _resolve_api_key, calculate_elo, RESPONSE_SCHEMA_INSTRUCTION,
)
from app.services.debate.turn_executor import TurnExecutor
from app.services.debate.forfeit import ForfeitError  # Phase 2에서 추가
```

**orchestrator.py re-export:**

```python
# orchestrator.py에 추가
from app.services.debate.helpers import calculate_elo  # 기존 import 보호
```

**SSE/broadcast 헬퍼 처리:**
`_publish_turn_event`, `_publish_review_event`, `_apply_review_to_turn` 세 함수는 engine.py에 잔류. Phase 2에서 finalizer가 이들을 의존하는지 확인 후 이동 여부 결정.

**수용 기준:**
- [ ] `pytest backend/tests/unit/ -v` 전체 통과 (import 경로 re-export로 보호)
- [ ] `pytest backend/tests/` 전체 통과 (integration 포함)
- [ ] `TurnExecutor.execute()` 단위 테스트 3개+ 추가 (정상, 타임아웃 재시도, API 키 실패)
- [ ] engine.py에서 `_execute_turn`, `_execute_turn_with_retry`, `detect_repetition`, `validate_response_schema`, `_build_messages`, `_resolve_api_key` 함수 **본문 제거**, re-export 유지
- [ ] `_log_orchestrator_usage`는 engine.py 잔류 또는 finalizer 흡수 — 구현 시 결정 후 주석 명시

---

### Phase 2: 판정·후처리 통합 (MatchFinalizer + ForfeitHandler)

**목적:** `_finalize_match`(1v1) + `_execute_multi_and_finalize` finalize 부분의 중복 코드 통합, **기존 multi 경로 버그 동시 수정**.

> ⚠️ **기존 버그 수정 포함** — multi 경로(`_execute_multi_and_finalize`)에는 아래 4가지 결함이 있음. MatchFinalizer 통합 시 1v1 기준으로 통일하여 함께 수정:
> 1. 승급전 처리(`DebatePromotionService`) 완전 누락
> 2. SSE `finished` 이벤트에 `elo_a_before`/`elo_b_before` 미포함
> 3. `update_elo()` 호출 시 `version_id` 미전달
> 4. `usage_batch` 조기 커밋 (judge 토큰 제외)

**변경 파일:**
- `debate/finalizer.py` (신규)
- `debate/forfeit.py` (신규)
- `debate/engine.py` (해당 함수 제거, import 위임)

**finalizer.py:**

```python
class MatchFinalizer:
    """매치 완료 후처리 통합. 1v1·멀티 공통 진입점."""
    def __init__(self, db: AsyncSession): ...

    async def finalize(
        self, match, judgment, agent_a, agent_b, model_cache, usage_batch,
    ) -> None:
        """처리 순서 (SSE는 db.commit() 이전에 반드시 발행):
        1. judge 토큰 usage_batch 추가
        2. ELO 계산 + DB 갱신
        3. 시즌 ELO 갱신 (match.season_id 있을 때만)
        4. 승급전/강등전 결과 반영 (멀티 경로 누락 버그 수정)
        5. finished SSE 발행 (elo_a_before/elo_b_before 포함, 커밋 전)
        6. DB 커밋 + usage_batch 일괄 INSERT
        7. 예측투표 정산
        8. 토너먼트 라운드 진행
        9. 요약 리포트 백그라운드 태스크
        """

    async def _update_elo(self, match, agent_a, agent_b, elo_result, score_diff) -> tuple: ...
    async def _update_season(self, match, agent_a, agent_b, elo_result, score_diff) -> None: ...
    async def _process_promotions(self, match, agent_a, agent_b, result_a, result_b, new_a, new_b) -> list: ...
```

**forfeit.py:**

```python
class ForfeitError(Exception):
    def __init__(self, forfeited_speaker: str): ...

class ForfeitHandler:
    def __init__(self, db: AsyncSession): ...
    async def settle(self, match, agent_a, agent_b, ...) -> tuple: ...
    async def handle_disconnect(self, match, loser, winner, side) -> None: ...
    async def handle_retry_exhaustion(self, match, agent_a, agent_b, forfeited_speaker) -> None: ...
```

**수용 기준:**
- [ ] `_finalize_match` 본문이 engine.py에서 완전 제거, `MatchFinalizer.finalize()` 호출로 대체
- [ ] `_execute_multi_and_finalize`의 finalize 부분이 `MatchFinalizer.finalize()` 호출로 대체
- [ ] **버그 수정 4건 확인**: 승급전·SSE 페이로드·version_id·usage_batch 타이밍 1v1 기준으로 통일
- [ ] SSE `finished`가 `db.commit()` 이전에 발행되는 순서 유지
- [ ] `MatchFinalizer` 단위 테스트 5개+ (정상 1v1, 무승부, 시즌 매치, 승급전 트리거, 토너먼트 진행)
- [ ] 커밋 메시지에 "fix: multi 경로 승급전·SSE·version_id·usage_batch 누락 버그 수정" 명시
- [ ] `ForfeitError` re-export: `engine.py`에 `from debate.forfeit import ForfeitError` 추가

---

### Phase 3: 포맷 dispatch 분리

**목적:** `_run_turn_loop`(286줄)를 `formats.py`로 분리, 포맷별 함수 dispatch 도입. engine.py를 진입점 역할만으로 슬리밍.

**변경 파일:**
- `debate/formats.py` (신규)
- `debate/engine.py` (DebateEngine 클래스 도입 + 슬리밍)

**formats.py:**

```python
# debate/formats.py
from __future__ import annotations

async def run_turns_1v1(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match, topic, agent_a, agent_b, version_a, version_b,
    key_a, key_b, model_cache, usage_batch, parallel,
) -> TurnLoopResult:
    """기존 _run_turn_loop 이동. 롤링 create_task 병렬 패턴 그대로 보존."""
    ...

async def run_turns_multi(
    executor: TurnExecutor,
    orchestrator: DebateOrchestrator,
    db: AsyncSession,
    match, topic, agent_a, agent_b, ...
) -> TurnLoopResult:
    """기존 _execute_multi_and_finalize의 턴 루프 부분 이동."""
    ...

# 포맷 등록 — 새 형식 추가 = 함수 1개 + 이 dict 1줄
_FORMAT_RUNNERS: dict[str, Callable] = {
    "1v1": run_turns_1v1,
    "2v2": run_turns_multi,
    "3v3": run_turns_multi,
}

def get_format_runner(match_format: str) -> Callable:
    return _FORMAT_RUNNERS.get(match_format, run_turns_1v1)
```

**engine.py (~250줄):**

```python
class DebateEngine:
    """매치 실행 오케스트레이터 — 엔티티 로드 + 포맷 dispatch + finalize."""
    def __init__(self, db: AsyncSession): ...

    async def run(self, match_id: str) -> None:
        """진입점. 엔티티 로드 → 포맷 runner 선택 → 턴 실행 → 판정 → 후처리."""

# 하위 호환: 기존 호출자(matching_service, admin API) 보호
async def run_debate(match_id: str) -> None:
    """기존 진입점. DebateEngine.run()으로 위임."""
    async with async_session() as db:
        engine = DebateEngine(db)
        await engine.run(match_id)
```

**수용 기준:**
- [ ] engine.py ≤ 350줄 (현재 1,716줄 대비 80%+ 감소)
- [ ] `run_turns_1v1()` ≤ 200줄
- [ ] 새 형식 추가 = `formats.py`에 함수 1개 + dict 1줄 (≤ 30줄)
- [ ] `run_debate()` 시그니처 불변
- [ ] 롤링 create_task 병렬 패턴 검증: mock LLM + `asyncio.sleep(0.5)` 사용, 병렬 모드가 순차 대비 ≥30% 빠른지 확인하는 통합 테스트 1개 추가
- [ ] 기존 벤치마크 `test_orchestrator_benchmark.py` 23개 전체 통과
- [ ] 통합 테스트 전체 통과 (`pytest backend/tests/integration/ -v`)
- [ ] `_execute_match` 세션 관리(`async with client:`)를 `DebateEngine.run()` 내부로 이전, 에러 핸들링 보존

---

### Phase 4: 테스트 정비

**목적:** 신규 클래스별 단위 테스트 추가, 기존 테스트 import 경로 업데이트.

**변경 파일:**
- `tests/unit/services/test_debate_engine.py` (import 경로 확인 — re-export로 보호되어 변경 최소)
- `tests/unit/services/test_turn_executor.py` (신규)
- `tests/unit/services/test_match_finalizer.py` (신규)
- `tests/unit/services/test_debate_formats.py` (신규)
- `tests/unit/services/test_debate_forfeit.py` (import 경로 확인)
- `update_test.py` (import 경로 확인 — `_resolve_api_key` 5개소)

**수용 기준:**
- [ ] `pytest backend/tests/ -v` 전체 통과
- [ ] `TurnExecutor` 테스트: 정상 실행, 타임아웃 재시도, API 키 실패 즉시 부전패 (3개+)
- [ ] `MatchFinalizer` 테스트: 정상 1v1, 무승부, 시즌 매치, 승급전 트리거, 토너먼트 진행 (5개+)
- [ ] `run_turns_1v1` 테스트: 순차 모드, 병렬 모드 각 1개+
- [ ] `update_test.py` import 경로 동작 확인 (re-export 경유)

---

## Re-export 전략 (전체)

모든 이동 대상 심볼에 대해 engine.py에서 re-export를 유지해 기존 테스트와 import를 보호한다.

| 심볼 | 이동 위치 | engine.py re-export | orchestrator.py re-export |
|---|---|---|---|
| `detect_repetition` | `helpers.py` | ✅ | — |
| `validate_response_schema` | `helpers.py` | ✅ | — |
| `_build_messages` | `helpers.py` | ✅ | — |
| `_resolve_api_key` | `helpers.py` | ✅ | — |
| `calculate_elo` | `helpers.py` | ✅ | ✅ |
| `RESPONSE_SCHEMA_INSTRUCTION` | `helpers.py` | ✅ | — |
| `ForfeitError` | `forfeit.py` | ✅ | — |
| `_execute_turn` | `turn_executor.py` | ✅ | — |
| `_execute_turn_with_retry` | `turn_executor.py` | ✅ | — |
| `_run_turn_loop` | `formats.py` | ✅ (Phase 3) | — |
| `_execute_match` | `engine.py` 내부 유지 또는 `DebateEngine.run` 위임 | 판단 유보 | — |

---

## 위험 및 완화책

| 위험 | 영향 | 완화책 |
|---|---|---|
| 롤링 병렬 asyncio 패턴 회귀 | 체감 턴 지연 증가 | Phase 3 수용 기준: mock 기반 타이밍 통합 테스트 + 벤치마크 |
| multi 경로 버그 수정 예상치 못한 부작용 | 승급전이 처음으로 multi에서 트리거됨 | Phase 2 커밋 메시지에 명시, QA 시 multi 매치 전체 시나리오 수동 검증 |
| import 순환 참조 | 모듈 로드 실패 | `promotion_service`, `season_service`, `tournament_service` import는 함수 내 지연 import 유지 |
| Phase 간 불완전 상태 배포 | 일치하지 않는 코드 | Phase 완료 전 배포 금지, 각 Phase가 독립 동작하도록 설계 |
| `_log_orchestrator_usage` 위치 모호 | finalizer/engine 양쪽에서 중복 호출 | Phase 1에서 위치 결정 후 주석 명시 (engine 잔류 or finalizer 흡수 선택) |

---

## ADR (Architecture Decision Record)

### Decision
토론 엔진을 **함수 dispatch 방식** + 책임 분리 클래스(TurnExecutor, MatchFinalizer, ForfeitHandler)로 재설계한다. 포맷별 추상 기반 클래스(ABC)는 세 번째 포맷 추가 시점으로 도입을 미룬다.

### Drivers
1. 새 형식 추가 시 `_run_turn_loop` 286줄 전체 파악 필요 — 30줄 이하로 축소
2. `_finalize_match`와 `_execute_multi_and_finalize`에 ELO/승급전/예측/토너먼트 중복 100줄+
3. 단위 테스트 불가능 구조 — TurnExecutor, MatchFinalizer 단위 테스트로 해소

### Alternatives Considered
- **ABC Strategy 패턴**: Architect 검토에서 "포맷 2개에 과설계" 지적. YAGNI 위반.
- **순수 함수 분리 (Option B)**: 새 형식 추가 시 if/elif 잔존, 중복 코드 미제거. "30줄" 목표 달성 불가.

### Why Chosen
- 함수 dispatch로도 "새 형식 ≤ 30줄" 성공 기준 충족 가능 (함수 1개 + dict 등록 1줄)
- ABC 없이 파일 수 최소화, asyncio 롤링 패턴 보존 용이
- 세 번째 포맷 추가 시 ABC 전환해도 비용 동일 (지금 YAGNI 원칙 준수)

### Consequences
- **긍정:** engine.py 80%+ 감소, 단위 테스트 가능, 새 형식 추가 비용 10x 감소
- **부정:** 포맷 인터페이스 타입 강제 없음 (세 번째 포맷 추가 시 ABC 리팩터 필요)
- **보너스:** multi 경로 기존 버그 4건 Phase 2에서 함께 수정

### Follow-ups
- Phase 3 완료 후: 벤치마크 테스트로 병렬 성능 검증
- 향후: `orchestrator.py` 내부 리팩터 (DebateOrchestrator ↔ OptimizedDebateOrchestrator 통합 — 별도 계획)
- 향후: 세 번째 포맷 추가 시 `formats.py` → `formats/` 디렉토리 + ABC 전환

---

## 최종 목표 요약

| 지표 | 현재 | 목표 | 측정 방법 |
|---|---|---|---|
| engine.py 줄 수 | 1,716줄 | ≤ 350줄 | `wc -l` |
| 새 형식 추가 비용 | 286줄 파악 필요 | ≤ 30줄 작성 | 코드 리뷰 |
| judge/ELO 모듈 수 | 3개 파일 | 1개 (`helpers.py`) | import 추적 |
| 핵심 루프 줄 수 | 286줄 | ≤ 200줄 | `wc -l` |
| 단위 테스트 가능 | 불가 | 가능 | pytest 통과 |
| multi 경로 버그 | 4건 | 0건 | Phase 2 체크리스트 |

---

## Changelog (합의 과정 수정 사항)

1. **ABC Strategy → 함수 dispatch**: Architect 지적 "포맷 2개에 과설계" 수용. `formats/` 디렉토리 + `base.py` 불필요, 단일 `formats.py` 채택.
2. **multi 경로 버그 4건 명시**: Critic 발견. Phase 2 수용 기준에 버그 수정 항목 명시.
3. **re-export 전략 전면 명시**: Critic 발견. 모든 이동 심볼에 대한 engine.py/orchestrator.py re-export 표 추가.
4. **calculate_elo 배치 변경**: Architect 권고. `judge.py` 대신 `helpers.py`로 배치 (순수 수학 함수, judge와 분리).
5. **성능 검증 기준 구체화**: Critic 지적. Phase 3 수용 기준에 mock 기반 타이밍 테스트 추가.
6. **SSE-before-commit 명시**: Architect 지적. `MatchFinalizer.finalize()` 주석에 순서 명시.
