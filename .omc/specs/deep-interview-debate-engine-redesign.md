# Deep Interview Spec: 토론 엔진 클래스/인터페이스 재설계

## Metadata
- Interview ID: di-debate-engine-20260313
- Rounds: 11
- Final Ambiguity Score: 11%
- Type: brownfield
- Generated: 2026-03-13
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown
| 차원 | 점수 | 무게 | 가중치 |
|---|---|---|---|
| 목표 명확도 | 0.85 | 35% | 0.298 |
| 제약 명확도 | 0.80 | 25% | 0.200 |
| 성공 기준 | 0.85 | 25% | 0.213 |
| 컨텍스트 명확도 | 0.80 | 15% | 0.120 |
| **총 명확도** | | | **0.831** |
| **모호성** | | | **11%** |

---

## Goal

`engine.py`(1,716줄) + `orchestrator.py`(534줄)를 **클래스/인터페이스 기반**으로 재설계해 유지보수성을 대폭 향상시킨다. 새 토론 형식 추가, judge/ELO 로직 수정, 디버깅이 현재보다 명확하게 가능한 구조로 만든다.

---

## 핵심 문제 (현재 상태)

| 문제 | 증거 |
|---|---|
| `engine.py`가 너무 큰 단일 파일 | 1,716줄, 함수 20개 이상 |
| `_run_turn_loop`이 모든 로직을 담당 | 조건 분기·LLM 호출·검토·점수 산정 혼재 |
| judge/ELO 로직 분산 | `orchestrator.py` + `engine.py` + `promotion_service.py`에 각각 존재 |
| 새 형식 추가 시 `_run_turn_loop` 전체 파악 필요 | 멀티에이전트(`_execute_multi`) 추가 시 이미 겪음 |
| 디버깅 시 함수 간 컨텍스트 추적 어려움 | match_id, turn, agent 등 파라미터가 다른 시그니처로 전달됨 |

---

## Constraints

- **프론트엔드 코드는 변경하지 않는다** — SSE 이벤트명, API 응답 스키마, WebSocket 프로토콜 유지 필수
- 백엔드 `services/` 내부 구조는 자유롭게 변경 가능
- DB 스키마는 가능하면 변경하지 않는다 (필요 시 컬럼 추가 허용)
- `api/` 라우터 시그니처는 최대한 유지 (호출 방식은 내부에서 위임만 변경)

---

## 병렬 실행 정책

`OptimizedDebateOrchestrator`의 `asyncio.gather(A검토, B실행)` 패턴(턴 지연 37% 단축)은 **새 구조에서도 자연스럽게 수용되도록 설계**한다. 억지로 유지할 필요는 없지만 성능 저하는 허용하지 않는다.

---

## Non-Goals

- 프론트엔드 컴포넌트 변경
- SSE 이벤트 스키마 변경
- 성능 최적화 (현재 37% 단축은 유지, 추가 최적화는 이번 범위 아님)
- 새 기능 추가 (리팩터링만)
- 멀티에이전트 형식 직접 구현 (확장 가능하게만 설계)

---

## Acceptance Criteria

- [ ] 새 토론 형식 추가 시 작성해야 할 코드가 30줄 이내로 끝난다
- [ ] `_run_turn_loop` 또는 그 대체 메서드가 200줄 이하다
- [ ] judge/ELO 로직이 단일 클래스/모듈에 집중된다 (`orchestrator.py`와 분리)
- [ ] 테스트는 새 구조에 맞춰 완전히 재작성 가능 (핵심 시나리오: 토론 실행·판정·ELO 갱신은 반드시 커버)
- [ ] 1vs1 형식을 나중에 멀티에이전트로 확장할 때 새 클래스 하나 추가로 가능하다
- [ ] `engine.py`의 최종 줄 수가 현재(1,716줄) 대비 40% 이상 줄어든다

---

## 선호 설계 방향: 클래스/인터페이스 기반

### 제안 구조 (참고용 — Planner/Architect가 최종 결정)

```
services/debate/
├── engine.py              # 얇은 오케스트레이션 레이어만 남김 (진입점)
├── orchestrator.py        # 현행 유지 (검토/판정 LLM 호출)
├── formats/               # 새 디렉토리
│   ├── base.py            # DebateFormat 추상 기반 클래스
│   ├── one_vs_one.py      # 1vs1 형식 구현
│   └── multi_agent.py     # (미래) 멀티에이전트 확장 자리
├── turn_executor.py       # 턴 실행 로직 (LLM 호출, WebSocket 분기) 분리
└── judge.py               # judge() + ELO 계산 + 승급전 체크 통합
```

### 핵심 인터페이스 아이디어

