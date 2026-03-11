# Backend CLAUDE.md

백엔드 개발 시 참고하는 규칙과 명세. 루트 `CLAUDE.md`의 공통 원칙과 함께 적용.

## Python 코딩 컨벤션

- Python 3.12+, 비동기 우선 (`async/await`)
- 타입 힌트 필수, Pydantic v2로 입출력 검증
- 포매터: ruff (format + lint), 줄 길이 120자
- 네이밍: snake_case (변수/함수), PascalCase (클래스)
- import 순서: stdlib → third-party → local
- 문자열: 큰따옴표(`"`) 통일, f-string 우선, `.format()` 금지
- 예외: 맨손 `except:` 금지, 구체적 예외 타입 명시
- 환경 변수: `core/config.py`의 `BaseSettings`로만 관리, `os.getenv()` 직접 호출 금지
- DB/Redis/HTTP 호출은 반드시 `async`, sync 함수에서 `asyncio.run()` 금지

```toml
# pyproject.toml
[tool.ruff]
line-length = 120
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "ASYNC"]
```

## 주석 규칙

**"왜(Why)"만 쓴다. "무엇(What)"은 코드로.**

```python
# Good — 비직관적 동작의 이유
# asyncio.gather로 A 검토와 B 실행을 병렬화 — 턴 지연 37% 단축
review_a, result_b = await asyncio.gather(review(turn_a), execute(turn_b))

# Bad — 코드 반복
# 사용자 ID를 가져온다
user_id = request.user.id
```

- docstring: 공개 라우터/서비스 클래스에만 작성
- TODO: `# TODO(이름): 설명 — #이슈번호` 형식, 이슈 없는 TODO 금지
- 마이그레이션 파일: 변경 사유 주석 필수
- SQL 주석: 복잡 쿼리(JOIN 3개+, 서브쿼리)에 의도 기술

## RBAC & 접근 제어

- 관리자 API: `Depends(require_admin)` 또는 `Depends(require_superadmin)` 필수
- 파괴적 작업(삭제/역할변경): `require_superadmin` 필수
- 사용자는 자신의 리소스만 접근 가능 (소유권 체크 필수)
- 소유권 실패 → `PermissionError` (HTTP 403), 미존재 → `ValueError` (HTTP 404)

## 프로젝트 구조

```
app/
├── main.py                  # FastAPI 앱, 라우터 등록
├── api/                     # 라우터 레이어 (입력 검증 + HTTP 응답만)
│   ├── auth.py
│   ├── debate_agents.py
│   ├── debate_matches.py
│   ├── debate_topics.py
│   ├── debate_tournaments.py
│   ├── debate_ws.py         # WebSocket (로컬 에이전트 연결)
│   ├── models.py
│   ├── uploads.py
│   ├── usage.py
│   └── admin/
│       ├── debate/          # 토론 관리 (agents, matches, seasons, stats, templates, tournaments)
│       └── system/          # 시스템 관리 (llm_models, monitoring, usage, users)
├── core/                    # 인프라 설정
│   ├── config.py            # BaseSettings (환경 변수 전체 관리)
│   ├── database.py          # SQLAlchemy async 엔진 + 세션
│   ├── redis.py             # Redis 클라이언트
│   ├── auth.py              # JWT 발급/검증
│   ├── deps.py              # FastAPI Depends (get_db, get_current_user, require_admin 등)
│   ├── encryption.py        # API 키 암호화/복호화 (Fernet)
│   ├── observability.py     # Langfuse + Sentry 초기화
│   └── rate_limit.py        # SlowAPI 기반 Rate Limiting
├── models/                  # SQLAlchemy ORM 모델
├── schemas/                 # Pydantic 입출력 스키마
└── services/                # 비즈니스 로직 (라우터에서 직접 쿼리 금지)
    ├── debate/              # 토론 도메인 서비스 (engine, orchestrator, broadcast 등 12개)
    ├── llm/                 # LLM 추론 (inference_client.py + providers/)
    │   └── providers/       # provider별 HTTP 구현 (openai, anthropic, google, runpod)
    ├── usage_service.py
    └── user_service.py
```

## API 라우트 목록

