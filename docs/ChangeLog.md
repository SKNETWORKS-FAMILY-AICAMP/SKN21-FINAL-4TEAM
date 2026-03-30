## [2026-03-30] 관리자 UI 개선 — 대시보드·모델 관리·모니터링

### Fixed

- **대시보드 최근 활동** — 플레이스홀더만 표시되던 "최근 활동" 섹션에 실제 데이터 연동 (최근 가입 사용자 5명 + 최근 매치 5건)
- **비활성 모델 사용자 노출** — 에이전트 생성 폼에서 하드코딩된 모델 목록 대신 `GET /api/models` API로 동적 fetch, 관리자가 비활성화한 모델은 사용자 드롭다운에서 자동 제외 (하드코딩 폴백 유지)
- **"비활성" 버튼 폭** — 관리자 LLM 모델 관리 페이지에서 "활성"/"비활성" 텍스트 길이 차이로 버튼 크기가 변하는 문제 수정 (`min-w-[4rem]` 적용)
- **`monitoring.py`** — `now.replace()` 반환값 미사용 버그 수정

### Added

- **모니터링 토론 주제 연동** — `token_usage_logs`에 `match_id` FK 컬럼 추가, LLM 호출 로그에 토론 주제명 표시 (테이블 컬럼 + 상세 모달)
- **마이그레이션** `s0t1u2v3w4x5` — `token_usage_logs.match_id` 컬럼 추가

---

## [2026-03-26] 엔진 안정성·랭킹·커뮤니티·매칭 UX 개선

### Fixed

- **`engine.py` / `forfeit.py`** — 세션 격리·보상 롤백·GC 안전 처리 등 엔진 안정성 전반 개선
- **`forfeit.py` / UI** — 부전패 판정 사유 프론트엔드 표시, 웹 검색 결과 폴백 UI 추가
- **`engine.py`** — 요약 생성 시 마크다운 래핑된 JSON 응답 파싱 오류 해결
- **`engine.py`** — 앱 시작 시 요약 미생성 매치 자동 재시도 로직 추가
- **`matching.py` / `topics`** — 랜덤 매칭 후 중복 참가 에러 및 UX 혼선 수정, 토픽 상세 대신 대기방으로 직접 이동
- **`engine.py` / `finalizer.py`** — 크레딧 환불 버그·ELO 오산정·SSE 격리 수정
- **ranking UI** — 인기 토론 상세 UI 수정(StatCard 줄바꿈·최근 토론 목록), subtitle 주제 작성자 닉네임으로 교체, 인기 토론 순위 주제별 누적 매치 수 기준 재구현

### Added

- **`community`** — 게시글 상세에서 토론 리플레이 바로 보기, 에이전트 이름에 티어 아이콘 뱃지 표시
- **ranking** — 컬럼 10개 제한·내 에이전트 하이라이트·더 보기 버튼, 최근 토론 행 클릭 시 리플레이 자동 시작

### Removed

- **`topics`** — 고급 설정에서 턴 토큰 한도 필드 제거

---

## [2026-03-25] 토론 엔진 버그 수정·Tool Use·debate_formats 리팩토링

### Fixed

- **`orchestrator.py`** — OpenAI strict mode schema 오류 수정, required 배열 누락 수정
- **`evidence_search.py`** — search_by_query LLM 합성 누락으로 영어 raw 내용 출력되던 버그 수정
- **`debate_engine.py`** — 부전패·점수일관성·claim오염·근거무관 버그 4건 수정
- **`debate_engine.py`** — run_turns_multi agent cache miss 시 claims 인덱스 불일치 수정
- **`engine.py` / `orchestrator.py` / `finalizer.py`** — auto-walkthrough 합의 버그 3건 수정
- **`orchestrator.py` / `judge.py`** — off_topic 심각도 기준 추가, minor 위반 Judge 가시성 확보
- **`config.py`** — `debate_forfeit_on_severe_streak` 5 → 3 조정
- **`debate.py`** — `tool_used` / `tool_result` 컬럼을 `DebateTurnLog` 생성 시 직접 세팅

### Added

- **`evidence_search.py`** — `EvidenceResult`에 `raw_content` 필드 추가 및 오케스트레이터 교차검증 연결
- **`evidence_search.py`** — Tool Use: URL 실제 fetch + 본문 기반 근거 합성
- **debate UI** — Tool Use 사용 여부를 헤더 뱃지로 실시간 표시

### Refactored

- **`debate_formats.py`** — god-file 분리 (1262→255줄): `format_1v1.py` / `format_multi.py` 분리

---

## [2026-03-24] dev-guide 최신화 — 테이블 수·마이그레이션·서비스·스토어 목록 갱신

### Changed

- `docs/dev-guide.md` — 단위 테스트 수 252개 수정, 마이그레이션 체인 최신화 + 다중 헤드 주의사항
- `docs/dev-guide/backend.md` — 테이블 수 22개로 수정, 누락 테이블 4개 추가(user_follows/notifications/community_posts/user_community_stats), 서비스 목록 12→20개 이상으로 확장(turn_executor/judge/finalizer/debate_formats/auto_matcher/evidence_search/forfeit/template_service/control_plane/helpers/exceptions), 마이그레이션 체인 최신화
- `docs/dev-guide/frontend.md` — 스토어 목록에 themeStore/followStore/notificationStore 추가, 주요 스토어 요약 표 갱신, SSE 이벤트 표에 judge_intro/turn_tool_call/forfeit/credit_insufficient/match_void/series_update 추가

---

## [2026-03-24] 문서 전면 정비 — API / 모델 / 프론트엔드 / 서비스 전체

### Added

**신규 문서 영역 3개:**
- `docs/api/` — API 라우터 문서 19개 신규 작성 (사용자 13개 + Admin 10개)
  - 사용자: auth, debate_agents, debate_matches, debate_topics, debate_tournaments, debate_ws, community, follows, models, notifications, usage, health, uploads
  - Admin: users, llm_models, usage, monitoring, debate_agents, debate_matches, debate_seasons, debate_templates, debate_topics, debate_tournaments
- `docs/models/` — SQLAlchemy ORM 모델 문서 16개 신규 작성 (22개 테이블 커버)
  - user, debate_agent(+version+season_stats), debate_match(+participant+prediction+queue), debate_turn_log, debate_season, debate_promotion_series, debate_tournament, debate_agent_template, debate_topic, llm_model, token_usage_log, community_post, user_community_stats, user_follow, user_notification + README(전체 관계도)
- `docs/frontend/` — 프론트엔드 Zustand 스토어 11개 + 주요 컴포넌트 7개 신규 작성

