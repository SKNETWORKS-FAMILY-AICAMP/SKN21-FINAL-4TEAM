# promotion_service.py 모듈 명세

**파일 경로:** `backend/app/services/debate/promotion_service.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

ELO가 티어 경계를 넘을 때 즉시 티어를 변경하는 대신, 승급전(3판 2선승) 또는 강등전(1판 필승) 시리즈를 생성하여 결과에 따라 티어를 결정한다.

---

## 주요 상수

| 상수 | 값 | 설명 |
|---|---|---|
| `TIER_ORDER` | `["Iron","Bronze","Silver","Gold","Platinum","Diamond","Master"]` | 티어 순서. 인덱스가 낮을수록 하위 티어 |

---

## DebatePromotionService

생성자: `__init__(self, db: AsyncSession)`

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `get_active_series` | `(agent_id: str) -> DebatePromotionSeries \| None` | 에이전트의 현재 활성(`status="active"`) 시리즈 조회 |
| `get_series_history` | `(agent_id: str, limit: int = 20, offset: int = 0) -> list[DebatePromotionSeries]` | 시리즈 이력 (created_at DESC) |
| `create_promotion_series` | `(agent_id, from_tier, to_tier) -> DebatePromotionSeries` | 승급전 시리즈 생성 (`required_wins=2`, 3판 2선승) |
| `create_demotion_series` | `(agent_id, from_tier, to_tier) -> DebatePromotionSeries` | 강등전 시리즈 생성 (`required_wins=1`, 1판 필승) |
| `record_match_result` | `(series_id: str, result: str) -> dict` | 시리즈에 매치 결과(`'win'`/`'loss'`) 기록. 종료 조건 충족 시 티어 변경 및 에이전트 상태 갱신 |
| `cancel_series` | `(agent_id: str) -> None` | 활성 시리즈를 `"cancelled"` 상태로 전환 |
| `check_and_trigger` | `(agent_id, old_elo, new_elo, current_tier, protection_count) -> DebatePromotionSeries \| None` | ELO 변화로 승급전/강등전 트리거 여부 확인 후 시리즈 생성 |
| `_create_series` | `(agent_id, series_type, from_tier, to_tier, required_wins) -> DebatePromotionSeries` | 시리즈 생성 공통 로직. `DebateAgent.active_series_id` 갱신 포함 |

### `record_match_result` 종료 조건

- 승급전 (`required_wins=2`, `max_losses=1`): `current_wins >= 2` → 시리즈 승리, `current_losses > 1` → 시리즈 패배
- 강등전 (`required_wins=1`, `max_losses=2`): `current_wins >= 1` → 시리즈 승리, `current_losses > 2` → 시리즈 패배

### 시리즈 종료 시 에이전트 상태 변경

| 상황 | 결과 |
|---|---|
| 승급전 승리 | `tier = to_tier`, `tier_protection_count = 3`, `active_series_id = None` |
| 승급전 패배 | `active_series_id = None` (티어 유지) |
| 강등전 승리 | `tier_protection_count = 1`, `active_series_id = None` (티어 유지) |
| 강등전 패배 | `tier = to_tier`, `active_series_id = None` |

### `check_and_trigger` 트리거 조건

- `old_tier == new_tier`: 트리거 없음
- 이미 활성 시리즈 있음: 트리거 없음
- 승급 방향 + `old_tier != "Master"`: `create_promotion_series()` 호출
- 강등 방향 + `old_tier != "Iron"` + `protection_count == 0`: `create_demotion_series()` 호출
- 강등 방향 + `protection_count > 0`: 시리즈 미생성 (보호 소진 처리는 호출자 `update_elo`가 담당)

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.models.debate_agent` | `DebateAgent` |
| `app.models.debate_promotion_series` | `DebatePromotionSeries` |
| `app.services.debate.agent_service` | `get_tier_from_elo` (지연 임포트) |

---

## 호출 흐름

```
engine.py (_finalize_match 또는 _handle_forfeit)
  → DebateAgentService.update_elo()
      → DebatePromotionService.check_and_trigger()
          → create_promotion_series() 또는 create_demotion_series()
              → _create_series()

engine.py (시리즈 소속 매치 완료 시)
  → DebatePromotionService.record_match_result()
      → 종료 조건 충족 시 UPDATE debate_agents (tier, protection_count, active_series_id)

matching_service.py (ready_up)
  → DebatePromotionService.get_active_series() — 매치에 series_id 태깅
```

---

## `record_match_result` 반환 dict 구조

```python
{
    "series_id": str,
    "series_type": str,          # "promotion" | "demotion"
    "status": str,               # "active" | "won" | "lost"
    "current_wins": int,
    "current_losses": int,
    "required_wins": int,
    "from_tier": str,
    "to_tier": str,
    "tier_changed": bool,
    "new_tier": str | None,
}
```

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
