# Deep Interview Spec: 팔로우 & 알림 시스템

## Metadata
- Interview ID: di-follow-notification-001
- Rounds: 7
- Final Ambiguity Score: 16.5%
- Type: brownfield
- Generated: 2026-03-12
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.92 | 35% | 0.322 |
| Constraint Clarity | 0.85 | 25% | 0.213 |
| Success Criteria | 0.75 | 25% | 0.188 |
| Context Clarity | 0.75 | 15% | 0.113 |
| **Total Clarity** | | | **0.835** |
| **Ambiguity** | | | **16.5%** |

## Goal
사용자가 AI 에이전트 및 다른 사용자를 팔로우하고, 팔로우한 대상의 주요 이벤트(매치 시작/종료, 예측투표 결과, 새 팔로워)를 헤더 벨 아이콘 + 드롭다운 알림 파나를 통해 실시간으로 확인할 수 있는 시스템을 구축한다.

## Scope: 4개 핵심 기능

### 1. 팔로우 관계 (Follow Relationship)
- 팔로우 대상: `DebateAgent` + `User` 둘 다
- 팔로우 버튼: 에이전트 상세 페이지 / 사용자 프로필 페이지에 표시
- 팔로우/언팔로우 토글 기능
- 팔로우 상태: 내가 팔로우했는지 여부 표시 (버튼 상태)

### 2. 팔로워 수 표시
- 에이전트 상세 페이지: 팔로워 수 카운트 표시
- 사용자 프로필 페이지(`/mypage` 또는 공개 프로필): 팔로워 수 표시

### 3. 팔로우 리스트
- `/profile/following`: 내가 팔로우하는 에이전트/사용자 목록
- 목록에서 바로 언팔로우 가능

### 4. 인페이지 알림 시스템
- **위치**: 헤더 우측 벨(🔔) 아이콘 + 읽지 않은 수 배지
- **클릭 시**: 드롭다운 알림 파나 (최근 N개 목록)
- **알림 트리거 4가지**:
  1. 내가 팔로우한 **에이전트**의 새 매치 시작
  2. 내가 팔로우한 **에이전트**의 매치 종료 (결과 포함)
  3. 내가 팔로우한 **에이전트** 매치의 예측투표 결과 공개
  4. 내 에이전트 또는 나를 새로 팔로우한 사용자 알림
- **알림 전달 방식**: 서버 → SSE 또는 폴링 (로그인 중인 사용자에게만)
- **읽음 처리**: 클릭 시 읽음 표시

## Constraints (범위 내)
- 백엔드: FastAPI + SQLAlchemy async (기존 패턴 유지)
- 프론트엔드: Next.js 15 App Router + Zustand (기존 패턴 유지)
- 알림: 인페이지 전용 (이메일/브라우저 푸시 X)
- 알림 기술: SSE 또는 폴링 (기존 SSE 패턴 참고: `/api/matches/{id}/stream`)
- 알림 저장: DB 테이블 (`user_notifications`) — 서버 재시작 후에도 유지
- 알림 읽음 처리: DB 업데이트

## Non-Goals (범위 밖)
- 이메일/SMS/브라우저 푸시 알림
- DM(다이렉트 메시지) 기능
- 팔로워 공개/비공개 설정
- 팔로우 승인 요청 (모두 즉시 팔로우)
- 실시간 활동 피드(타임라인)
- 팔로우한 사용자의 댓글/게시물 피드

## Acceptance Criteria
- [ ] `POST /api/follows` — 에이전트 또는 유저 팔로우 (중복 불가)
- [ ] `DELETE /api/follows/{target_type}/{target_id}` — 언팔로우
- [ ] `GET /api/follows/following` — 내 팔로우 목록 (agent/user 구분)
- [ ] `GET /api/agents/{id}` 응답에 `follower_count`, `is_following` 필드 포함
- [ ] `GET /api/auth/me` 응답에 `follower_count` 필드 포함
- [ ] `GET /api/notifications` — 내 알림 목록 (읽음/안읽음 구분)
- [ ] `PUT /api/notifications/{id}/read` — 읽음 처리
- [ ] `PUT /api/notifications/read-all` — 전체 읽음
- [ ] 헤더에 벨 아이콘 + 읽지않은 알림 배지 표시
- [ ] 벨 아이콘 클릭 시 드롭다운 알림 파나 표시
- [ ] 팔로우한 에이전트의 매치 시작 시 알림 생성 (debate_engine 연동)
- [ ] 팔로우한 에이전트의 매치 종료 시 결과 알림 생성
- [ ] 매치 예측투표 결과 공개 시 알림 생성
- [ ] 새 팔로워 생성 시 알림 생성
- [ ] 에이전트 상세 페이지에 팔로우 버튼 + 팔로워 수 표시
- [ ] `/profile/following` 페이지: 팔로우 목록 + 언팔로우 버튼
- [ ] 비로그인 사용자는 팔로우 버튼 클릭 시 로그인 유도

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| 팔로우 대상은 에이전트 | 유저도 팔로우 가능? | 에이전트 + 유저 둘 다 |
| 구독자 수만 보여주면 충분 | 팔로우 버튼/리스트 없으면 활용 어려움 | 버튼 + 수 + 리스트 + 알림 4가지 모두 |
| 알림은 브라우저 푸시 | 인프라 비용/복잡도 이슈 | 인페이지 전용 (SSE/폴링) |
| 알림 파나는 별도 페이지 | 헤더 벨 아이콘이 UX 표준 | 헤더 벨 + 드롭다운 |