**신규 서비스 모듈 문서 5개:**
- `docs/modules/debate/evidence_search.md` — EvidenceSearchService (Tool-Use 검색 + 출처 검증)
- `docs/modules/debate/forfeit.md` — ForfeitHandler (몰수패·강제종료 처리)
- `docs/modules/debate/exceptions.md` — MatchVoidError, ForfeitError 예외 정의
- `docs/modules/debate/template_service.md` — DebateTemplateService (에이전트 템플릿 CRUD + 커스터마이징 검증)
- `docs/modules/debate/control_plane.md` — OrchestrationControlPlane (정책·점진 롤아웃·SSE 트레이스)

### Changed (문서 최신화)

**서비스 모듈 문서 8개 갱신:**
- `auto_matcher.md` — `_on_debate_task_done`, `_do_auto_match` 9단계 흐름, Redis 락 계층 추가
- `broadcast.md` — `publish_queue_event` None 가드 + best-effort 처리 추가
- `match_service.md` — `summary_report` JSONB 최신 구조, `_build_rule_violations` 신규 함수
- `matching_service.md` — `DebateAutoMatcher` 분리 반영 (auto_matcher.md로 이동)
- `promotion_service.md` — `draw` 처리·`expired` 상태·강등전 max_losses 오류 수정
- `season_service.md` — `close_season` 5단계 구조 수정
- `agent_service.md` — `DebateTemplateService` 분리 반영 (template_service.py로 이동)
- `notification_service.md` — `notify_new_follower` link 경로 추가

**아키텍처 문서 4개 갱신:**
- `01-system-overview.md` — DB 테이블 수 22개, SSH 키 경로, Tool-Use 추가, API 라우트 표
- `03-sse-streaming.md` — `judge_intro`/`turn_tool_call`/`series_update` 이벤트 추가, 타임아웃 명시
- `04-auth-ranking.md` — community/follows/notifications 경로, `elo_suppressed` 분기, 승급전 경로
- `06-scoring-system.md` — 3단계 판정(`generate_intro` 추가), 위반 유형 9종, score overflow 방지

---

## [2026-03-24] auto-walkthrough 재워크스루 — 버그 수정 6건

### Fixed (Critical)

- **`finalizer.py`** — `finished` SSE + `series_update` SSE를 try/except로 보호 (CRITICAL): DB 커밋 후 SSE 발행 실패가 `run_debate()` 예외 핸들러까지 전파되어 이미 'completed'로 저장된 `match.status`가 'error'로 덮어씌워지는 치명적 버그 수정

### Fixed

- **`engine.py`** — `judge_intro` SSE 발행을 try/except로 보호: Redis 장애 시에도 매치 실행 계속
- **`turn_executor.py`** — `turn_tool_call` SSE 발행을 try/except로 보호: Redis 장애 시에도 턴 실행 계속
- **`orchestrator.py`** — `REVIEW_SYSTEM_PROMPT`에 XML 구분자 안내 추가 + `review_turn` user_content에 `<발언 시작>…<발언 끝>` 등 XML 태그로 에이전트 발언 격리 (prompt injection 방어)
- **`judge.py`** — score 합산 방식 `sum(values())` → `sum(get(k, 0) for k in SCORING_CRITERIA)` 변경: LLM이 extra key 추가 시 score가 100점을 초과하던 버그 수정
- **`debate_formats.py`** — `_run_parallel_turns` end-of-loop에서 `prev_b_review_task` await를 `prev_b_evidence_task.done()` 체크 앞으로 이동: LLM 리뷰(수백 ms)가 완료되기 전에 evidence_task가 done() 아님을 이유로 불필요하게 취소되던 버그 수정

### Docs

- `docs/modules/debate/turn_executor.md` 신규 작성 (TurnExecutor 클래스 — 이전 문서 없음)
- `docs/modules/debate/debate_formats.md` 신규 작성 (포맷별 턴 루프 — 이전 문서 없음)
- `docs/modules/debate/engine.md`, `finalizer.md`, `orchestrator.md`, `judge.md` 최신화

---

## [2026-03-23] DuckDuckGo Tool-Use 웹 근거 인용 통합

### Added
- **`evidence_search.py`** — `EvidenceSearchService.search_by_query()` 추가: 이미 추출된 쿼리로 LLM 키워드 추출 없이 직접 DDG 검색 (Tool-Use 경로 전용)
- **`turn_executor.py`** — API 에이전트(OpenAI/Anthropic/Google) Tool-Use 2단계 파이프라인:
  - 1단계: 비스트리밍 호출로 `web_search` function call 감지
  - `turn_tool_call` SSE 이벤트 발행 ("근거 검색 중..." 스피너)
  - 검색 결과를 messages에 네이티브 형식으로 주입
  - 2단계: 스트리밍 발언 생성 (검색 결과 인용 포함)
- **`orchestrator.py`** — `LLM_VIOLATION_PENALTIES`에 `no_web_evidence`(3점), `false_citation`(8점) 추가; `REVIEW_SYSTEM_PROMPT`에 `tools_available` 조건부 위반 규칙 주입
- **`judge.py`** — `PENALTY_KO_LABELS`에 `no_web_evidence`, `false_citation`, `llm_no_web_evidence`, `llm_false_citation` 등록
- **`frontend/src/hooks/useDebateStream.ts`** — `turn_tool_call` SSE 이벤트 핸들러
- **`frontend/src/stores/debateStore.ts`** — `setTurnSearching()` 액션, `searchingTurns` 상태
- **`frontend/src/components/debate/TurnBubble.tsx`** — 검색 중 스피너 + "근거 검색 중..." UI, 출처 링크 표시

### Fixed
- **`debate_formats.py`** — 사후(post-hoc) evidence 수집 시 Tool-Use로 이미 근거가 설정된 턴 덮어쓰기 방지: `raw.get("tool_used") != "web_search"` 가드를 3곳(롤링 B 수집, A 수집, 루프 종료 후 마지막 B)에 적용
- **`turn_executor.py`** — Google provider `_to_gemini_format()`이 `functionResponse.name`을 읽을 수 있도록 tool 메시지에 `name` 필드 포함
- **`judge.py`** — `llm_` 접두사 레이블 누락으로 TurnBubble에서 위반 유형 미표시 버그 수정

### Notes
- RunPod(SGLang)은 function calling 미지원으로 Tool-Use 제외, 기존 사후 evidence 경로 유지
- Tool-Use 비활성: `DEBATE_TOOL_USE_ENABLED=false` 환경 변수로 즉시 비활성화 (기존 스트리밍 경로로 폴백)
- 기존 `turn_evidence_patch` SSE + TurnBubble 근거 박스는 Tool-Use 사용 턴을 제외하고 유지

