## [2026-03-05] 모델 참조 오류 수정

### Fixed
- app/models/token_usage_log.py: ChatSession relationship 제거 (모델 부재로 인한 mapper 초기화 오류)
- app/models/user.py: 존재하지 않는 모델들의 relationship 제거 (ConsentLog, SpoilerSetting, ChatSession, UserMemory, UserSubscription, UserPersona, PersonaFavorite, PersonaRelationship, Notification)
- tests/unit/services/test_debate_streaming.py: db.execute() mock을 AsyncMock으로 수정 (coroutine 반환)

### Notes
- 전체 단위 테스트 371개 모두 통과

---

## [2026-03-05] Alembic 마이그레이션 squash

### Changed
- alembic/versions/: 기존 마이그레이션 체인 전체 제거 → 단일 베이스라인(0001_baseline)으로 교체

### Notes
- 삭제된 모델 34개 참조 정리
- 새 환경 alembic upgrade head 정상 동작 확인
- 기존 운영 DB가 있다면 alembic stamp 0001_baseline 실행 필요

## [2026-03-05] debate_engine + debate_orchestrator 재작성

### Changed
- debate_orchestrator.py: DebateOrchestrator + OptimizedDebateOrchestrator → 단일 DebateOrchestrator
- debate_engine.py: use_optimized 분기 제거, 항상 asyncio.gather 병렬 실행
- config.py: 항상 True였던 플래그 7개 제거 (debate_turn_review_enabled 등)

### Removed
- config.py: debate_turn_review_enabled, debate_orchestrator_optimized, debate_review_fast_path, debate_turn_review_model, debate_orchestrator_model, debate_summary_enabled
- debate_orchestrator.py: OptimizedDebateOrchestrator 클래스, SCORING_CRITERIA 상수

### Notes
- 외부 인터페이스(API, SSE 이벤트) 변경 없음
- 동작 동일, 코드 복잡도만 감소

---

## [2026-03-05] 프론트엔드 비토론 화면 전체 제거

### Removed
- Pages: chat, character, character-chats, community, favorites, notifications, pending-posts, personas, relationships, sessions (사용자 페이지 10개)
- Admin Pages: content, features, personas, policy, reports, video-gen, world-events (관리자 페이지 7개)
- Components: character, chat, community, live2d, persona, subscription, guide, pending (8개 디렉토리)
- Stores: personaStore, live2dStore, communityStore, creditStore, chatStore, pendingPostStore, worldEventStore, characterChatStore, characterPageStore, notificationStore (10개)
- MyPage tabs: subscription, user-persona, memories, creator (비토론 탭 4개)

### Notes
- AI 토론 전용으로 범위 축소에 따른 프론트엔드 정리
- layout.tsx 네비게이션 및 admin 메뉴에서 삭제된 항목 제거
- UserSidebar: 토론/갤러리/토너먼트/마이페이지 항목만 유지
- Admin Sidebar: 사용자관리/LLM모델/사용량/모니터링/AI토론관리/화면관리만 유지

## [2026-03-05] AI 토론 외 모듈 전체 제거

### Removed
- API: board, character_cards, character_chats, character_pages, chat, credits, favorites, features, image_gen, lorebook, lounge, memories, notifications, pending_posts, personas, policy, relationships, subscriptions, tts, user_personas, webtoons, world_events (사용자 라우터 22개)
- API Admin: agents, board, content, credits, features, personas, policy, reports, subscriptions, system, video_gen, world_events (관리자 라우터 12개)
- Services: adult_verify, agent_activity, agent_scheduler, batch_scheduler, board, character_card, character_chat, character_page, chat, favorite, feature_flag, image_gen, lorebook, moderation, notification, pending_post, persona, policy, quota, rag, relationship, report, review, subscription, tts, user_persona, video_gen, world_event (28개)
- Models: agent_activity_log, board*, character_chat*, chat*, comment_stat, consent_log, credit_cost, episode*, live2d_model, lorebook_entry, notification, pending_post, persona*, review_cache, spoiler_setting, subscription_plan, usage_quota, user_memory, user_persona, user_subscription, video_generation, webtoon, world_event (34개)

### Notes
- AI 토론 시스템 전용 프로젝트로 범위 축소
- main.py 라우터 등록 및 alembic/env.py 모델 import 동시 정리
- 삭제된 모델에 대한 기존 마이그레이션 파일은 유지 (DB 스키마 이력 보존)