| 경로 | 파일 | 설명 |
|---|---|---|
| `GET /health` | `health.py` | 서버 상태 확인 |
| `/api/auth/*` | `auth.py` | 회원가입, 로그인, 토큰 갱신 |
| `/api/models/*` | `models.py` | LLM 모델 목록 조회, 선호 모델 설정 |
| `/api/usage/*` | `usage.py` | 내 토큰 사용량 조회 |
| `/api/uploads/*` | `uploads.py` | 이미지 업로드 |
| `/api/agents/*` | `debate_agents.py` | 에이전트 CRUD, 랭킹, 갤러리, H2H |
| `/api/topics/*` | `debate_topics.py` | 토픽 등록/조회/매칭 큐 |
| `/api/matches/*` | `debate_matches.py` | 매치 조회, SSE 스트리밍, 예측투표, 요약 |
| `/api/tournaments/*` | `debate_tournaments.py` | 토너먼트 CRUD, 대진표 |
| `/api/ws/debate/*` | `debate_ws.py` | WebSocket (로컬 에이전트 전용) |
| `/api/admin/users/*` | `admin/system/users.py` | 사용자 조회/역할 변경 |
| `/api/admin/models/*` | `admin/system/llm_models.py` | LLM 모델 등록/수정/활성화 |
| `/api/admin/usage/*` | `admin/system/usage.py` | 전체 사용량 현황 |
| `/api/admin/monitoring/*` | `admin/system/monitoring.py` | 토큰/비용 모니터링 |
| `/api/admin/debate/*` | `admin/debate/` | 매치 강제실행, 시즌/토너먼트 관리 |

## Database

- **엔진:** PostgreSQL 16, EC2 내부 Docker (RDS 사용 안 함)
- **ORM:** SQLAlchemy 2.0 async, **마이그레이션:** Alembic

### SQL 컨벤션

- 테이블/컬럼: snake_case
- PK: `id` (UUID)
- FK: `{참조테이블_단수}_id`
- 인덱스: `idx_{테이블}_{컬럼}`
- TIMESTAMPTZ 사용 (TIME ZONE 포함)
- CHECK 제약조건으로 enum 대체

### 모델 목록 (18개)

| 모델 | 테이블 | 설명 |
|---|---|---|
| `User` | `users` | 사용자 계정, 역할(user/admin/superadmin), 크레딧 잔액 |
| `LLMModel` | `llm_models` | 등록된 LLM 모델 (provider, 비용, 활성화 여부) |
| `TokenUsageLog` | `token_usage_logs` | LLM 호출 토큰·비용 기록 |
| `DebateAgent` | `debate_agents` | 에이전트 (소유자, provider, ELO, 공개 여부, 승급전 상태) |
| `DebateAgentVersion` | `debate_agent_versions` | 에이전트 버전 이력 (system_prompt 스냅샷) |
| `DebateAgentSeasonStats` | `debate_agent_season_stats` | 시즌별 ELO·전적 분리 집계 |
| `DebateAgentTemplate` | `debate_agent_templates` | 관리자 제공 에이전트 템플릿 |
| `DebateTopic` | `debate_topics` | 토론 주제 (등록자, 승인 상태) |
| `DebateMatch` | `debate_matches` | 매치 (참가자, 형식, 상태, 결과, 시즌/시리즈 연결) |
| `DebateMatchParticipant` | `debate_match_participants` | 멀티에이전트 매치 참가자 목록 |
| `DebateMatchPrediction` | `debate_match_predictions` | 사용자 예측투표 |
| `DebateMatchQueue` | `debate_match_queues` | 매칭 대기 큐 |
| `DebateTurnLog` | `debate_turn_logs` | 턴별 발언·검토 결과·점수 기록 |
| `DebatePromotionSeries` | `debate_promotion_series` | 승급전/강등전 시리즈 상태 |
| `DebateSeason` | `debate_seasons` | 시즌 기간·상태 |
| `DebateSeasonResult` | `debate_season_results` | 시즌 종료 시 최종 순위 스냅샷 |
| `DebateTournament` | `debate_tournaments` | 토너먼트 대진표·상태 |
| `DebateTournamentEntry` | `debate_tournament_entries` | 토너먼트 참가 에이전트 목록 |

## 서비스 목록

**`services/debate/`**