---

## [2026-03-17] 문서 전면 최신화 (코드베이스 기준: 3a715c2)

### Changed
- `docs/architecture/02-debate-engine.md` — engine.py 클래스 기반 재설계 반영, 채점 체계 argumentation/rebuttal/strategy로 교체, SSE 이벤트 목록 신규 이벤트 추가
- `docs/modules/debate/engine.md` — DebateEngine 클래스 구조 문서화, 하위 호환 래퍼 명시
- `docs/modules/debate/orchestrator.md` — judge/ELO 역할 분리 명시, 위반 유형 현행 5종으로 정정

### Added
- `docs/architecture/06-scoring-system.md` — 채점 시스템 상세 (argumentation/rebuttal/strategy, 2-stage judge, 벌점 시스템, 클램핑, ELO)
- `docs/modules/debate/judge.md` — DebateJudge 클래스 (2-stage LLM 판정, SCORING_CRITERIA, 파싱 폴백)
- `docs/modules/debate/auto_matcher.md` — DebateAutoMatcher 클래스 (백그라운드 큐 폴링, 플랫폼 에이전트 자동 매칭)
- `docs/modules/debate/finalizer.md` — MatchFinalizer 클래스 (ELO·시즌·승급전·SSE·예측투표·토너먼트·요약 후처리 순서)

---

## [2026-03-17] 토론 점수 산정 시스템 개선 — 채점 체계 변경

### Changed
- `backend/app/services/debate/judge.py`
  - `SCORING_CRITERIA`: 구버전(`logic` 30 / `evidence` 25 / `rebuttal` 25 / `relevance` 20) → 현행(`argumentation` 40 / `rebuttal` 35 / `strategy` 25)
  - 판정 방식: 단일 LLM 호출 → 2-stage (Stage 1 서술형 분석 + Stage 2 채점) — 앵커링 편향 차단
  - 점수 클램핑 추가: `max(0, min(score, max_val))`로 LLM 오버슈팅 방어
- `backend/app/services/debate/orchestrator.py`
  - `LLM_VIOLATION_PENALTIES` 5종으로 축소: `false_claim`, `hasty_generalization`, `genetic_fallacy`, `appeal`, `slippery_slope`, `circular_reasoning`, `accent`, `division`, `composition` 제거
  - `PENALTY_KO_LABELS` 동기화

### Notes
- 기존 scorecard JSONB에 `logic`/`evidence`/`relevance` 키가 있는 레코드와 새 `argumentation`/`strategy` 키 레코드가 혼재할 수 있음. 프론트엔드에서 두 형식 모두 처리 필요.

---

## [2026-03-17] 토론 엔진 클래스/인터페이스 기반 재설계

### Changed
- `backend/app/services/debate/engine.py`
  - 1716줄 단일 파일 → 342줄 오케스트레이터로 축소
  - `DebateEngine` 클래스 도입: `run()`, `_load_entities()`, `_deduct_credits()`, `_wait_for_local_agents()`, `_void_match()`, `_refund_credits()`, `_run_with_client()`
  - 하위 호환 래퍼 함수 보존 (`_execute_turn_with_retry`, `_run_turn_loop`)

### Added
- `backend/app/services/debate/judge.py` — `DebateJudge` 클래스 분리 (orchestrator.py에서 분리)
- `backend/app/services/debate/finalizer.py` — `MatchFinalizer` 클래스 분리 (engine.py `_finalize_match`에서 분리)
- `backend/app/services/debate/auto_matcher.py` — `DebateAutoMatcher` 클래스 분리 (matching_service.py에서 분리)
- `backend/app/services/debate/debate_formats.py` — 포맷별 턴 루프 함수 분리 (`run_turns_1v1`, `run_turns_multi`, `get_format_runner`, `TurnLoopResult`)
- `backend/app/services/debate/exceptions.py` — `MatchVoidError` 전용 예외

### Removed
- `backend/app/services/debate/formats.py` — `debate_formats.py`로 이름 변경

### Notes
- `engine.py`에서 직접 import하던 테스트는 하위 호환 래퍼로 계속 동작
- 단위 테스트 252개 전부 통과

---

## [2026-03-17] SummaryReport 프론트엔드 필드명 수정

### Changed
- `frontend/src/components/debate/SummaryReport.tsx`
  - 백엔드 응답 필드명 수정: `key_arguments` → `agent_a_arguments` / `agent_b_arguments`
  - `turning_points`, `rule_violations` 필드 타입 정의 추가

---

## [2026-03-12] Debate LLM 위반 유형 확장

### Changed
- `backend/app/services/debate/orchestrator.py`
  - `LLM_VIOLATION_PENALTIES`에 신규 위반 7종 추가:
    - `hasty_generalization`, `accent`, `genetic_fallacy`, `appeal`, `slippery_slope`, `division`, `composition`
  - `PENALTY_KO_LABELS`에 대응 `llm_*` 레이블 추가
  - `REVIEW_SYSTEM_PROMPT`의 허용 위반 유형 목록에 신규 7종 정의 추가
- `frontend/src/components/debate/TurnBubble.tsx`
  - 신규 `llm_*` 위반 레이블/설명 추가
- `frontend/src/components/debate/DebateDebugModal.tsx`
  - `review_result.violations`와 `turn.penalties` 표시를 위한 기본/`llm_*` 레이블 확장
- 문서 동기화:
  - `docs/debate-code-review.md`
  - `docs/modules/debate/orchestrator.md`
  - `docs/architecture/02-debate-engine.md`
  - `docs/architecture/05-module-flow.md`
  - `scripts/make_docx.py` (문서 생성 문자열)

### Added
- `backend/tests/unit/services/test_debate_orchestrator.py`
  - 신규 논리 오류 7종의 벌점 매핑 검증 테스트 추가

---

## [2026-03-12] 팔로우 & 인페이지 알림 시스템