```python
class DebateFormat(ABC):
    """새 형식 추가 시 이 클래스만 구현하면 됨."""
    @abstractmethod
    async def run(self, ctx: DebateContext) -> MatchResult: ...

class TurnExecutor:
    """LLM 호출 / WebSocket 분기 로직 캡슐화."""
    async def execute(self, agent: DebateAgent, ctx: TurnContext) -> TurnResult: ...

class DebateJudge:
    """judge() + ELO + 승급전 체크 통합. 현재 3개 파일에 분산된 로직 집결."""
    async def finalize(self, ctx: DebateContext) -> MatchResult: ...
```

---

## 영향 범위 (현재 코드베이스 기준)

| 파일 | 현재 줄 수 | 예상 변화 |
|---|---|---|
| `services/debate/engine.py` | 1,716줄 | 대폭 축소 (목표 <1,000줄 또는 분리) |
| `services/debate/orchestrator.py` | 534줄 | judge 로직 → 새 `judge.py`로 이동 |
| `services/debate/promotion_service.py` | 미확인 | ELO 부분 → `judge.py`에서 호출 |
| `services/debate/formats/` | 없음 | 새로 생성 |
| `services/debate/turn_executor.py` | 없음 | 새로 생성 (engine.py에서 분리) |

---

## Assumptions Exposed & Resolved

| 가정 | 질문 | 결론 |
|---|---|---|
| "어렵다" = 줄 수 문제 | Contrarian: 지금 안 고쳐도 되는 이유? | 새 기능 추가·버그 수정·테스트 작성 모두 막히는 복합 문제 |
| API 시그니처도 바꿔야 할 수 있다 | 제약 확인 | 프론트만 안 바뀌면 됨 — 백엔드 내부는 전부 자유 |
| 멀티에이전트도 같이 고쳐야 한다 | 범위 확인 | 확장 가능하게만 설계, 직접 구현은 이번 범위 아님 |

---

## Technical Context (현재 코드베이스)

```
engine.py 주요 함수:
  _run_turn_loop()     — 모든 턴 로직 담당 (가장 크고 복잡)
  _execute_turn()      — 단일 턴 LLM 호출
  _execute_turn_with_retry()
  _build_messages()    — system_prompt + context 조립
  _finalize_match()    — 결과 저장 + ELO 갱신
  _settle_forfeit()    — 몰수패 처리
  _execute_multi_and_finalize() — 멀티에이전트 (별도 분기)

orchestrator.py:
  JUDGE_SYSTEM_PROMPT  — 판정 LLM 프롬프트
  REVIEW_SYSTEM_PROMPT — 검토 LLM 프롬프트
  DebateOrchestrator   — 기본 검토
  OptimizedDebateOrchestrator — asyncio.gather 병렬 실행 (37% 단축)

현재 judge/ELO 흐름:
  orchestrator.judge() → _finalize_match() → promotion_service.check_promotion()
  → 세 파일에 걸쳐 있음
```

---

## Interview Transcript

<details>
<summary>전체 Q&A (9라운드)</summary>

### Round 1
**Q:** 어떤 아키텍처를 변경하고 싶으신가요?
**A:** 토론 엔진 흐름
**Ambiguity:** 85%

### Round 2
**Q:** 어떤 부분이 가장 문제라고 느끼시나요?
**A:** 전체적인 재설계
**Ambiguity:** 75%

### Round 3
**Q:** 기존 코드 교체 동기 vs 새 기능 추가 동기?
**A:** 기존 코드가 다루기 어렵다
**Ambiguity:** 75%

### Round 4 [Contrarian Mode]
**Q:** 지금 당장 수정하지 않아도 되는 이유가 있나요?
**A:** 복합적 이유 (새 형식 추가, 버그 수정, 테스트 작성 모두 막힘)
**Ambiguity:** 65%

### Round 5
**Q:** engine.py를 열었을 때 가장 곤란했던 상황은?
**A:** 새 기능 관련 상황 모두 해당
**Ambiguity:** 65%

### Round 6 [Simplifier Mode]
**Q:** 재설계 성공의 최소 조건은?
**A:** 새 형식 추가 쉬움 + judge/ELO 한곳에 + _run_turn_loop 200줄 이내
**Ambiguity:** 35%

### Round 7
**Q:** API 구조 제약은?
**A:** 프론트 코드만 변경하지 않는 선이면 다 괜찮음
**Ambiguity:** 24%

### Round 8
**Q:** 멀티에이전트 포함 범위?
**A:** 나중에 멀티 확장 가능하도록 (직접 구현은 이번 범위 밖)
**Ambiguity:** 22%

### Round 9
**Q:** 선호하는 설계 패턴?
**A:** 클래스/인터페이스 재설계 (DebateFormat, TurnExecutor, JudgeStrategy)
**Ambiguity:** 17% ✅

</details>
