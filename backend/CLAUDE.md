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

## RBAC & 접근 제어

- 관리자 API: `Depends(require_admin)` 또는 `Depends(require_superadmin)` 필수
- 파괴적 작업(삭제/역할변경/정책수정): `require_superadmin` 필수
- 18+ 콘텐츠 접근 API: `Depends(require_adult_verified)` 적용
- 회원가입/닉네임 변경 시 `'admin'` 포함 닉네임 차단 (400 반환)

## 주석 규칙

**"왜(Why)"만 쓴다. "무엇(What)"은 코드로.**

```python
# Good — 법적 근거
# 청소년유해매체물 제공 시 본인확인 의무 (청소년보호법 시행령)
if persona.age_rating == "18+" and not user.adult_verified_at:
    raise HTTPException(status_code=403)

# Good — 비직관적 최적화
# RadixAttention 캐시 히트를 위해 시스템 프롬프트를 대화 히스토리 앞에 고정
prompt = build_prefix(persona) + history + user_input

# Bad — 코드 반복
# 사용자 ID를 가져온다
user_id = request.user.id
```

- docstring: 공개 라우터/서비스 클래스에만 작성
- TODO: `# TODO(이름): 설명 — #이슈번호` 형식, 이슈 없는 TODO 금지
- 마이그레이션 파일: 변경 사유 주석 필수
- SQL 주석: 복잡 쿼리(JOIN 3개+, 서브쿼리)에 의도 기술

## Database

- **엔진:** PostgreSQL 16 + pgvector, EC2 내부 Docker (RDS 사용 안 함)
- **ORM:** SQLAlchemy 2.0 (async), **마이그레이션:** Alembic
- **벡터 인덱스:** HNSW (vector_cosine_ops), BGE-M3 1024차원

### SQL 컨벤션

- 테이블/컬럼: snake_case
- PK: `id` (UUID 또는 BIGINT IDENTITY)
- FK: `{참조테이블_단수}_id`
- 인덱스: `idx_{테이블}_{컬럼}`
- TIMESTAMPTZ 사용 (TIME ZONE 포함)
- CHECK 제약조건으로 enum 대체

### 테이블 목록 (36개)

- **정책/사용자 (8):** users, consent_logs, spoiler_settings, user_personas, notifications, persona_favorites, persona_relationships, usage_quotas
- **근거 데이터 (7):** webtoons, episodes, episode_emotions, episode_embeddings, comment_stats, lorebook_entries, review_cache
- **대화/생성 (5):** personas, live2d_models, chat_sessions, chat_messages, user_memories
- **LLM/과금 (3):** llm_models, token_usage_logs, credit_ledger
- **크레딧/구독 (4):** subscription_plans, user_subscriptions, credit_costs, credit_ledger
- **커뮤니티/에이전트 (11):** boards, board_posts, board_comments, board_reactions, persona_lounge_configs, agent_activity_logs, pending_posts, character_chat_sessions, character_chat_messages, world_events

### 주요 컬럼 변경 이력

- `users` — `role`, `adult_verified_at`, `preferred_llm_model_id`, `password_hash`, `credit_balance`, `last_credit_grant_at`, `preferred_themes` 추가. role CHECK에 'superadmin' 추가
- `personas` — `created_by`, `type`, `visibility`, `moderation_status`, `age_rating`, `live2d_model_id`, `background_image_url`, `category`, `description`, `greeting_message`, `scenario`, `example_dialogues`, `tags`, `chat_count`, `like_count`, `follower_count`, `is_character_page_enabled` 추가
- `chat_sessions` — `llm_model_id`, `title`, `is_pinned`, `user_persona_id` 추가
- `chat_messages` — `parent_id` (self FK, 분기용), `is_active`, `is_edited`, `edited_at` 추가
- `lorebook_entries` — `persona_id`, `created_by` 추가, `webtoon_id` NULLABLE
- 신규 테이블: `live2d_models`, `llm_models`, `token_usage_logs`, `user_personas`, `persona_favorites`, `persona_relationships`, `notifications`, `usage_quotas`, `subscription_plans`, `user_subscriptions`, `credit_ledger`, `credit_costs`, `boards`, `board_posts`, `board_comments`, `board_reactions`, `persona_lounge_configs`, `agent_activity_logs`, `pending_posts`, `character_chat_sessions`, `character_chat_messages`, `world_events`

## 성인인증 & 연령등급 게이트

```
사용자 가입 (age_group: 'unverified')
         │
         ▼
  성인인증 (/api/auth/adult-verify)
         ├─ 성공 → age_group = 'adult_verified', adult_verified_at = now()
         └─ 미인증 → 'minor_safe' 또는 'unverified' 유지
```

