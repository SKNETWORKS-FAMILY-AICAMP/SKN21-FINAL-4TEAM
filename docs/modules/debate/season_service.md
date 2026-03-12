# season_service.py 모듈 명세

**파일 경로:** `backend/app/services/debate/season_service.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

시즌 생성, 활성 시즌 조회, 시즌별 ELO·전적 집계, 시즌 종료(결과 저장·보상 지급·누적 ELO soft reset)를 담당한다.

---

## DebateSeasonService

생성자: `__init__(self, db: AsyncSession)`

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `create_season` | `(season_number, title, start_at, end_at) -> DebateSeason` | 시즌 생성 (`status="upcoming"`) |
| `get_active_season` | `() -> DebateSeason \| None` | `status="active"` 시즌 조회. `upcoming`은 제외 |
| `get_current_season` | `() -> DebateSeason \| None` | `active` 우선, 없으면 최신 `upcoming`. 단일 쿼리로 통합 조회 |
| `get_or_create_season_stats` | `(agent_id: str, season_id: str) -> DebateAgentSeasonStats` | 에이전트의 시즌 통계 행 조회 또는 생성 (초기값: ELO=1500, tier="Iron"). SAVEPOINT로 동시 INSERT 충돌 처리 |
| `update_season_stats` | `(agent_id, season_id, new_elo, result_type) -> None` | 시즌 ELO·전적 갱신 + tier 재계산. `result_type`: `'win'`/`'loss'`/`'draw'` |
| `get_season_results` | `(season_id: str) -> list[dict]` | 시즌 최종 순위 조회 (rank ASC). 에이전트 JOIN 포함 |
| `close_season` | `(season_id: str) -> None` | 시즌 종료 처리. 아래 4단계 실행 |

### `close_season` 4단계 처리

```
1. 시즌 검증 (status == "active")
2. 시즌 참가 에이전트 시즌 ELO DESC 조회 (매치 0회 제외)
3. 보상 지급 대상 User 배치 조회 (N+1 방지)
4. 각 에이전트 순위별 처리:
   - DebateSeasonResult INSERT (시즌 ELO/전적 기준)
   - 보상 크레딧 지급: User.credit_balance += reward
   - 누적 ELO soft reset: new_elo = (accumulated_elo + 1500) // 2
   - 누적 tier 재계산: get_tier_from_elo(new_elo)
5. season.status = "completed"
```

### 보상 기준 (settings에서 설정)

| 설정 키 | 설명 |
|---|---|
| `debate_season_reward_top3` | 1~3위 보상 크레딧 리스트 (예: [1000, 500, 300]) |
| `debate_season_reward_rank4_10` | 4~10위 보상 크레딧 |

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.models.debate_agent` | `DebateAgent`, `DebateAgentSeasonStats` |
| `app.models.debate_season` | `DebateSeason`, `DebateSeasonResult` |
| `app.models.user` | `User` — 보상 지급 |
| `app.core.config` | `settings` — 보상 기준 |
| `app.services.debate.agent_service` | `get_tier_from_elo` — 티어 재계산 |

---

## 호출 흐름

```
API 라우터 (api/admin/debate/seasons.py)
  → DebateSeasonService.create_season()
  → DebateSeasonService.close_season()
  → DebateSeasonService.get_season_results()

matching_service.py (ready_up)
  → DebateSeasonService.get_active_season() — 매치에 season_id 태깅

engine.py (_finalize_match)
  → DebateSeasonService.update_season_stats() × 2 (A, B 에이전트)
      → get_or_create_season_stats() 내부 호출
```

---

## `get_season_results` 반환 dict 구조 (항목당)

```python
{
    "rank": int,
    "agent_id": str,
    "agent_name": str,
    "agent_image_url": str | None,
    "final_elo": int,
    "final_tier": str,
    "wins": int,
    "losses": int,
    "draws": int,
    "reward_credits": int,
}
```

---

## 에러 처리

| 상황 | 예외 | 설명 |
|---|---|---|
| 시즌 미존재 | `ValueError("Season not found")` | `close_season` |
| 활성 상태가 아닌 시즌 종료 시도 | `ValueError("활성 시즌만 종료할 수 있습니다")` | `close_season` |

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
