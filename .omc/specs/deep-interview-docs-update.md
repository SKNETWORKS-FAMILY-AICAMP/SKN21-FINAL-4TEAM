# Deep Interview Spec: 프로젝트 문서 전체 최신화

## Metadata
- Interview ID: di-docs-update-001
- Rounds: 4
- Final Ambiguity Score: 18%
- Type: brownfield
- Generated: 2026-03-12
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.90 | 35% | 0.315 |
| Constraint Clarity | 0.80 | 25% | 0.200 |
| Success Criteria | 0.75 | 25% | 0.188 |
| Context Clarity | 0.80 | 15% | 0.120 |
| **Total Clarity** | | | **0.823** |
| **Ambiguity** | | | **17.7%** |

## Goal
현재 코드베이스(2026-03-12 기준)와 완전히 일치하도록 프로젝트 문서를 전면 재작성·신규 작성한다.
팔로우/알림 시스템 추가, services/ 도메인별 재편, UI 개선 등 최근 변경사항을 모두 반영한다.

## Scope: 3개 작업 영역

### 1. ChangeLog.md 업데이트
- 파일: `docs/ChangeLog.md`
- 추가할 커밋:
  - `76e8924` — feat: 팔로우 & 인페이지 알림 시스템 구현
  - `855a08a` — feat: 토론 관전·랭킹 화면 정보 계층화 UI 개선
- 형식: 기존 ChangeLog 섹션 형식 유지

### 2. 기존 모듈 문서 12개 완전 재작성
- 디렉토리: `docs/modules/debate/`
- 대상 파일 (12개):
  - `agent_service.md`
  - `broadcast.md`
  - `engine.md` ← 알림 훅 연동 추가됨
  - `matching_service.md`
  - `match_service.md` ← 예측투표 결과 알림 연동 추가됨
  - `orchestrator.md`
  - `promotion_service.md`
  - `season_service.md`
  - `tool_executor.md`
  - `topic_service.md`
  - `tournament_service.md`
  - `ws_manager.md`
- 각 파일: 현재 코드를 직접 읽고 완전 재작성
  - 서비스 경로: `services/debate/` 반영
  - 주요 메서드 시그니처 + 역할
  - 의존성 (다른 서비스, 모델)
  - 신규 연동 포인트 반영 (알림, 팔로우 등)

### 3. 신규 모듈 문서 2개 작성
- `docs/modules/debate/follow_service.md`
- `docs/modules/debate/notification_service.md`
- 형식: 기존 모듈 문서와 동일 구조

## Constraints
- 문서 형식: 기존 docs/modules/debate/ 문서와 동일한 Markdown 구조 유지
- 신규 문서 위치: docs/modules/debate/ (전용 서브디렉토리 X)
- CLAUDE.md 파일은 이번 범위에서 제외
- 코드를 직접 읽고 작성 — 추측 금지

## Non-Goals
- CLAUDE.md 파일 업데이트 (루트/백엔드/프론트엔드)
- architecture/ 문서 업데이트
- dev-guide/ 문서 업데이트
- API 명세서 별도 생성

## Acceptance Criteria
- [ ] `docs/ChangeLog.md` — 팔로우/알림 시스템 및 UI 개선 섹션 추가
- [ ] `docs/modules/debate/engine.md` — 알림 훅 (match_started/match_finished) 반영
- [ ] `docs/modules/debate/match_service.md` — 예측투표 결과 알림 연동 반영
- [ ] `docs/modules/debate/` 기존 12개 파일 — services/debate/ 경로 반영하여 재작성
- [ ] `docs/modules/debate/follow_service.md` — 신규 작성
- [ ] `docs/modules/debate/notification_service.md` — 신규 작성
- [ ] 모든 문서의 import 경로가 현재 코드와 일치

## Technical Context (Brownfield)

### 최근 주요 변경사항
1. **팔로우/알림 시스템** (2026-03-12, commit 76e8924)
   - 신규: `backend/app/services/follow_service.py`
   - 신규: `backend/app/services/notification_service.py`
   - 신규: `backend/app/models/user_follow.py`, `user_notification.py`
   - 신규: `backend/app/api/follows.py`, `notifications.py`
   - 변경: `engine.py` — run_debate에 match_started/match_finished 알림 훅
   - 변경: `match_service.py` — resolve_predictions 후 알림 생성

2. **services/ 도메인별 재편** (2026-03-11, commit 직전)
   - 기존: `services/debate_engine.py` → 변경: `services/debate/engine.py`
   - 기존: `services/debate_matching_service.py` → `services/debate/matching_service.py`
   - 전체 12개 서비스가 `services/debate/` 하위로 이동

3. **UI 개선** (2026-03-12, commit 855a08a)
   - 토론 관전·랭킹 화면 정보 계층화
   - 프론트엔드 컴포넌트 변경 (docs 영향 없음)

### 코드베이스 현황
- 백엔드 단위 테스트: 311개 통과
- 마이그레이션 최신 버전: `n4o5p6q7r8s9`
- Python: `backend/app/services/debate/` (12개 서비스)
- 팔로우/알림: `backend/app/services/` 루트 (도메인 재편 전 위치, 의도적)

## Ontology (Key Entities)
| Entity | Fields | Relationships |
|--------|--------|---------------|
| follow_service.py | follow, unfollow, get_following, get_follower_count, is_following, get_follower_user_ids | UserFollow 모델, NotificationService |
| notification_service.py | create, create_bulk, get_list, get_unread_count, mark_read, mark_all_read, notify_match_event, notify_prediction_result, notify_new_follower | UserNotification 모델, FollowService |
| engine.py (updated) | run_debate에 알림 훅 추가 | NotificationService (별도 세션) |
| match_service.py (updated) | resolve_predictions 후 알림 | NotificationService (별도 세션) |

## Interview Transcript
<details>
<summary>Full Q&A (4 rounds)</summary>

### Round 1
**Q:** 어떤 문서들을 최신화하고 싶으신가요?
**A:** ChangeLog.md, docs/modules/ 모듈 문서, 신규 기능 문서 작성
**Ambiguity:** 52% (Goal: 0.70, Constraints: 0.25, Criteria: 0.25)

### Round 2
**Q:** 팔로우/알림 시스템 신규 문서는 어디에, 어떤 형식으로 작성할까요?
**A:** docs/modules/debate/ 동일 형식
**Ambiguity:** 39% (Goal: 0.80, Constraints: 0.55, Criteria: 0.30)

### Round 3
**Q:** 문서가 "다 됩다"는 거 언제라고 볼 수 있을까요?
**A:** 전체 문서 코드 맞춤화
**Ambiguity:** 26% (Goal: 0.85, Constraints: 0.70, Criteria: 0.60)

### Round 4 (Contrarian Mode)
**Q:** 기존 모듈 문서 12개를 "코드 맞춤화"할 때, 어떤 수준으로 업데이트할까요?
**A:** 완전 재작성
**Ambiguity:** 18% (Goal: 0.90, Constraints: 0.80, Criteria: 0.75)

</details>