### Added
- **팔로우 시스템** — `user_follows` 테이블, `FollowService` (`follow`, `unfollow`, `get_following`, `get_follower_count`, `is_following`, `get_follower_user_ids`), `GET/POST/DELETE /api/follows/*`, `GET /api/follows/status` 엔드포인트
- **인페이지 알림 시스템** — `user_notifications` 테이블, `NotificationService` (`create`, `create_bulk`, `get_list`, `get_unread_count`, `mark_read`, `mark_all_read`, `notify_match_event`, `notify_prediction_result`, `notify_new_follower`), `GET/PUT /api/notifications/*` 엔드포인트
- **매치 알림 훅** — `engine.py`: 매치 시작·종료 시 `notify_match_event` 호출 (별도 세션), `match_service.py`: 예측투표 정산 후 `notify_prediction_result` 호출 (별도 세션)
- **NotificationBell 컴포넌트** — TopHeader에 미읽기 카운트 배지, 드롭다운 알림 목록, 낙관적 업데이트
- **FollowButton 컴포넌트** — 에이전트 카드에 팔로우/언팔로우 토글, 팔로워 수 표시
- **팔로잉 페이지** — `/profile/following` — 내가 팔로우한 에이전트/사용자 목록
- **Zustand 스토어** — `followStore`, `notificationStore` (낙관적 업데이트 + 실패 시 스냅샷 롤백)
- **단위 테스트 35개** — `test_follow_service.py` (17개), `test_notification_service.py` (18개)

---

## [2026-03-12] 토론 관전·랭킹 화면 정보 계층화 UI 개선

### Changed
- **TurnBubble** — 검토 결과 패널 기본 접힘 상태, 클릭으로 펼치는 토글 추가
- **MatchActionBar** — 신규 컴포넌트, 예측투표·공유·팔로우 액션을 관전 화면 하단에 고정 배치
- **DebateViewer** — MatchActionBar를 뷰어 내부로 이동, 화면 레이아웃 계층화
- **FightingHPBar** — 진행률 색상 강화, 라운드별 델타 표시 추가
- **RankingTable** — 현재 사용자 소유 에이전트 행 하이라이트(배경색 구분)

---

## [2026-03-12] 메인화면 리뉴얼 및 테마 시스템 구축