## Technical Context (Brownfield)

### 기존 코드 연동 포인트

**백엔드 연동:**
- `debate_engine.py` — 매치 시작/종료 시점에 알림 생성 훅 추가
- `debate_match_predictions.py` — 예측 결과 공개 시 알림 생성
- `backend/app/models/` — `user_follows.py`, `user_notifications.py` 신규 모델
- `backend/app/api/` — `follows.py`, `notifications.py` 신규 라우터

**프론트엔드 연동:**
- `frontend/src/components/layout/Header.tsx` (또는 유사 파일) — 벨 아이콘 추가
- `frontend/src/stores/notificationStore.ts` — 알림 상태 관리
- `frontend/src/app/(user)/debate/agents/[id]/page.tsx` — 팔로우 버튼 추가
- `frontend/src/app/(user)/profile/following/page.tsx` — 신규 페이지

### DB 신규 테이블
```sql
-- 팔로우 관계
user_follows (
  id UUID PK,
  follower_id UUID FK→users,
  target_type VARCHAR(10),  -- 'agent' or 'user'
  target_id UUID,
  created_at TIMESTAMP
  UNIQUE(follower_id, target_type, target_id)
)

-- 알림
user_notifications (
  id UUID PK,
  user_id UUID FK→users,
  type VARCHAR(30),   -- 'match_started', 'match_ended', 'prediction_result', 'new_follower'
  title VARCHAR(100),
  body TEXT,
  link VARCHAR(200),  -- 알림 클릭 시 이동 URL
  is_read BOOLEAN DEFAULT false,
  created_at TIMESTAMP
)
```

## Ontology (Key Entities)
| Entity | Fields | Relationships |
|--------|--------|---------------|
| UserFollow | follower_id, target_type, target_id, created_at | User → DebateAgent 또는 User |
| UserNotification | user_id, type, title, body, link, is_read, created_at | User |

## Interview Transcript
<details>
<summary>Full Q&A (7 rounds)</summary>

### Round 1
**Q:** 소셜 기능으로 어떤 것을 원하시나요?
**A:** 팔로우/구독
**Ambiguity:** 70% (Goal: 0.50, Constraints: 0.10, Criteria: 0.10)

### Round 2
**Q:** 팔로우 대상이 뭔가요? User와 DebateAgent 두 개의 주체가 있습니다.
**A:** 둘 다
**Ambiguity:** 65% (Goal: 0.60, Constraints: 0.15, Criteria: 0.10)

### Round 3
**Q:** 팔로우하면 구체적으로 어떤 일이 일어나나요?
**A:** 구독자 수 표시
**Ambiguity:** 60% (Goal: 0.65, Constraints: 0.20, Criteria: 0.15)

### Round 4 (Contrarian Mode)
**Q:** 구독자 수만 보여주면 충분할까요? 팔로우 버튼이나 리스트가 없어도 되나요?
**A:** 팔로우 버튼 + 구독자 수 + 팔로우 리스트 + 알림 (모두 선택)
**Ambiguity:** 40% (Goal: 0.80, Constraints: 0.65, Criteria: 0.25)

### Round 5
**Q:** 알림 방식은? (페이지 안 토스트, 브라우저 푸시, 이메일)
**A:** 페이지 안 토스트/알림 파나
**Ambiguity:** 32% (Goal: 0.85, Constraints: 0.70, Criteria: 0.45)

### Round 6 (Simplifier Mode)
**Q:** 알림 트리거 이벤트를 고르세요
**A:** 매치 시작 + 매치 종료 + 예측투표 결과 + 새 팔로워 (모두 선택)
**Ambiguity:** 23% (Goal: 0.90, Constraints: 0.75, Criteria: 0.65)

### Round 7
**Q:** 알림 파나를 어디에 배치할까요?
**A:** 헤더 벨 아이콘 (드롭다운)
**Ambiguity:** 16.5% (Goal: 0.92, Constraints: 0.85, Criteria: 0.75)

</details>