| 파일 | 역할 |
|---|---|
| `agent_service.py` | 에이전트 CRUD, 랭킹, 갤러리, 클론, H2H, 버전 관리 |
| `match_service.py` | 매치 조회, 하이라이트, 요약 리포트 생성 |
| `matching_service.py` | 큐 등록/취소, 자동 매칭(`DebateAutoMatcher`), ready_up |
| `engine.py` | 토론 실행 루프 (턴 실행 → 검토 → 판정 → 결과 저장) |
| `orchestrator.py` | LLM 검토(`DebateOrchestrator`) + 최적화 병렬 실행(`OptimizedDebateOrchestrator`) |
| `broadcast.py` | SSE 이벤트 발행/구독, 관전자 수 관리 |
| `ws_manager.py` | WebSocket 연결 관리 (로컬 에이전트 인증·메시지 라우팅) |
| `topic_service.py` | 토픽 CRUD, Redis 캐싱·동기화 |
| `season_service.py` | 시즌 생성/종료, 시즌 ELO 집계, 보상 지급 |
| `promotion_service.py` | 승급전/강등전 시리즈 생성·진행·완료 처리 |
| `tournament_service.py` | 토너먼트 대진표 생성·진행 |
| `tool_executor.py` | 에이전트 Tool Call 실행 (함수 호출 결과 반환) |

**`services/llm/`**

| 파일 | 역할 |
|---|---|
| `inference_client.py` | LLM 호출 단일 진입점 (Langfuse 추적, 토큰 로깅, provider 분기) |
| `providers/base.py` | provider 공통 추상 인터페이스 |
| `providers/{openai,anthropic,google,runpod}_provider.py` | provider별 HTTP 구현 |

**`services/` 루트**

| 파일 | 역할 |
|---|---|
| `usage_service.py` | 토큰 사용량 집계 조회 |
| `user_service.py` | 사용자 조회, 역할 변경, 쿼터 관리 |

## LLM 호출 규칙

**모든 LLM 호출은 반드시 `InferenceClient`를 통한다.** 직접 `openai.AsyncOpenAI()` 호출 금지.

```
서비스 → inference_client.generate()
    → llm_models 테이블에서 provider/model_id 조회
    → provider별 분기 (openai / anthropic / google / runpod)
    → Langfuse 트레이스 기록
    → token_usage_logs INSERT
    → 응답 반환
```

**llm_models 주요 필드:** `provider`, `model_id`, `display_name`, `input_cost_per_1m`, `output_cost_per_1m`, `max_context_length`, `is_active`, `tier`

## 토론 엔진 흐름

```
큐 등록 → DebateAutoMatcher 감지 → ready_up() → DebateMatch 생성
    → debate_engine.run_match()
        ├─ 턴 루프 (N 라운드)
        │   ├─ 에이전트 발언 생성 (LLM 호출 or WebSocket)
        │   └─ OptimizedDebateOrchestrator.review_turn()  ← 항상 LLM 검토
        │       └─ asyncio.gather(A 검토, B 실행) 병렬 실행
        └─ judge() → 최종 판정 → ELO 갱신 → 승급전 체크
    → SSE 이벤트 발행 (debate_broadcast)
```

**오케스트레이터 설정 (`config.py`):**
- `debate_review_model = "gpt-5-nano"` — 턴 검토 (경량)
- `debate_judge_model = "gpt-4.1"` — 최종 판정 (고정밀)
- `debate_orchestrator_optimized = True` — 모델 분리 + 병렬 실행 활성화

## WebSocket 인증 방식

URL 파라미터 토큰 방식 미사용. 연결 후 첫 메시지로 인증:

```json
{"type": "auth", "token": "<JWT>"}
```

인증 실패 또는 5초 내 미전송 시 연결 즉시 종료.

## 테스트

**반드시 venv 활성화 후 실행** (`backend/.venv/Scripts/activate` on Windows)

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/unit/ -v          # 단위 테스트 (224개)
.venv/Scripts/python.exe -m pytest tests/benchmark/ -v     # 벤치마크 (28개)
.venv/Scripts/python.exe -m pytest tests/integration/ -v   # 통합 테스트 (DB/Redis 필요)
```

### 규칙

- 파일: `test_*.py`, 함수: `test_동작_조건_기대결과`
- 외부 LLM API만 mock, 내부 서비스는 실제 로직 테스트
- 비동기: `@pytest.mark.asyncio`, async fixture는 `@pytest_asyncio.fixture`
- DB 격리: 테스트마다 트랜잭션 롤백

### 필수 정책 검증 테스트

- 타인의 에이전트 수정 시도 → 403
- 관리자 API에 일반 사용자 접근 → 403
- 소유하지 않은 에이전트로 큐 등록 → 403
- 토큰 사용량 기록 누락 없음 확인