### Added
- **라이트/다크 테마 토글** — TopHeader에 ☀️/🌙 버튼 추가, `uiStore`에 `theme` 상태 관리
- **라이트 모드 디자인** — teal(#0d9488) primary, 민트 화이트 배경 계열
- **다크 모드 디자인** — 오렌지(#f97316) primary, 기존 어두운 배경 유지
- **2컬럼 레이아웃** — xl(1280px) 이상에서 좌측 토픽 목록 + 우측 통계/랭킹 사이드바 (max-w-[1400px])
- **히어로 배너** — 테마에 따라 teal/오렌지 그라디언트 자동 전환
- **TopHeader** — 검색바 + 테마 토글 + 알림 + 유저 아바타 상시 표시
- **UserSidebar 섹션 구분** — "플랫폼"(Home/Ranking/Agents/Gallery) / "내 계정"(마이페이지) 분리
- **TopicCard 개선** — LIVE 배지(빨간 펄스), 2열 그리드, 큰 제목, 방장 표시, 상태별 모드 태그
- **하단 네비 카드** — 주제 탭 하단 Agents + Ranking 카드 2열 추가
- **통계 카드 수정** — "진행 예정" API `/topics?status=scheduled`로 수정, "오늘의 참여자" live×2 추산
- **"토론 참여하기" 버튼** — 에이전트 있으면 랜덤 매칭 모달, 없으면 에이전트 생성 페이지 이동

### Fixed
- **tailwind.config.ts CSS 변수 연동** — 색상값 하드코딩 → `var(--color-*)` 참조로 변경, 테마 전환 정상화
- **전체 하드코딩 어두운 색상 교체** — `bg-gray-*`, `text-gray-*`, `border-gray-*` → CSS 변수 기반 클래스로 전환 (7개 파일)
- **deploy.sh orphan 컨테이너 충돌 방지** — `cleanup_containers`에 `status=created` 필터 추가, 빌드 후 `up` 직전 cleanup 추가
- **watchdog 주기 단축** — 2분 → 30초 (crontab 2줄로 30초 간격 구현)

---

## [2026-03-11] services/ 도메인별 서브패키지 재편

### Changed
- `services/` 하위 파일을 도메인별 서브패키지로 분리
  - `services/debate/` (신규): `debate_*` 서비스 12개 이동 + `debate_` 접두사 제거
    - `agent_service.py`, `broadcast.py`, `engine.py`, `match_service.py`, `matching_service.py`, `orchestrator.py`, `promotion_service.py`, `season_service.py`, `tool_executor.py`, `topic_service.py`, `tournament_service.py`, `ws_manager.py`
  - `services/llm/` (신규): `inference_client.py` + `providers/` 폴더 이동
- 전체 `.py` 파일 38개 import 경로 일괄 교체 (`app.services.debate_X` → `app.services.debate.X`, `app.services.inference_client` → `app.services.llm.inference_client`, `app.services.providers.` → `app.services.llm.providers.`)

### Notes
- 기능 변경 없음 — 파일 이동 및 import 경로 변경만
- 단위 테스트 273개 전부 통과

---

## [2026-03-11] core/ 데드코드 제거 및 정리

### Removed
- `auth.py`: `blacklist_all_user_tokens()` 제거 — `user_token_revoked:` Redis 키를 읽는 코드가 전체 프로젝트에 없음 (세션 무효화는 `clear_user_session()`이 담당)
- `deps.py`: `require_adult_verified()` 제거 — 성인인증 기능 제거 후 어떤 라우터에도 Depends 사용처 없음
- `observability.py`: `record_pipeline_duration()` + `_pipeline_duration` Histogram 제거 — 구 챗봇 NLP 파이프라인(emotion/embedding/reranker) 잔재, 호출처 없음. `get_metrics()` 반환값도 2개로 정리

### Fixed
- `rate_limit.py`: SSE 스트림 블록에서 `reset_at - int(now)` 중복 계산 → `retry_after` 변수로 캐싱

### Notes
- 단위 테스트 273개 전부 통과

---

## [2026-03-10] 토큰 제한 초과 전용 감점 도입

### Added
- `providers/openai_provider.py`: SSE 스트림에서 `finish_reason` 캡처 → `usage_out["finish_reason"]`에 저장
- `providers/anthropic_provider.py`: `stop_reason="max_tokens"` → `finish_reason="length"` 정규화
- `providers/google_provider.py`: `finishReason="MAX_TOKENS"` → `finish_reason="length"` 정규화
- `debate_engine.py`: `PENALTY_TOKEN_LIMIT = 3` 상수 추가
- `debate_orchestrator.py`: `PENALTY_KO_LABELS`에 `"token_limit": "토큰 제한 초과"` 추가

### Changed
- `debate_engine.py`: 발언 파싱 실패 시 원인 구분 — `finish_reason == "length"`이면 `token_limit` 감점(-3), 실제 JSON 오류면 `schema_violation` 감점(-5) 부여. `token_limit`은 파싱 성공 여부와 무관하게 응답 절삭 자체에 부여.

### Notes
- 감점을 낮게(-3) 설정한 이유: 토픽에서 직접 설정한 제한(`turn_token_limit`)이므로 에이전트 의도적 위반보다 경미하게 처리
- 단위 테스트 273개 전부 통과

---

## [2026-03-10] 코드 리뷰 기반 수정 — Critical 2개 · Major 3개 · Minor 2개

### Fixed (Critical)
- `debate_orchestrator.py`: `_call_review_llm`, `_judge_with_model`이 `_call_openai_byok` 하드코딩 → `generate_byok(provider, ...)` 교체. `_infer_provider(model_id)` + `_platform_api_key(provider)` 추가로 Anthropic/Google 모델도 review·judge에 사용 가능
- `debate_orchestrator.py` + `debate_engine.py`: `DebateOrchestrator.__init__`에서 `InferenceClient()` 독립 생성으로 httpx 커넥션 누수 → `client` 파라미터 주입 방식으로 변경, `debate_engine.py`에서 엔진 공유 클라이언트 재사용

### Fixed (Major)
- `debate_topics.py`: `_auto_match_safe` 카운트다운 매칭 경로에서 `season_id`, `match_type`, `series_id` 태깅 누락 → `ready_up()`과 동일한 시즌·시리즈 태깅 로직 추가. `select(DebateAgentVersion)` 중복 쿼리 → `get_latest_version()` 재사용
- `debate_match_service.py`, `debate_agent_service.py`: 검색 쿼리 `f"%{search}%"` → LIKE 특수문자(`%`, `_`, `\`) 이스케이프 처리 (3곳)
- `debate_ws_manager.py`: `asyncio.get_event_loop().time()` → `asyncio.get_running_loop().time()` (Python 3.12 deprecated)

### Fixed (Minor)
- `debateStore.ts`: `fetchRanking` 응답 타입 `{ items, total } | RankingEntry[]` 유니온 → `{ items, total }` 단일 타입

### Notes
- 단위 테스트 273개 전부 통과

---

## [2026-03-10] debate_agent_service.py dead code 제거 + 주석 보강

### Fixed (dead code)
- `update_agent()` — `elif data.name is not None: agent.name = data.name` 제거 (동일값 재할당 no-op)
- `update_elo()` — `if new_idx > old_idx:` 블록(즉시 승급) 제거: `check_and_trigger()`가 이미 승급전 시리즈를 생성하므로 도달 불가
- `update_elo()` — 로컬 `tier_order` 하드코딩 → `debate_promotion_service.TIER_ORDER` import로 교체 (중복 제거)
- `get_gallery()` — `get_tier_from_elo(agent.elo_rating)` 재계산 → `agent.tier` (DB authoritative 값) 사용으로 교체

### Tests
- `test_debate_agent_service.py` — `TestUpdateAgentDeadCode`, `TestUpdateEloDeadCode` 클래스 추가 (4개 신규 테스트)
- 단위 테스트 273개 전부 통과

### Notes
- 서비스 외부 API 변경 없음 — 모두 내부 구현 수정
- `TIER_ORDER` 단일 출처: `debate_promotion_service.py`

---

## [2026-03-09] 전체 코드 리뷰 기반 성능·재사용성·매직상수 개선

### Fixed (성능)
- `debate_match_service.py:get_match()` — 에이전트 개별 조회 2회(N+1) → `id.in_()` 단일 배치 쿼리로 교체
- `debate_season_service.py:close_season()` — 루프 내 User 개별 조회 → 배치 쿼리 후 맵 참조로 O(N) → O(1)
- `debate_match_service.py:generate_summary_task()` — 매 호출마다 새 SQLAlchemy 엔진 생성 → 앱 수준 공유 `async_session` 재사용
- `debate_match_service.py:DebateSummaryService` — `InferenceClient()` 직접 생성 → `async with InferenceClient() as client:` 패턴으로 연결 풀 정리 보장

### Fixed (재사용성)
- `debate_topics.py` — 에이전트 소유권 검증 쿼리 4중 복붙 → `_require_agent_ownership()` 헬퍼로 추출
- `debate_agents.py` — 에이전트 존재+권한 검증 블록 3중 복붙 → `_require_agent_access()` 헬퍼로 추출, `_ADMIN_ROLES` 상수 선언
- `debate_matches.py:get_match_summary` — 라우터 직접 DB 쿼리 → `DebateMatchService.get_summary_status()` 메서드로 이동
- `debate_promotion_service.py` — `create_promotion_series` / `create_demotion_series` 중복 → `_create_series()` private 메서드 추출
- `debate_match_service.py` — Decimal 토큰 비용 계산식 중복 → `calculate_token_cost()` 헬퍼 추출 (debate_engine.py에서도 재사용)
- `debate_agent_service.py` — ELO 티어 경계값 하드코딩 if/elif 체인 → `_TIER_THRESHOLDS` 모듈 상수로 선언 + 루프 기반 계산

### Fixed (매직 상수)
- `config.py` — 8개 설정 추가: `debate_draw_threshold`, `debate_review_max_tokens`, `debate_judge_max_tokens`, `debate_prediction_cutoff_turns`, `debate_ready_countdown_seconds`, `debate_season_reward_top3`, `debate_season_reward_rank4_10`, `agent_name_change_cooldown_days`
- `debate_orchestrator.py` — `max_tokens=2000/1024`, `diff >= 5` 리터럴 → settings 참조
- `debate_orchestrator.py` — 파싱 실패 폴백 스코어카드 고정값 → `{k: v // 2 for k, v in SCORING_CRITERIA.items()}` 동적 계산
- `debate_season_service.py` — `SEASON_REWARDS / RANK_4_10_REWARD` 모듈 상수 → settings 참조로 교체
- `debate_matching_service.py` + `debate_topics.py` — 카운트다운 `10` 리터럴 두 곳 → `settings.debate_ready_countdown_seconds` 동기화
- `debate_match_service.py` — `turn_count > 2` 하드코딩 → `settings.debate_prediction_cutoff_turns` 참조
- `debate_agent_service.py` — 이름 변경 쿨다운 `7` 하드코딩 → `settings.agent_name_change_cooldown_days` 참조

### Notes
- 단위 테스트 222개 전부 통과
- 서비스 API 변경 없음 — 모두 내부 구현 변경

---

## [2026-03-09] AI 토론 스트리밍 및 성능 전면 최적화

### Changed
- `frontend/src/components/debate/DebateViewer.tsx`: React 18 Automatic Batching으로 인한 "한번에 출력" 문제 수정 — setTimeout 20ms 큐(`enqueueChunk`)로 각 청크를 별도 macrotask에서 렌더링해 실시간 타자기 효과 구현
- `frontend/src/app/api/[...path]/route.ts`: `cache: 'no-store'` 추가 — Next.js 확장 fetch의 SSE body 버퍼링 방지
- `backend/app/services/debate_broadcast.py`: `get_message(timeout=0.05)` (1.0→0.05) + 하트비트 sleep 2초 — Redis Pub/Sub 청크 전달 지연 95% 감소
- `backend/app/services/inference_client.py`: `InferenceClient`에 인스턴스 수준 공유 `httpx.AsyncClient` 도입 (`__init__`에서 생성, `aclose()`/`__aenter__`/`__aexit__` 추가) — 매 LLM 호출마다 TCP/TLS 핸드셰이크를 생략해 첫 토큰 도달 시간(TTFT) 단축
- `backend/app/services/debate_engine.py`: 롤링 병렬 B 리뷰 패턴 구현 — B 실행 직후 `asyncio.create_task`로 B 리뷰를 시작하고 다음 턴 A 실행 동안 숨겨 턴 간 순수 대기 시간 제거 (턴당 ~15→5초). `_run_match_with_client` 추출로 `async with InferenceClient()` 블록에서 예외·조기 반환 시에도 HTTP 연결 풀 정리 보장

### Notes
- 단위 테스트 222개 통과
- 스트리밍 체감 성능: 청크가 즉시 한 글자씩 출력 (이전: LLM 완료 후 한번에 출력)
- 턴 간 지연: ~30초 → ~5초 (B 리뷰가 다음 턴 A 실행과 병렬화됨)

---

## [2026-03-09] 시스템 아키텍처 문서 작성

### Added
- `docs/modules/system-architecture.md`: 전체 시스템 아키텍처 문서 최초 작성 (인프라 구성, API 엔드포인트, 토론 엔진 흐름, DB 구조, 배포 구성, 성능 목표 포함)
- `docs/modules/model-architecture.md`: LLM 모델 아키텍처 문서 최초 작성 (모델 역할 분리, 라우팅 구조, 지원 모델 목록, OptimizedOrchestrator 병렬 처리, 벤치마크 결과 포함)

---

## [2026-03-06] debate agents 버그 수정 및 코드 품질 개선

### Fixed
- `debate_agents.py` + `debate_agent_service.py`: `update_agent` — 소유권 불일치 시 404 대신 403 반환하도록 `PermissionError` 분리
- `debate_agent_service.py`: `clone_agent` — BYOK(non-local, use_platform_credits=False) 에이전트 복제 시 항상 실패하던 버그 수정. api_key 없이 직접 DB 삽입으로 복제, 복제본은 비공개로 시작
- `debate_agent_service.py`: `get_gallery` 응답에 `is_system_prompt_public` 필드 추가 (복제 가능 여부 프론트 판단용)
- `debate_agents.py`: `get_head_to_head` — 잘못된 UUID 입력 시 500 대신 422 반환

### Changed
- `debate_agent.py`: `DebateAgent.updated_at` 컬럼에 `onupdate=lambda: datetime.now(UTC)` 추가 (수정 시 자동 갱신)
- `debate_agent_schema.py`: `AgentUpdate.system_prompt` — `min_length=1` 검증 추가 (빈 문자열 업데이트 차단)
- `debate_agent_schema.py`: `GalleryEntry`에 `is_system_prompt_public` 필드 추가; `AgentRankingListResponse`, `GalleryListResponse`, `HeadToHeadListResponse` 래퍼 스키마 추가
- `debate_agents.py`: `/ranking`, `/gallery`, `/{id}/head-to-head` 엔드포인트에 `response_model` 연결

### Notes
- 단위 테스트 224개 통과

---

## [2026-03-06] 서비스 실용성 없는 로직 9개 수정

### Changed
- `debate_engine.py`: `human_suspicion_score` 데드코드 전면 제거 (PENALTY_HUMAN_SUSPICION, elapsed/length_history 수집, SSE 이벤트 포함)
- `debate_engine.py`: 멀티에이전트 루프에서 루프 전 에이전트·버전 일괄 로드 → dict 캐시 조회 (매 턴 N번 DB 쿼리 → 1번으로 감소)
- `debate_match_service.py`: `generate_summary()` — `httpx.AsyncClient` 직접 OpenAI 호출 → `InferenceClient.generate()` 교체 + `TokenUsageLog` INSERT 추가
- `debate_match_service.py`: `list_featured()` — `return items, len(items)` → 별도 COUNT 쿼리로 실제 전체 건수 반환
- `debate_agent_service.py`: `get_latest_version` 4곳 중복 구현 → 단독 함수로 통합 (debate_matching_service가 import하여 재사용)
- `debate_agent_service.py`: `get_my_ranking()` — 에이전트 수만큼 COUNT 반복 (N+1) → 전체 리스트 1회 조회 + rank_map dict 계산
- `debate_orchestrator.py`: `_build_review_result(skipped: bool = False)` → `skipped: bool | None = None` (기존 default False는 `is not None` 체크를 항상 True로 만들던 버그)
- `debate_topic_service.py`: `_last_sync_at` 클래스 변수 기반 스로틀링 → Redis `SET NX EX 60` 분산 락으로 교체 (멀티 워커 환경에서 안전)
- `debate_season_service.py`: `close_season()` — 시즌 보상(`reward > 0`) 계산 후 `User.credit_balance` 실제 차감 (기존: DB에만 기록, 잔액 미반영)

### Notes
- DB 컬럼 `human_suspicion_score` 는 API 호환성을 위해 스키마/마이그레이션 유지, 서비스 레이어에서만 미사용
- 단위 테스트 252개 통과 (통합 테스트 연결 오류는 로컬 DB/Redis 미실행 탓 — 코드 이슈 없음)

---

## [2026-03-06] 정규식 탐지 제거 → LLM 검토 항상 실행

### Changed
- `debate_engine.py`: `_INJECTION_PATTERNS`, `_AD_HOMINEM_PATTERNS`, `detect_prompt_injection()`, `detect_ad_hominem()`, `PENALTY_PROMPT_INJECTION`, `PENALTY_AD_HOMINEM` 전체 제거
- `debate_orchestrator.py`: `_should_skip_review()` 제거, `review_turn_fast()` 패스트패스 분기 제거 → 모든 발언에 LLM 검토 항상 실행, `PENALTY_KO_LABELS`에서 정규식 벌점 키 제거
- `config.py`: `debate_review_fast_path` 설정값 제거
- 벤치마크/단위 테스트에서 관련 테스트 정리

### Notes
- 기존 정규식은 영어 중심 + 한국어 3단어(바보/멍청/병신)에 불과해 우회 가능성 높음
- 패스트패스가 LLM 검토 여부를 결정하는 게이트였으나, 게이트 제거 후 gpt-5-nano가 모든 발언 검토
- 단위 테스트 252개 통과

---

## [2026-03-06] 프론트엔드 비토론 코드 전면 삭제

### Removed
- **사용자 페이지** (`src/app/(user)/`): `character/`, `character-chats/`, `chat/`, `community/`, `favorites/`, `notifications/`, `pending-posts/`, `personas/`, `relationships/`, `sessions/`
- **관리자 페이지** (`src/app/admin/`): `content/`, `features/`, `personas/`, `policy/`, `reports/`, `video-gen/`, `world-events/`
- **컴포넌트 디렉토리**: `src/components/character/`, `src/components/pending/`, `src/components/persona/`, `src/components/credits/`, `src/components/subscription/`, `src/components/chat/`, `src/components/community/`, `src/components/live2d/`
- **인증 모달**: `src/components/auth/AdultVerifyModal.tsx`, `AdultVerifyModal.test.tsx`, `AgeGateModal.tsx`, `AgeGateModal.test.tsx`
- **레이아웃**: `src/components/layout/NotificationBell.tsx`
- **마이페이지 탭**: `src/components/mypage/SubscriptionTab.tsx`, `UserPersonaTab.tsx`, `MemoriesTab.tsx`, `CreatorTab.tsx`
- **스토어**: `characterChatStore.ts`, `characterPageStore.ts`, `chatStore.ts`, `communityStore.ts`, `creditStore.ts`, `featureFlagStore.ts`, `live2dStore.ts`, `notificationStore.ts`, `pendingPostStore.ts`, `personaStore.ts`, `worldEventStore.ts`
- **상수**: `src/constants/categories.ts`

### Changed
- `src/app/(user)/layout.tsx`: `featureFlagStore` import 제거, feature flag 게이팅 로직 제거, chat 전용 분기 제거
- `src/app/(user)/mypage/page.tsx`: 비토론 탭(subscription, user-persona, memories, creator) 제거 → profile/settings/usage/agents 4개 탭만 유지
- `src/app/page.tsx`: 테마 선택 단계 제거, 회원가입 후 `/debate`로 바로 리다이렉트, 아이콘 Swords로 변경
- `src/components/layout/UserSidebar.tsx`: 비토론 메뉴 항목 제거, `featureFlagStore`/`notificationStore`/`CreditBadge` 제거, 홈 링크 `/debate`로 변경
- `src/components/admin/Sidebar.tsx`: 비토론 메뉴 항목 제거, `pendingReports` 로직 제거, 미사용 import 정리
- `src/components/mypage/ProfileTab.tsx`: `creditStore` 의존성 제거, 대화석 표시 항목 제거
- `src/components/mypage/SettingsTab.tsx`: `AdultVerifyModal`, 성인인증 섹션 제거 → LLM 모델 목록만 표시

### Notes
- TypeScript 타입 오류 없음 (`npx tsc --noEmit` 통과)
- 프론트엔드 테스트 36개 모두 통과

## [2026-03-06] 테스트 파일 정리 (23개 삭제)

### Removed
- `integration/api/` 비토론 테스트 14개: board, character_chats/pages, chat, credits, lorebook, lounge, pending_posts, personas, policy, subscriptions, video_gen, webtoons, world_events
- `unit/pipeline/` 삭제된 서비스 테스트 5개: embedding, emotion, korean_nlp, pii, reranker
- `unit/prompt/test_compiler.py`: 삭제된 persona 프롬프트 컴파일러 테스트
- `unit/services/test_debate_engine_rewrite.py`: 완료된 리라이트 계획 잔재
- `unit/services/test_debate_orchestrator_rewrite.py`: 완료된 리라이트 계획 잔재
- `unit/services/test_debate_queue_broadcast.py`: debate_broadcast로 병합된 모듈 테스트

### Notes
- 단위 테스트 352개 → 232개 (비토론 및 중복 테스트 제거)

---

## [2026-03-06] debate 모듈 파일 병합 (Services 5개, Models 7개 제거)

### Changed
**Services (17개 → 12개):**
- `debate_broadcast.py` ← `debate_queue_broadcast.py` 흡수 (publish_queue_event, subscribe_queue)
- `debate_matching_service.py` ← `debate_auto_match.py` 흡수 (DebateAutoMatcher 클래스)
- `debate_match_service.py` ← `debate_summary_service.py` 흡수 (generate_summary_task)
- `debate_agent_service.py` ← `debate_template_service.py` 흡수 (DebateTemplateService) + `debate_utils.get_latest_version` 이동
- `debate_orchestrator.py` ← `debate_utils` 의 detect_prompt_injection, detect_ad_hominem, format_debate_log 이동

**Models (15개 → 8개):**
- `debate_match.py` ← DebateMatchParticipant, DebateMatchPrediction, DebateMatchQueue 통합
- `debate_agent.py` ← DebateAgentVersion, DebateAgentSeasonStats 통합
- `debate_season.py` ← DebateSeasonResult 통합
- `debate_tournament.py` ← DebateTournamentEntry 통합
- `models/__init__.py`: 통합 파일에서 import하도록 정리

### Notes
- 전체 단위 테스트 352개 통과
- `main.py`의 `DebateAutoMatcher` import 경로 버그 동시 수정 (debate_auto_match → debate_matching_service)

---

## [2026-03-06] 비토론 모듈 파일 실제 삭제

### Removed
- `api/` 비토론 라우터 22개: board, character_cards/chats/pages, chat, credits, favorites, features, image_gen, lorebook, lounge, memories, notifications, pending_posts, personas, policy, relationships, subscriptions, tts, user_personas, webtoons, world_events
- `api/admin/` 레거시 플랫 파일 17개: agents, board, content, credits, debate(구 단일파일), features, llm_models, monitoring, personas, policy, reports, subscriptions, system(구 단일파일), usage, users, video_gen, world_events
- `services/` 비토론 서비스 30개: adult_verify, agent_activity, agent_scheduler, batch_scheduler, board, character_card/chat/page, chat, credit, favorite, feature_flag, human_detection, image_gen, lorebook, moderation, notification, pending_post, persona, policy, quota, rag, relationship, report, review, subscription, tts, user_persona, video_gen, world_event
- `models/` 비토론 모델 35개: agent_activity_log, board/board_comment/post/reaction, character_chat_message/session, chat_message/session, comment_stat, consent_log, credit_cost/ledger, episode/embedding/emotion, live2d_model, lorebook_entry, notification, pending_post, persona/favorite/lounge_config/relationship/report, review_cache, spoiler_setting, subscription_plan, usage_quota, user_memory/persona/subscription, video_generation, webtoon, world_event
- `schemas/` 비토론 스키마 20개: board, character_chat/page, chat, credit, favorite, image_gen, lorebook, lounge, notification, pending_post, persona, relationship, report, subscription, tts, user_persona, video_gen, webtoon, world_event
- `tests/unit/` 비토론 테스트 11개: agent_activity, batch_scheduler, board, chat, credit, human_detection, image_gen, quota, subscription, tts, video_gen

### Changed
- `models/__init__.py`: debate 전용 18개 모델만 import (User, LLMModel, TokenUsageLog + 15개 debate 모델)
- `services/debate_engine.py`: 삭제된 CreditLedger, HumanDetectionAnalyzer import 및 관련 로직 제거
- `services/debate_season_service.py`: 삭제된 CreditLedger import 및 시즌 크레딧 보상 로직 제거
- `api/auth.py`: 삭제된 성인인증 관련 어드민 엔드포인트 제거
- `api/usage.py`: 삭제된 quota 엔드포인트 제거

### Notes
- 전체 단위 테스트 352개 통과 (기존 471개 → 비토론 테스트 제거 후 352개)
- main.py에 미등록 상태로만 남아있던 파일들을 실제 삭제

---

## [2026-03-06] WebSocket 인증 방식 변경 (H-1)

### Changed
- backend/app/api/debate_ws.py: JWT를 URL 쿼리 파라미터(`?token=`)에서 first-message 방식(`{"type":"auth","token":"..."}`)으로 변경
  - 연결 즉시 accept → 10초 timeout으로 첫 메시지 대기 → 인증 실패 시 code=4001 close
  - 블랙리스트 + 세션 JTI 검증 추가 (`is_token_blacklisted`, `get_user_session_jti`)
  - Redis 장애 시 fail-open (WS 서비스 완전 차단 방지)
- frontend/src/lib/agentWebSocket.ts: WS URL에서 `?token=` 제거, `onopen` 시 `{"type":"auth","token":"..."}` 전송

### Notes
- nginx 로그·브라우저 히스토리·프록시 캐시에 JWT 노출 방지
- 재연결(지수 백오프) 시에도 onopen에서 자동으로 인증 메시지 재전송됨

---

## [2026-03-06] 프로덕션 기준 코드 리뷰 20개 항목 수정

### Fixed
**HIGH (보안/데이터 정합성)**
- H-2: debate_engine.py - use_platform_credits=False + 키 없음 시 ValueError 명시적 raise (플랫폼 키 fallback 제거)
- H-3: core/encryption.py + config.py - ENCRYPTION_KEY를 SECRET_KEY와 완전 분리 (암호화 키 교체 독립성)
- H-4: debate_topics.py - _auto_match_safe 이중 잠금 → 단일 `IN (...) FOR UPDATE` 쿼리 (TOCTOU 방지)
- H-5: debate_ws.py - 블랙리스트·세션 JTI 검증 추가 (H-1과 함께 처리)
- H-6: debate_broadcast.py - SSE 연결별 신규 Redis 연결 → 공유 ConnectionPool(max_connections=200) 전환

**MEDIUM (가용성/성능)**
- M-1: health.py - DB SELECT 1 + Redis ping 상태 포함, 실패 시 HTTP 503 반환
- M-2: rate_limit.py - `/stream` 경로 전용 제한(debate limit의 절반), UUID suffix로 타임스탬프 충돌 방지
- M-3: debate_engine.py - judge() 호출에 asyncio.wait_for(timeout=90.0) 추가
- M-4: debate_tournament_service.py - join_tournament에 SELECT ... FOR UPDATE 추가 (bracket_size 초과 방지)
- M-5: debate_topics.py - _run_debate_safe를 await→asyncio.create_task + _background_tasks set (GC 방지)
- M-6: debate_engine.py - 에러 턴 claim 내용 내부 예외 메시지 대신 고정 문구로 sanitize
- M-7: debate_ws_manager.py - _pubsub_loop_with_restart 지수 백오프 재시작 (최대 60초)
- M-8: debate_engine.py - resolve_predictions/advance_round를 try/except로 감싸 ELO 커밋 후 실패 격리

**LOW (코드 품질)**
- L-1: inference_client.py - Google API 키를 URL 파라미터→ x-goog-api-key 헤더로 변경
- L-2: rate_limit.py - zadd member에 UUID suffix 추가 (타임스탬프 충돌 방지)
- L-3: debate_agent_service.py + debate_agents.py - get_ranking 반환값에 total 포함, API 응답 `{items, total}`
- L-4: config.py - CHECK_INTERVAL 하드코딩 → debate_auto_match_check_interval 설정값으로 변경
- L-5: debate_topics.py - _count_queue/_count_matches를 public 메서드로 승격
- L-6: inference_client.py - _openai_max_tokens_key 적용 (max_completion_tokens 키 통일)

### Added
- alembic/versions/j0k1l2m3_add_prediction_unique_constraint.py: DebateMatchPrediction(match_id, user_id) UniqueConstraint 추가

### Notes
- 전체 단위 테스트 471개 모두 통과
- 프론트엔드 WS 인증 변경(H-1)은 별도 항목으로 기록

---

## [2026-03-06] admin/ 서브패키지 분리 + 모듈 병합

### Changed
- backend/app/api/admin/ 플랫 구조 → admin/debate/ + admin/system/ 서브패키지로 분리
  - admin/debate/: agents, matches, seasons, stats, templates, tournaments
  - admin/system/: llm_models, monitoring, usage, users
- services/ 21개 → 16개 파일 병합
  - debate_queue_broadcast.py → debate_broadcast.py 통합
  - debate_auto_match.py → debate_matching_service.py 통합
  - debate_summary_service.py → debate_match_service.py 통합
- models/ 19개 → 13개 파일 병합
  - debate_match_participant.py + debate_match_prediction.py + debate_match_queue.py → debate_match.py
  - debate_agent_version.py + debate_agent_season_stats.py → debate_agent.py
  - debate_season_result.py → debate_season.py
  - debate_tournament_entry.py → debate_tournament.py

### Notes
- 각 병합 파일 내 한국어 섹션 구분 주석 추가 (가독성)
- 전체 단위 테스트 315개 통과

---

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
