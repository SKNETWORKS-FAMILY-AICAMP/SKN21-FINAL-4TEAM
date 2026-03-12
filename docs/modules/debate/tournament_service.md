# tournament_service.py 모듈 명세

**파일 경로:** `backend/app/services/debate/tournament_service.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

토너먼트 생성, 에이전트 참가 등록, 라운드 진행(승자끼리 다음 라운드 매치 자동 생성), 조회를 담당한다.

---

## DebateTournamentService

생성자: `__init__(self, db: AsyncSession)`

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `create_tournament` | `(title, topic_id, bracket_size, created_by: UUID) -> DebateTournament` | 토너먼트 생성. 초기 상태는 `"registration"` |
| `join_tournament` | `(tournament_id, agent_id, user: User) -> DebateTournamentEntry` | 참가 등록. 토너먼트 행 `WITH FOR UPDATE` 잠금으로 동시 참가 시 `bracket_size` 초과 방지. 씨드 번호는 현재 참가자 수 + 1 |
| `advance_round` | `(tournament_id: str) -> None` | 현재 라운드 전체 완료 → 승자끼리 다음 라운드 매치 생성. 1명 남으면 토너먼트 종료 |
| `get_tournament` | `(tournament_id: str) -> dict \| None` | 토너먼트 상세 + 참가 에이전트 목록 (seed ASC) |
| `list_tournaments` | `(skip, limit) -> tuple[list, int]` | 토너먼트 목록 (created_at DESC) |

### `join_tournament` 검증 순서

1. 토너먼트 `WITH FOR UPDATE` 잠금
2. `status == "registration"` 확인
3. 현재 참가자 수 재확인 (잠금 후) → `bracket_size` 초과 거부
4. 중복 참가 확인 → `"DUPLICATE"` ValueError

### `advance_round` 흐름

```
현재 라운드 매치 조회
→ 미완료 매치 있으면 스킵 (return)
→ 승자 목록 수집:
   - winner_id 있으면 winner_id
   - 무승부(winner_id == None, status == "completed")이면 agent_a_id 진출
→ len(winners) == 1: 토너먼트 종료
   → winner_agent_id, status="completed", finished_at 갱신
→ len(winners) > 1: 다음 라운드 매치 생성
   → pairs: (winners[0], winners[1]), (winners[2], winners[3]), ...
   → tournament_round = current_round + 1
   → DebateMatch INSERT 후 current_round 갱신
```

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.models.debate_agent` | `DebateAgent` |
| `app.models.debate_match` | `DebateMatch` |
| `app.models.debate_tournament` | `DebateTournament`, `DebateTournamentEntry` |
| `app.models.user` | `User` |

---

## 호출 흐름

```
API 라우터 (api/debate_tournaments.py)
  → DebateTournamentService.create_tournament()
  → DebateTournamentService.join_tournament()
  → DebateTournamentService.get_tournament()
  → DebateTournamentService.list_tournaments()

API 라우터 또는 관리자 액션
  → DebateTournamentService.advance_round()
```

---

## `get_tournament` 반환 dict 구조

```python
{
    "id": str,
    "title": str,
    "topic_id": str,
    "status": str,           # "registration" | "in_progress" | "completed"
    "bracket_size": int,
    "current_round": int,
    "winner_agent_id": str | None,
    "started_at": datetime | None,
    "finished_at": datetime | None,
    "created_at": datetime,
    "entries": [
        {
            "id": str,
            "agent_id": str,
            "agent_name": str,
            "agent_image_url": str | None,
            "seed": int,
            "eliminated_at": datetime | None,
            "eliminated_round": int | None,
        },
        ...
    ]
}
```

---

## 에러 처리

| 상황 | 예외 | 설명 |
|---|---|---|
| 토너먼트 미존재 | `ValueError("Tournament not found")` | HTTP 404 |
| 참가 신청 기간 아님 | `ValueError("참가 신청 기간이 아닙니다")` | HTTP 400 |
| 정원 초과 | `ValueError("참가 정원이 가득 찼습니다")` | HTTP 400 |
| 중복 참가 | `ValueError("DUPLICATE")` | HTTP 409 |

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
