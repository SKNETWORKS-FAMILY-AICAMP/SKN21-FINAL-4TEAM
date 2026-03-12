# matching_service.py 모듈 명세

**파일 경로:** `backend/app/services/debate/matching_service.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

큐 등록, 준비 완료 처리, 자동 매칭을 담당한다. `DebateMatchingService`(큐/ready_up)와 `DebateAutoMatcher`(백그라운드 자동 매칭 루프) 두 클래스로 구성된다.

---

## DebateMatchingService

생성자: `__init__(self, db: AsyncSession)`

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `join_queue` | `(user: User, topic_id: str, agent_id: str, password: str \| None) -> dict` | 큐 등록. 토픽·에이전트·크레딧 검증 후 `DebateMatchQueue` INSERT. 상대가 이미 있으면 양방향 `opponent_joined` 이벤트 발행 |
| `ready_up` | `(user: User, topic_id: str, agent_id: str) -> dict` | 준비 완료 처리. ABBA 데드락 방지를 위해 PK 오름차순으로 큐 항목 일괄 잠금. 양쪽 모두 준비되면 `DebateMatch` 생성 |
| `_purge_expired_entries` | `() -> None` | 만료된 큐 항목 일괄 삭제 (내부용) |

### `join_queue` 검증 순서

1. 토픽 존재 + `status == "open"` 확인
2. 비밀번호 보호 토픽이면 password 검증
3. 에이전트 소유권 확인 (admin/superadmin은 모든 에이전트 사용 가능)
4. API 키 검증: `local` / BYOK / `use_platform_credits` 중 하나 충족 필요
5. 크레딧 잔액 사전 확인 (`debate_credit_cost > 0 && credit_system_enabled`)
6. 만료된 큐 항목 정리 (`_purge_expired_entries`)
7. 유저당 1개 큐 제한 (admin 제외) → `QueueConflictError`
8. 에이전트당 1개 큐 제한 → `QueueConflictError` 또는 `ValueError`
9. `DebateMatchQueue` INSERT (UniqueConstraint race condition 처리)
10. 상대 존재 시 양방향 `opponent_joined` 이벤트 발행

### `ready_up` 매치 생성 흐름

```
토픽 전체 큐 항목 PK 오름차순 WITH FOR UPDATE 잠금
→ 내 항목 찾기 (없으면 ValueError)
→ 이미 ready이면 멱등 처리 반환
→ my_entry.is_ready = True
→ 상대 미존재: waiting_for_opponent 반환
→ 상대 미준비: countdown_started 이벤트 양방향 발행
→ 양쪽 모두 준비: DebateMatch 생성
    → DebateSeasonService.get_active_season() → season_id 태깅
    → DebatePromotionService.get_active_series() × 2 → series_id/match_type 태깅
    → 큐 항목 삭제 → matched 이벤트 발행
    → run_debate(match_id) 백그라운드 태스크 실행
```

---

## DebateAutoMatcher

싱글톤 백그라운드 자동 매칭 태스크.

생성자: `__init__(self)` (싱글톤 — `get_instance()` 사용)

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `get_instance` | `() -> DebateAutoMatcher` | 싱글톤 인스턴스 반환 |
| `start` | `() -> None` | lifespan에서 호출. 백그라운드 루프 태스크 시작 |
| `stop` | `() -> None` | 앱 종료 시 루프 태스크 취소 |
| `_loop` | `() -> None` | 주기적 점검 루프 (`debate_auto_match_check_interval`초마다 실행) |
| `_purge_expired_queue_entries` | `() -> None` | 만료된 큐 항목 삭제 + `timeout` SSE 이벤트 발행 |
| `_check_stale_entries` | `() -> None` | 장시간 대기 큐 항목 탐지 → `_auto_match_with_platform_agent()` 호출 |
| `_check_stuck_matches` | `() -> None` | `pending`/`waiting_agent` 상태로 오래 멈춘 매치 → `error` 상태로 전환 |
| `_auto_match_with_platform_agent` | `(db, entry: DebateMatchQueue) -> None` | `is_platform=True` 에이전트 중 random() 선택 → `DebateMatch` 생성 → `run_debate` 시작 |

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.core.auth` | `verify_password` — 토픽 비밀번호 검증 |
| `app.core.config` | `settings` — 큐 타임아웃, 준비 카운트다운, 자동 매칭 주기 등 |
| `app.core.database` | `async_session` — 자동 매칭 독립 세션 |
| `app.core.exceptions` | `QueueConflictError` |
| `app.models.debate_agent` | `DebateAgent` |
| `app.models.debate_match` | `DebateMatch`, `DebateMatchQueue` |
| `app.models.debate_topic` | `DebateTopic` |
| `app.services.debate.agent_service` | `get_latest_version` — 버전 스냅샷 연결 |
| `app.services.debate.broadcast` | `publish_queue_event` — 큐 SSE 이벤트 발행 |
| `app.services.debate.engine` | `run_debate` — 토론 엔진 시작 |
| `app.services.debate.promotion_service` | `DebatePromotionService` — 시리즈 태깅 |
| `app.services.debate.season_service` | `DebateSeasonService` — 시즌 태깅 |

---

## 관련 설정값

| 설정 키 | 설명 |
|---|---|
| `debate_queue_timeout_seconds` | 큐 항목 만료 시간 (기본 120초) |
| `debate_ready_countdown_seconds` | ready_up 후 카운트다운 초 |
| `debate_auto_match_check_interval` | 자동 매칭 루프 점검 주기 (초) |
| `debate_pending_timeout_seconds` | pending 매치 타임아웃 (기본 600초) |
| `debate_credit_cost` | 매치당 크레딧 비용 |
| `credit_system_enabled` | 크레딧 시스템 활성화 여부 |

---

## 에러 처리

| 상황 | 예외 | 설명 |
|---|---|---|
| 토픽 미존재/비개방 | `ValueError` | HTTP 400/404 |
| 비밀번호 불일치 | `ValueError("비밀번호가 올바르지 않습니다")` | HTTP 400 |
| 에이전트 미존재/비소유 | `ValueError("Agent not found or not owned by user")` | HTTP 404 |
| 유저 큐 중복 | `QueueConflictError` | HTTP 409 |
| 에이전트 큐 중복 | `QueueConflictError` 또는 `ValueError` | HTTP 409/400 |
| 크레딧 부족 | `ValueError("크레딧이 부족합니다...")` | HTTP 400 |
| ready_up 시 큐 미존재 | `ValueError("Not in queue")` | HTTP 400 |

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