| 사용자 상태 | 전연령(all) | 15+ | 18+ |
|---|:---:|:---:|:---:|
| unverified | O | X | X |
| minor_safe | O | O | X |
| adult_verified | O | O | O |

- 게이트는 **API 미들웨어**에서 강제 (프롬프트 의존 금지)
- 18+ 페르소나 생성/접근: `adult_verified`만 가능

## LLM 모델 관리

```
사용자 요청 → inference_client.py
    → llm_models 테이블에서 provider/model_id 조회
    → provider별 분기 (runpod / openai / anthropic / google)
    → 응답 + 토큰 수 → token_usage_logs INSERT
```

**llm_models 주요 필드:** `provider`, `model_id`, `display_name`, `input_cost_per_1m`, `output_cost_per_1m`, `max_context_length`, `is_adult_only`, `is_active`, `tier`, `credit_per_1k_tokens`

## 토큰 사용량 & 크레딧

```
LLM 호출 완료 → token_usage_logs INSERT
    → cost = (input_tokens * input_cost / 1M) + (output_tokens * output_cost / 1M)
    → Redis 캐시 갱신: user:{id}:daily_usage, user:{id}:monthly_usage
```

- **크레딧 시스템:** 일일 무료 지급 + 유료 구매/구독, `credit_ledger`에 모든 변동 기록
- **Quota:** 일/월 토큰 한도 + 월 비용 한도, 초과 시 429

## 페르소나 시스템

| 항목 | 저장 위치 |
|---|---|
| 캐릭터 이름 | `personas.display_name` |
| 성격/시스템 프롬프트 | `personas.system_prompt` |
| 말투 규칙 | `personas.style_rules` (JSONB) |
| 리뷰 템플릿 | `personas.review_template` (JSONB) |
| 캐치프레이즈 | `personas.catchphrases` (TEXT[]) |
| Live2D 모델 | `personas.live2d_model_id` |
| 배경 이미지 | `personas.background_image_url` |
| 연령등급 | `personas.age_rating` ('all'/'15+'/'18+') |
| 공개 범위 | `personas.visibility` (private/public/unlisted) |
| 카테고리 | `personas.category` (romance/action/fantasy/daily/horror/comedy/drama/scifi) |
| 로어북 | `lorebook_entries` |

### 프롬프트 레이어 순서

1. 불변 정책 (스포일러/연령/PII/저작권 안전)
1.5. 세계관 이벤트 — [World Event] 블록
2. 사용자 정의 페르소나 (성격/말투/시스템 프롬프트 + scenario)
2.3. 관계 상태 — [Relationship] 블록
2.5. 사용자 페르소나 — [User Character] 블록
2.7. 예시 대화 — example_dialogues few-shot
3. 사용자 정의 로어북
3.5. 사용자 기억 — [User Memories] 블록
4. 세션 요약 + 최근 대화 (is_active=True)
5. 근거 번들 (검색 결과 + 감정 신호)

## RunPod Integration

- **엔진:** SGLang (RadixAttention 활성화, DISABLE_RADIX_CACHE=false)
- **기본 모델:** Llama 3 70B (4-bit 양자화), GPU: A100 80GB
- **과금:** 초 단위 Serverless, 콜드스타트 FlashBoot (~2초)
- **네트워크:** 서울↔미국 RTT ~150ms, SSE 스트리밍으로 체감 지연 상쇄
- **멀티 모델:** llm_models 테이블 기반 동적 라우팅

## 테스트

**반드시 venv 활성화 후 실행** (`backend/.venv/Scripts/activate` on Windows)

```bash
pytest backend/tests/ -v --cov=app --cov-report=term-missing  # 전체
pytest backend/tests/unit/ -v                                   # 단위만
pytest backend/tests/integration/ -v                            # 통합만
```

### 규칙

- 파일: `test_*.py`, 함수: `test_동작_조건_기대결과`
- 외부 의존성(RunPod, 외부 LLM API)만 mock, 내부 서비스는 실제 로직
- 비동기: `@pytest.mark.asyncio`, async fixture는 `@pytest_asyncio.fixture`
- DB 격리: 테스트마다 트랜잭션 롤백

### 필수 정책 검증 테스트 (CI 통과 필수)

- 미성년 사용자가 18+ 페르소나 접근 → 403
- 성인인증 미완료가 18+ 페르소나 생성 → 403
- 차단된 페르소나로 채팅 시도 → 403
- 타인의 private 페르소나 접근 → 403
- 관리자 API에 일반 사용자 접근 → 403
- PII 포함 입력 → 마스킹 처리 확인
- 토큰 사용량 기록 누락 없음 확인
