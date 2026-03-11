# topic_service.py 모듈 명세

**파일 경로:** `backend/app/services/debate/topic_service.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

토론 토픽 CRUD, 목록 조회(페이지네이션·정렬), 스케줄 기반 status 자동 갱신을 담당한다. Redis SET NX EX 패턴으로 멀티 워커 환경에서도 status 동기화 중복 실행을 방지한다.

---

## 주요 상수

| 상수 | 값 | 설명 |
|---|---|---|
| `_TOPIC_SYNC_REDIS_KEY` | `"debate:topic_sync:last_at"` | 스케줄 동기화 분산 락 Redis 키 |
| `_TOPIC_SYNC_INTERVAL_SECS` | `60` | 스케줄 동기화 최소 실행 간격 (초) |

---

## DebateTopicService

생성자: `__init__(self, db: AsyncSession)`

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `create_topic` | `(data: TopicCreate, user: User) -> DebateTopic` | 토픽 생성. 일반 사용자 일일 등록 한도 검사. `scheduled_start_at` 미래이면 `"scheduled"`, 아니면 `"open"`. 비밀번호 설정 가능 |
| `get_topic` | `(topic_id: str) -> DebateTopic \| None` | 단일 토픽 조회 |
| `list_topics` | `(status, sort, page, page_size) -> tuple[list[dict], int]` | 토픽 목록. 집계 서브쿼리(queue_count, match_count)로 N+1 방지. sort: `recent`/`popular_week`/`queue`/`matches` |
| `update_topic` | `(topic_id: str, data: TopicUpdate) -> DebateTopic` | 토픽 수정 (관리자용) |
| `update_topic_by_user` | `(topic_id: UUID, user_id: UUID, payload: TopicUpdatePayload) -> DebateTopic` | 작성자 본인 수정. 소유권 검사 포함 |
| `delete_topic` | `(topic_id: str) -> None` | 토픽 삭제 (관리자용). 매치 없을 때만 허용. 대기 큐 먼저 제거 |
| `delete_topic_by_user` | `(topic_id: UUID, user_id: UUID) -> None` | 작성자 본인 삭제. 진행 중 매치 있으면 거부 |
| `count_queue` | `(topic_id) -> int` | 현재 대기 큐 항목 수 |
| `count_matches` | `(topic_id) -> int` | 테스트 제외 전체 매치 수 |
| `_sync_scheduled_topics` | `() -> None` | scheduled → open (시작 시각 도달), open/in_progress → closed (종료 시각 초과). Redis 분산 락으로 60초 이내 재실행 방지 |

### `list_topics` sort 옵션

| 값 | 정렬 기준 |
|---|---|
| `recent` (기본) | `created_at DESC` |
| `popular_week` | 최근 7일 매치 수 DESC |
| `queue` | 현재 큐 대기 수 DESC |
| `matches` | 전체 매치 수 DESC |

### `_sync_scheduled_topics` 상태 전환 규칙

```
scheduled AND scheduled_start_at <= now  → open
open/in_progress AND scheduled_end_at <= now AND scheduled_end_at IS NOT NULL → closed
```

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.core.auth` | `get_password_hash` — 토픽 비밀번호 해싱 |
| `app.core.redis` | `get_redis` — 스케줄 동기화 분산 락 |
| `app.core.config` | `settings.debate_daily_topic_limit` |
| `app.models.debate_match` | `DebateMatch`, `DebateMatchQueue` |
| `app.models.debate_topic` | `DebateTopic` |
| `app.models.user` | `User` |
| `app.schemas.debate_topic` | `TopicCreate`, `TopicUpdate`, `TopicUpdatePayload` |

---

## 호출 흐름

```
API 라우터 (api/debate_topics.py)
  → DebateTopicService.create_topic()
  → DebateTopicService.list_topics()
      → _sync_scheduled_topics() 자동 호출

API 라우터 (api/admin/debate/topics.py)
  → DebateTopicService.update_topic()
  → DebateTopicService.delete_topic()
```

---

## 에러 처리

| 상황 | 예외 | 설명 |
|---|---|---|
| 일일 등록 한도 초과 | `ValueError("일일 토론 주제 등록 한도...")` | HTTP 400 |
| 토픽 미존재 | `ValueError("Topic not found")` | HTTP 404 |
| 소유권 불일치 | `PermissionError("Not the topic creator")` | HTTP 403 |
| 매치 있는 토픽 삭제 시도 (관리자) | `ValueError("진행된 매치가 N개...")` | HTTP 409 |
| 진행 중 매치 있는 토픽 삭제 시도 (사용자) | `ValueError("진행 중인 매치가 N개...")` | HTTP 409 |

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
