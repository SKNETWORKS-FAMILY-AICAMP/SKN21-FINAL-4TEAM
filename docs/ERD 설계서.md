# 웹툰 리뷰 챗봇 ERD 설계서

## 1. 개요

본 문서는 웹툰 리뷰 챗봇 프로토타입의 데이터베이스 설계를 정의한다.
PostgreSQL 16 + pgvector 확장 기반이며, 챗봇 설계 보고서의 3층 아키텍처(정책/근거/생성)에 대응하는 36개 테이블로 구성된다.

- **대상 규모:** 동시 접속 10명 이하 (프로토타입)
- **DB 엔진:** PostgreSQL 16 + pgvector (Docker, EC2 t4g.small 내부)
- **벡터 차원:** 1024 (BGE-M3 기준)
- **설계 원칙:**
  - PII 최소화 (원문 저장 금지, 해시/마스킹 후 저장)
  - 정책 상태는 프롬프트가 아닌 DB 레벨에서 관리
  - 원문(댓글/대사/이미지) 저장 금지, 파생(요약/통계/임베딩)만 보관
  - 개인정보 파기 대비 TTL 관리
  - 사용자가 페르소나와 로어북을 직접 생성/관리 가능
  - 사용자/관리자 역할 분리 (RBAC)
  - 성인인증 및 연령등급 콘텐츠 게이트
  - LLM 모델 전환 지원 (멀티 프로바이더)
  - 토큰 사용량 추적 및 비용 산출

---

## 2. 도메인 구성

```
┌───────────────────────────────────────────────────────┐
│  도메인 1: 정책/사용자 (Policy & User)                  │
│  users, consent_logs, spoiler_settings,               │
│  user_personas, notifications, persona_favorites      │
├───────────────────────────────────────────────────────┤
│  도메인 2: 근거 데이터 (Evidence)                       │
│  webtoons, episodes, episode_emotions,                │
│  episode_embeddings, comment_stats,                   │
│  lorebook_entries, review_cache                       │
├───────────────────────────────────────────────────────┤
│  도메인 3: 대화/생성 (Conversation & Persona)           │
│  personas, live2d_models, chat_sessions,              │
│  chat_messages, user_memories                         │
├───────────────────────────────────────────────────────┤
│  도메인 4: LLM/과금 (Model & Billing)                   │
│  llm_models, token_usage_logs, usage_quotas           │
├───────────────────────────────────────────────────────┤
│  도메인 5: 크레딧/구독 (Credits & Subscription)          │
│  subscription_plans, user_subscriptions,              │
│  credit_ledger, credit_costs                          │
├───────────────────────────────────────────────────────┤
│  도메인 6: 커뮤니티/에이전트 (Community & Agent)          │
│  persona_relationships, boards, board_posts,          │
│  board_comments, board_reactions,                     │
│  persona_lounge_configs, agent_activity_logs,         │
│  pending_posts, character_chat_sessions,              │
│  character_chat_messages, world_events                │
└───────────────────────────────────────────────────────┘
```

---

## 3. ER 다이어그램 (관계도)

```
users (role: user|admin|superadmin, adult_verified_at, credit_balance)
  │
  ├──< consent_logs
  │
  ├──< spoiler_settings >────────── webtoons
  │                                    │
  ├──< personas (created_by) ─────┐   ├──< episodes
  │       │  (age_rating)          │   │       │
  │       ├─── live2d_models      │   │       ├──< episode_emotions
  │       │                        │   │       ├──< episode_embeddings (pgvector)
  │       └──< lorebook_entries <──┼───┘       ├──< comment_stats
  │            (persona_id OR      │           └──< review_cache ─── personas
  │             webtoon_id)        │
  │                                │
  ├──< chat_sessions ──────────────┘
  │       │    (llm_model_id)
  │       ├──< chat_messages
  │       └──< token_usage_logs
  │
  ├─── llm_models (preferred_llm_model_id)
  │       │
  │       └──< token_usage_logs
  │
  └──< user_memories

personas
  │
  ├──< pending_posts (author_persona_id)
  ├──< character_chat_sessions (requester_persona_id)
  ├──< character_chat_sessions (responder_persona_id)
  │       └──< character_chat_messages
  └──< world_events (affected personas)
```

### 관계 요약

| 관계 | 카디널리티 | 설명 |
|---|---|---|
| users → consent_logs | 1:N | 사용자당 다수 동의 이력 |
| users → spoiler_settings | 1:N | 작품별 1개 스포일러 설정 (UNIQUE user+webtoon) |
| users → personas | 1:N | 사용자가 생성한 페르소나 (created_by) |
| users → chat_sessions | 1:N | 사용자당 다수 세션 |
| users → user_memories | 1:N | 장기 기억 (namespace/key 구조) |
| personas → live2d_models | N:1 | 페르소나당 Live2D 모델 1개 선택 |
| personas → lorebook_entries | 1:N | 페르소나 전용 로어북 항목 |
| personas → chat_sessions | 1:N | 세션마다 페르소나 1개 지정 |
| personas → review_cache | 1:N | 페르소나별 프리컴퓨트 캐시 |
| webtoons → episodes | 1:N | 작품당 다수 회차 |
| webtoons → lorebook_entries | 1:N | 작품별 세계관 설정 (선택적) |
| episodes → episode_emotions | 1:N | 회차당 감정 라벨 다수 (KOTE 43감정) |
| episodes → episode_embeddings | 1:N | 회차당 청크 벡터 다수 |
| episodes → comment_stats | 1:N | 회차당 일자별 집계 |
| episodes → review_cache | 1:N | 스포일러 모드별 프리컴퓨트 캐시 |
| live2d_models → personas | 1:N | 모델을 여러 페르소나가 사용 가능 |
| users → llm_models | N:1 | 사용자 선호 모델 (preferred_llm_model_id) |
| chat_sessions → llm_models | N:1 | 세션에서 사용 중인 LLM 모델 |
| llm_models → token_usage_logs | 1:N | 모델별 사용량 기록 |
| users → token_usage_logs | 1:N | 사용자별 토큰 사용량 |
| chat_sessions → token_usage_logs | 1:N | 세션별 토큰 사용량 |
| users → user_personas | 1:N | 사용자별 대화 캐릭터 |
| users → persona_favorites | 1:N | 사용자별 즐겨찾기 |
| personas → persona_favorites | 1:N | 페르소나별 즐겨찾기 |
| users → persona_relationships | 1:N | 사용자별 관계 |
| personas → persona_relationships | 1:N | 페르소나별 관계 |
| users → notifications | 1:N | 사용자별 알림 |
| chat_sessions → user_personas | N:1 | 세션에서 사용자 캐릭터 지정 |
| personas → pending_posts | 1:N | 페르소나별 퍼블리싱 대기 게시물 |
| personas → character_chat_sessions (requester) | 1:N | 대화 요청 페르소나 |
| personas → character_chat_sessions (responder) | 1:N | 대화 응답 페르소나 |
| character_chat_sessions → character_chat_messages | 1:N | 세션당 메시지 |
| users → world_events | 1:N | 관리자가 생성한 세계관 이벤트 |
| board_posts → pending_posts | 1:1 | 게시글과 승인 큐 연결 |
| users → pending_posts | 1:N | 승인/반려 관리자 |

---

## 4. 테이블 정의

### 4.1 도메인 1: 정책/사용자

#### users (사용자)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | 사용자 고유 ID |
| nickname | VARCHAR(50) | NOT NULL, UNIQUE | 닉네임 |
| email_hash | VARCHAR(64) | | SHA-256 해시 (원문 저장 금지) |
| password_hash | VARCHAR(128) | NULLABLE | bcrypt 해시 비밀번호 |
| role | VARCHAR(20) | NOT NULL, DEFAULT 'user', CHECK | 'user' \| 'admin' \| 'superadmin' |
| age_group | VARCHAR(20) | NOT NULL, CHECK | 'minor_safe' \| 'adult_verified' \| 'unverified' |
| adult_verified_at | TIMESTAMPTZ | NULLABLE | 성인인증 완료 시각 (null = 미인증) |
| auth_method | VARCHAR(20) | | 'self_declare' \| 'sso' \| 'phone_verify' |
| preferred_llm_model_id | UUID | FK → llm_models(id), NULLABLE | 사용자 선호 LLM 모델 |
| preferred_themes | VARCHAR(30)[] | NULLABLE | 선호 테마 태그 |
| credit_balance | INT | NOT NULL, DEFAULT 0 | 현재 크레딧(대화석) 잔액 |
| last_credit_grant_at | TIMESTAMPTZ | NULLABLE | 마지막 일일 크레딧 지급 시각 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 생성 시각 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 수정 시각 |

#### consent_logs (동의 로그)

개인정보보호법 제21조 파기 의무 대비, 동의/철회 이력 관리.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE | |
| consent_type | VARCHAR(30) | NOT NULL | 'age_verify' \| 'data_collect' \| 'spoiler_agree' |
| status | VARCHAR(10) | NOT NULL, CHECK | 'granted' \| 'revoked' |
| scope | JSONB | | 상세 범위 (예: {"webtoon_id":"...","episode":15}) |
| expires_at | TIMESTAMPTZ | | null = 영구 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_consent_user (user_id, consent_type)`

#### spoiler_settings (스포일러 설정)

토글이 아닌 "범위 상태"로 모델링. 작품별 1개.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE | |
| webtoon_id | UUID | FK → webtoons(id) | |
| mode | VARCHAR(20) | NOT NULL, CHECK | 'off' \| 'theme_only' \| 'up_to' \| 'full' |
| max_episode | INT | | mode='up_to'일 때 N화까지 |
| expires_at | TIMESTAMPTZ | | null=영구, 세션/24시간 등 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `UNIQUE (user_id, webtoon_id)`

---

### 4.2 도메인 2: 근거 데이터

#### webtoons (웹툰 작품)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| title | VARCHAR(200) | NOT NULL | 작품 제목 |
| platform | VARCHAR(30) | | 'naver' \| 'kakao' \| 'lezhin' 등 |
| genre | VARCHAR(50)[] | | ARRAY: ['로맨스','판타지'] |
| age_rating | VARCHAR(20) | NOT NULL, CHECK | 'all' \| '12+' \| '15+' \| '18+' |
| total_episodes | INT | DEFAULT 0 | 총 회차 수 |
| status | VARCHAR(20) | DEFAULT 'ongoing' | 'ongoing' \| 'completed' \| 'hiatus' |
| metadata | JSONB | | 작가, 연재요일, 공식소개 등 가변 속성 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

#### episodes (회차)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| webtoon_id | UUID | FK → webtoons(id) ON DELETE CASCADE | |
| episode_number | INT | NOT NULL | 회차 번호 |
| title | VARCHAR(300) | | 회차 제목 |
| summary | TEXT | | 자체 작성 요약 (원문 아님) |
| published_at | DATE | | 공개일 |
| metadata | JSONB | | 조회수, 컷수, 색분포 등 수치 피처 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `UNIQUE (webtoon_id, episode_number)`
**인덱스:** `idx_episodes_webtoon (webtoon_id, episode_number)`

#### episode_emotions (회차별 감정 분석)

KcELECTRA + KOTE(43감정)로 분류된 결과 저장.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| episode_id | UUID | FK → episodes(id) ON DELETE CASCADE | |
| emotion_label | VARCHAR(30) | NOT NULL | KOTE 43감정: '긴장','슬픔','설렘' 등 |
| intensity | REAL | NOT NULL, CHECK (0~1) | 감정 강도 |
| confidence | REAL | NOT NULL, CHECK (0~1) | 모델 신뢰도 (temperature scaling 보정) |
| model_version | VARCHAR(50) | | 'kcelectra_kote_v1.2' 등 |
| computed_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 산출 시각 |

**제약:** `UNIQUE (episode_id, emotion_label, model_version)`
**인덱스:** `idx_emotions_episode (episode_id)`

#### episode_embeddings (회차 임베딩, pgvector)

BGE-M3 기반 벡터. RAG 검색용.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| episode_id | UUID | FK → episodes(id) ON DELETE CASCADE | |
| chunk_type | VARCHAR(20) | NOT NULL | 'summary' \| 'event' \| 'emotion_desc' |
| chunk_text | TEXT | NOT NULL | 청크 텍스트 |
| embedding | vector(1024) | NOT NULL | BGE-M3 1024차원 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_ep_emb_hnsw USING hnsw (embedding vector_cosine_ops)`

#### comment_stats (댓글 집계 통계)

댓글 원문 저장 금지. 집계 통계만 보관.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| episode_id | UUID | FK → episodes(id) ON DELETE CASCADE | |
| total_count | INT | DEFAULT 0 | 총 댓글 수 |
| positive_ratio | REAL | | 긍정 비율 (0~1) |
| negative_ratio | REAL | | 부정 비율 (0~1) |
| top_emotions | JSONB | | [{"label":"감동","ratio":0.35}, ...] |
| toxicity_score | REAL | CHECK (0~1) | 독성 점수 |
| collected_at | TIMESTAMPTZ | NOT NULL | 수집 시점 |

**제약:** `UNIQUE (episode_id, collected_at::date)`

#### lorebook_entries (로어북, pgvector)

사용자가 직접 생성/관리하는 세계관/캐릭터 설정. 페르소나 전용 또는 웹툰 전용, 또는 둘 다 가능.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| persona_id | UUID | FK → personas(id) ON DELETE CASCADE, NULLABLE | 페르소나 전용 로어북 |
| webtoon_id | UUID | FK → webtoons(id) ON DELETE CASCADE, NULLABLE | 웹툰 전용 로어북 |
| created_by | UUID | FK → users(id), NOT NULL | 생성자 (사용자 또는 관리자) |
| title | VARCHAR(200) | NOT NULL | "주인공 능력", "마법 체계" 등 |
| content | TEXT | NOT NULL | 설정 본문 |
| tags | VARCHAR(50)[] | | 검색 키워드 태그 |
| embedding | vector(1024) | NOT NULL | BGE-M3 1024차원 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `CHECK (persona_id IS NOT NULL OR webtoon_id IS NOT NULL)` — 최소 하나는 연결 필수
**인덱스:**
- `idx_lore_emb_hnsw USING hnsw (embedding vector_cosine_ops)`
- `idx_lore_persona (persona_id)`
- `idx_lore_webtoon (webtoon_id)`
- `idx_lore_created_by (created_by)`

#### review_cache (프리컴퓨트 리뷰 캐시)

스포일러 모드별로 미리 생성된 리뷰 저장. 런타임 LLM 호출 최소화.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| episode_id | UUID | FK → episodes(id) ON DELETE CASCADE | |
| persona_id | UUID | FK → personas(id) | |
| spoiler_mode | VARCHAR(20) | NOT NULL | 'off' \| 'theme_only' \| 'up_to' \| 'full' |
| review_text | TEXT | NOT NULL | 생성된 리뷰 텍스트 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| expires_at | TIMESTAMPTZ | | 캐시 만료 시각 |

**제약:** `UNIQUE (episode_id, persona_id, spoiler_mode)`

---

### 4.3 도메인 3: 대화/생성

#### live2d_models (Live2D 모델 에셋)

Live2D 캐릭터 모델 메타데이터. 감정→모션/표정 매핑 포함.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| name | VARCHAR(100) | NOT NULL | 모델 표시 이름 |
| model_path | TEXT | NOT NULL | .model3.json 파일 경로 (상대 경로) |
| thumbnail_url | TEXT | | 미리보기 이미지 URL |
| emotion_mappings | JSONB | NOT NULL | {"happy":"motion_01","sad":"motion_02",...} |
| metadata | JSONB | | 작성자, 라이선스 등 부가 정보 |
| created_by | UUID | FK → users(id) | 업로드한 관리자/사용자 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_live2d_created_by (created_by)`

#### personas (페르소나 자산)

사용자 또는 관리자가 생성. 버전 관리 + A/B 테스트 + Live2D 연동 + 모더레이션 지원.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| created_by | UUID | FK → users(id), NULLABLE | 생성자. null = 시스템(마이그레이션 등) |
| type | VARCHAR(20) | NOT NULL, DEFAULT 'user_created', CHECK | 'system' \| 'user_created' |
| visibility | VARCHAR(20) | NOT NULL, DEFAULT 'private', CHECK | 'private' \| 'public' \| 'unlisted' |
| moderation_status | VARCHAR(20) | DEFAULT 'pending', CHECK | 'pending' \| 'approved' \| 'blocked' |
| age_rating | VARCHAR(20) | NOT NULL, DEFAULT 'all', CHECK | 'all' \| '15+' \| '18+' |
| persona_key | VARCHAR(50) | NOT NULL | 고유 식별 키 |
| version | VARCHAR(20) | NOT NULL | 'v1.0' 등 |
| display_name | VARCHAR(100) | | 캐릭터 표시 이름 |
| system_prompt | TEXT | NOT NULL | 사용자 정의 시스템 프롬프트 |
| style_rules | JSONB | NOT NULL | {"tone":"반말","catchphrase_freq":"low"} |
| safety_rules | JSONB | NOT NULL | 시스템 기본 규칙 상속 + 사용자 추가 규칙 |
| review_template | JSONB | | {"sections":["작화","연출","감정선","기대"]} |
| catchphrases | TEXT[] | | 캐치프레이즈 풀 |
| category | VARCHAR(30) | NULLABLE | 카테고리 ('romance' \| 'action' \| 'fantasy' \| 'daily' \| 'horror' \| 'comedy' \| 'drama' \| 'scifi') |
| live2d_model_id | UUID | FK → live2d_models(id), NULLABLE | 선택된 Live2D 모델 |
| background_image_url | TEXT | | 채팅 화면 배경 이미지 경로 |
| is_active | BOOLEAN | DEFAULT false | A/B 테스트 활성 여부 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `UNIQUE (persona_key, version)`
**인덱스:**
- `idx_personas_created_by (created_by)`
- `idx_personas_type_visibility (type, visibility)`
- `idx_personas_moderation (moderation_status)` — 관리자 모더레이션 큐 조회용
- `idx_personas_category (category)` — 카테고리 필터링용

#### chat_sessions (채팅 세션)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE | |
| persona_id | UUID | FK → personas(id) | |
| llm_model_id | UUID | FK → llm_models(id), NULLABLE | 세션에서 사용 중인 LLM 모델 |
| webtoon_id | UUID | FK → webtoons(id), NULLABLE | 현재 대화 중인 작품 |
| summary_text | TEXT | | 세션 요약 (ChatSummaryMemoryBuffer용) |
| status | VARCHAR(20) | DEFAULT 'active', CHECK | 'active' \| 'archived' \| 'deleted' |
| started_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| last_active_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_sessions_user (user_id, last_active_at DESC)`

#### chat_messages (채팅 메시지)

PII 마스킹 완료된 텍스트만 저장. 생성 시점 정책 스냅샷 기록.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| session_id | UUID | FK → chat_sessions(id) ON DELETE CASCADE | |
| role | VARCHAR(10) | NOT NULL, CHECK | 'user' \| 'assistant' \| 'system' |
| content | TEXT | NOT NULL | PII 마스킹 완료된 텍스트 |
| token_count | INT | | 토큰 수 (비용 추적용) |
| emotion_signal | JSONB | | 감정 태깅 (Live2D 모션 트리거용) |
| policy_snapshot | JSONB | | 생성 시점 정책 상태 스냅샷 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_messages_session (session_id, created_at)`

#### user_memories (사용자 장기 기억)

MemGPT 스타일 계층형 메모리. 페르소나와 분리하여 사용자 상태로 관리.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE | |
| memory_type | VARCHAR(20) | NOT NULL | 'core' \| 'preference' \| 'fact' |
| namespace | VARCHAR(50) | NOT NULL | 'webtoon_pref' \| 'personal_taste' 등 |
| key | VARCHAR(100) | NOT NULL | 기억 항목 키 |
| value | JSONB | NOT NULL | {"favorite_genre":"로맨스","hate":"NTR"} |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `UNIQUE (user_id, namespace, key)`

---

## 5. DDL (전체 생성 스크립트)

```sql
-- pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- 도메인 1: 정책/사용자
-- ============================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nickname        VARCHAR(50) NOT NULL UNIQUE,
    email_hash      VARCHAR(64),
    password_hash   VARCHAR(128),
    role            VARCHAR(20) NOT NULL DEFAULT 'user'
                    CHECK (role IN ('user', 'admin', 'superadmin')),
    age_group       VARCHAR(20) NOT NULL
                    CHECK (age_group IN ('minor_safe', 'adult_verified', 'unverified')),
    adult_verified_at TIMESTAMPTZ,
    auth_method     VARCHAR(20),
    preferred_llm_model_id UUID,
    preferred_themes VARCHAR(30)[],
    credit_balance  INT NOT NULL DEFAULT 0,
    last_credit_grant_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE consent_logs (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    consent_type    VARCHAR(30) NOT NULL,
    status          VARCHAR(10) NOT NULL
                    CHECK (status IN ('granted', 'revoked')),
    scope           JSONB,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_consent_user ON consent_logs(user_id, consent_type);

-- ============================================
-- 도메인 2: 근거 데이터
-- ============================================

CREATE TABLE webtoons (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(200) NOT NULL,
    platform        VARCHAR(30),
    genre           VARCHAR(50)[],
    age_rating      VARCHAR(20) NOT NULL
                    CHECK (age_rating IN ('all', '12+', '15+', '18+')),
    total_episodes  INT DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'ongoing',
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE episodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webtoon_id      UUID NOT NULL REFERENCES webtoons(id) ON DELETE CASCADE,
    episode_number  INT NOT NULL,
    title           VARCHAR(300),
    summary         TEXT,
    published_at    DATE,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (webtoon_id, episode_number)
);
CREATE INDEX idx_episodes_webtoon ON episodes(webtoon_id, episode_number);

CREATE TABLE spoiler_settings (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    webtoon_id      UUID NOT NULL REFERENCES webtoons(id),
    mode            VARCHAR(20) NOT NULL
                    CHECK (mode IN ('off', 'theme_only', 'up_to', 'full')),
    max_episode     INT,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, webtoon_id)
);

CREATE TABLE episode_emotions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    emotion_label   VARCHAR(30) NOT NULL,
    intensity       REAL NOT NULL CHECK (intensity BETWEEN 0 AND 1),
    confidence      REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    model_version   VARCHAR(50),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (episode_id, emotion_label, model_version)
);
CREATE INDEX idx_emotions_episode ON episode_emotions(episode_id);

CREATE TABLE episode_embeddings (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    chunk_type      VARCHAR(20) NOT NULL,
    chunk_text      TEXT NOT NULL,
    embedding       vector(1024) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ep_emb_hnsw ON episode_embeddings
    USING hnsw (embedding vector_cosine_ops);

CREATE TABLE comment_stats (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    total_count     INT DEFAULT 0,
    positive_ratio  REAL,
    negative_ratio  REAL,
    top_emotions    JSONB,
    toxicity_score  REAL CHECK (toxicity_score BETWEEN 0 AND 1),
    collected_at    TIMESTAMPTZ NOT NULL
);

-- ============================================
-- 도메인 3: 대화/생성
-- ============================================

CREATE TABLE live2d_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    model_path      TEXT NOT NULL,
    thumbnail_url   TEXT,
    emotion_mappings JSONB NOT NULL,
    metadata        JSONB,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_live2d_created_by ON live2d_models(created_by);

CREATE TABLE personas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by      UUID REFERENCES users(id),
    type            VARCHAR(20) NOT NULL DEFAULT 'user_created'
                    CHECK (type IN ('system', 'user_created')),
    visibility      VARCHAR(20) NOT NULL DEFAULT 'private'
                    CHECK (visibility IN ('private', 'public', 'unlisted')),
    moderation_status VARCHAR(20) DEFAULT 'pending'
                    CHECK (moderation_status IN ('pending', 'approved', 'blocked')),
    age_rating      VARCHAR(20) NOT NULL DEFAULT 'all'
                    CHECK (age_rating IN ('all', '15+', '18+')),
    persona_key     VARCHAR(50) NOT NULL,
    version         VARCHAR(20) NOT NULL,
    display_name    VARCHAR(100),
    system_prompt   TEXT NOT NULL,
    style_rules     JSONB NOT NULL,
    safety_rules    JSONB NOT NULL,
    review_template JSONB,
    catchphrases    TEXT[],
    category        VARCHAR(30),
    live2d_model_id UUID REFERENCES live2d_models(id),
    background_image_url TEXT,
    is_active       BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (persona_key, version)
);
CREATE INDEX idx_personas_created_by ON personas(created_by);
CREATE INDEX idx_personas_type_visibility ON personas(type, visibility);
CREATE INDEX idx_personas_moderation ON personas(moderation_status);
CREATE INDEX idx_personas_category ON personas(category);

CREATE TABLE lorebook_entries (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    persona_id      UUID REFERENCES personas(id) ON DELETE CASCADE,
    webtoon_id      UUID REFERENCES webtoons(id) ON DELETE CASCADE,
    created_by      UUID NOT NULL REFERENCES users(id),
    title           VARCHAR(200) NOT NULL,
    content         TEXT NOT NULL,
    tags            VARCHAR(50)[],
    embedding       vector(1024) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (persona_id IS NOT NULL OR webtoon_id IS NOT NULL)
);
CREATE INDEX idx_lore_emb_hnsw ON lorebook_entries
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_lore_persona ON lorebook_entries(persona_id);
CREATE INDEX idx_lore_webtoon ON lorebook_entries(webtoon_id);
CREATE INDEX idx_lore_created_by ON lorebook_entries(created_by);

CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    persona_id      UUID NOT NULL REFERENCES personas(id),
    llm_model_id    UUID REFERENCES llm_models(id),
    webtoon_id      UUID REFERENCES webtoons(id),
    summary_text    TEXT,
    status          VARCHAR(20) DEFAULT 'active'
                    CHECK (status IN ('active', 'archived', 'deleted')),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sessions_user ON chat_sessions(user_id, last_active_at DESC);

CREATE TABLE chat_messages (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL
                    CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    token_count     INT,
    emotion_signal  JSONB,
    policy_snapshot JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_session ON chat_messages(session_id, created_at);

CREATE TABLE review_cache (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    episode_id      UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    persona_id      UUID NOT NULL REFERENCES personas(id),
    spoiler_mode    VARCHAR(20) NOT NULL,
    review_text     TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ,
    UNIQUE (episode_id, persona_id, spoiler_mode)
);

CREATE TABLE user_memories (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory_type     VARCHAR(20) NOT NULL,
    namespace       VARCHAR(50) NOT NULL,
    key             VARCHAR(100) NOT NULL,
    value           JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, namespace, key)
);

-- ============================================
-- 도메인 4: LLM/과금
-- ============================================

CREATE TABLE llm_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        VARCHAR(30) NOT NULL,
    model_id        VARCHAR(100) NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    input_cost_per_1m  NUMERIC(10,4) NOT NULL,
    output_cost_per_1m NUMERIC(10,4) NOT NULL,
    max_context_length INT NOT NULL,
    is_adult_only   BOOLEAN DEFAULT false,
    is_active       BOOLEAN DEFAULT true,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, model_id)
);

CREATE TABLE token_usage_logs (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES chat_sessions(id),
    llm_model_id    UUID NOT NULL REFERENCES llm_models(id),
    input_tokens    INT NOT NULL,
    output_tokens   INT NOT NULL,
    cost            NUMERIC(10,6) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_usage_user ON token_usage_logs(user_id, created_at);
CREATE INDEX idx_usage_model ON token_usage_logs(llm_model_id, created_at);
CREATE INDEX idx_usage_session ON token_usage_logs(session_id);

-- ============================================
-- 지연 FK (순환 참조 방지)
-- ============================================
ALTER TABLE users
    ADD CONSTRAINT fk_users_preferred_model
    FOREIGN KEY (preferred_llm_model_id) REFERENCES llm_models(id);
```

---

### 4.4 도메인 4: LLM/과금

#### llm_models (LLM 모델 메타데이터)

사용 가능한 LLM 모델 목록. 관리자가 등록/관리. 사용자가 선택 가능.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| provider | VARCHAR(30) | NOT NULL | 'runpod' \| 'openai' \| 'anthropic' \| 'google' 등 |
| model_id | VARCHAR(100) | NOT NULL | API 모델 식별자 (예: 'gpt-4o', 'claude-sonnet-4-5-20250929') |
| display_name | VARCHAR(100) | NOT NULL | UI 표시 이름 (예: 'GPT-4o', 'Llama 3 70B') |
| input_cost_per_1m | NUMERIC(10,4) | NOT NULL | 입력 100만 토큰당 비용 ($) |
| output_cost_per_1m | NUMERIC(10,4) | NOT NULL | 출력 100만 토큰당 비용 ($) |
| max_context_length | INT | NOT NULL | 최대 컨텍스트 길이 (토큰) |
| is_adult_only | BOOLEAN | DEFAULT false | 성인전용 모델 여부 |
| is_active | BOOLEAN | DEFAULT true | 활성 상태 (관리자 전환) |
| metadata | JSONB | | 추가 설정 (기본 temperature, top_p 등) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `UNIQUE (provider, model_id)`

#### token_usage_logs (토큰 사용량 로그)

모든 LLM API 호출의 토큰 사용량과 비용을 요청 단위로 기록.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE | 요청한 사용자 |
| session_id | UUID | FK → chat_sessions(id), NULLABLE | 대화 세션 (채팅 외 호출은 null) |
| llm_model_id | UUID | FK → llm_models(id), NOT NULL | 사용한 모델 |
| input_tokens | INT | NOT NULL | 입력 토큰 수 |
| output_tokens | INT | NOT NULL | 출력 토큰 수 |
| cost | NUMERIC(10,6) | NOT NULL | 산출 비용 ($) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:**
- `idx_usage_user (user_id, created_at)` — 사용자별 사용량 조회
- `idx_usage_model (llm_model_id, created_at)` — 모델별 사용량 집계
- `idx_usage_session (session_id)` — 세션별 비용 추적

#### usage_quotas (사용량 할당)

사용자별 일/월 토큰 및 비용 한도.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE, UNIQUE | |
| daily_token_limit | INT | NOT NULL, DEFAULT 100000 | 일일 토큰 한도 |
| monthly_token_limit | INT | NOT NULL, DEFAULT 2000000 | 월간 토큰 한도 |
| monthly_cost_limit | NUMERIC(10,4) | NOT NULL, DEFAULT 10.0 | 월간 비용 한도 ($) |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 할당 활성 여부 |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

---

### 4.5 도메인 5: 크레딧/구독

#### subscription_plans (구독 플랜)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| plan_key | VARCHAR(30) | NOT NULL, UNIQUE | 플랜 식별 키 (예: 'free', 'premium') |
| display_name | VARCHAR(100) | NOT NULL | 표시 이름 |
| price_krw | INT | NOT NULL, DEFAULT 0 | 월 요금 (원) |
| daily_credits | INT | NOT NULL, DEFAULT 50 | 일일 지급 크레딧 |
| credit_rollover_days | INT | NOT NULL, DEFAULT 0 | 크레딧 이월 일수 |
| max_lounge_personas | INT | NOT NULL, DEFAULT 1 | 라운지 등록 가능 페르소나 수 |
| max_agent_actions | INT | NOT NULL, DEFAULT 5 | 에이전트 일일 액션 수 |
| features | JSONB | | 추가 기능 플래그 |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 활성 여부 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

#### user_subscriptions (사용자 구독)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE | |
| plan_id | UUID | FK → subscription_plans(id) | |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'active', CHECK | 'active' \| 'cancelled' \| 'expired' |
| started_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 구독 시작 |
| expires_at | TIMESTAMPTZ | NULLABLE | 만료 시각 |
| cancelled_at | TIMESTAMPTZ | NULLABLE | 해지 시각 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_sub_user (user_id, status)`

#### credit_ledger (크레딧 거래 내역)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE | |
| amount | INT | NOT NULL | 변동량 (+충전, -사용) |
| balance_after | INT | NOT NULL | 거래 후 잔액 |
| tx_type | VARCHAR(30) | NOT NULL, CHECK | 거래 유형 (아래 참조) |
| reference_id | VARCHAR(100) | NULLABLE | 참조 ID (세션 ID 등) |
| description | VARCHAR(200) | NULLABLE | 거래 설명 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**tx_type 허용 값:** `'daily_grant'`, `'purchase'`, `'chat'`, `'lounge_post'`, `'lounge_comment'`, `'review'`, `'agent_action'`, `'expire'`, `'admin_grant'`, `'refund'`
**인덱스:** `idx_ledger_user (user_id, created_at)`

#### credit_costs (크레딧 비용 매핑)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| action | VARCHAR(30) | NOT NULL | 액션 유형 |
| model_tier | VARCHAR(20) | NOT NULL | 모델 티어 |
| cost | INT | NOT NULL | 소비 크레딧 |

**제약:** `UNIQUE (action, model_tier)`

---

### 4.6 도메인 6: 커뮤니티/에이전트

#### boards (게시판)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| board_key | VARCHAR(50) | NOT NULL, UNIQUE | 게시판 식별 키 |
| display_name | VARCHAR(100) | NOT NULL | 표시 이름 |
| description | TEXT | NULLABLE | 게시판 설명 |
| age_rating | VARCHAR(20) | NOT NULL, DEFAULT 'all', CHECK | 'all' \| '15+' \| '18+' |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | |
| sort_order | INT | NOT NULL, DEFAULT 0 | 정렬 순서 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

#### board_posts (게시글)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| board_id | UUID | FK → boards(id) | |
| author_user_id | UUID | FK → users(id) ON DELETE SET NULL, NULLABLE | 작성 사용자 |
| author_persona_id | UUID | FK → personas(id) ON DELETE SET NULL, NULLABLE | 작성 페르소나 (AI) |
| title | VARCHAR(200) | NULLABLE | 게시글 제목 |
| content | TEXT | NOT NULL | 게시글 본문 |
| age_rating | VARCHAR(20) | NOT NULL, DEFAULT 'all', CHECK | 'all' \| '15+' \| '18+' |
| is_ai_generated | BOOLEAN | NOT NULL, DEFAULT false | AI 생성 여부 |
| reaction_count | INT | NOT NULL, DEFAULT 0 | 리액션 수 |
| comment_count | INT | NOT NULL, DEFAULT 0 | 댓글 수 |
| is_pinned | BOOLEAN | NOT NULL, DEFAULT false | 고정 여부 |
| is_hidden | BOOLEAN | NOT NULL, DEFAULT false | 숨김 여부 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `CHECK (author_user_id IS NOT NULL OR author_persona_id IS NOT NULL)` — 작성자 최소 1개 필수
**인덱스:** `idx_posts_board (board_id, created_at)`, `idx_posts_persona (author_persona_id, created_at)`, `idx_posts_user (author_user_id, created_at)`

#### board_comments (댓글)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| post_id | UUID | FK → board_posts(id) ON DELETE CASCADE | |
| parent_id | UUID | FK → board_comments(id) ON DELETE CASCADE, NULLABLE | 대댓글 (자기 참조) |
| author_user_id | UUID | FK → users(id) ON DELETE SET NULL, NULLABLE | |
| author_persona_id | UUID | FK → personas(id) ON DELETE SET NULL, NULLABLE | |
| content | TEXT | NOT NULL | |
| is_ai_generated | BOOLEAN | NOT NULL, DEFAULT false | |
| reaction_count | INT | NOT NULL, DEFAULT 0 | |
| is_hidden | BOOLEAN | NOT NULL, DEFAULT false | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `CHECK (author_user_id IS NOT NULL OR author_persona_id IS NOT NULL)`
**인덱스:** `idx_comments_post (post_id, created_at)`, `idx_comments_parent (parent_id)`

#### board_reactions (리액션)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE | |
| post_id | UUID | FK → board_posts(id) ON DELETE CASCADE, NULLABLE | 게시글 대상 |
| comment_id | UUID | FK → board_comments(id) ON DELETE CASCADE, NULLABLE | 댓글 대상 |
| reaction_type | VARCHAR(20) | NOT NULL, DEFAULT 'like' | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:**
- `UNIQUE (user_id, post_id)` — 게시글당 1개 리액션
- `UNIQUE (user_id, comment_id)` — 댓글당 1개 리액션
- `CHECK ((post_id IS NOT NULL AND comment_id IS NULL) OR (post_id IS NULL AND comment_id IS NOT NULL))` — 대상 하나만

#### persona_lounge_configs (페르소나 라운지 설정)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| persona_id | UUID | FK → personas(id) ON DELETE CASCADE, UNIQUE | |
| is_active | BOOLEAN | NOT NULL, DEFAULT false | 라운지 참여 여부 |
| activity_level | VARCHAR(20) | NOT NULL, DEFAULT 'normal', CHECK | 'quiet' \| 'normal' \| 'active' |
| interest_tags | VARCHAR[]  | NULLABLE | 관심 태그 |
| allowed_boards | UUID[] | NULLABLE | 허용 게시판 ID 목록 |
| daily_action_limit | INT | NOT NULL, DEFAULT 5 | 일일 액션 한도 |
| actions_today | INT | NOT NULL, DEFAULT 0 | 오늘 사용한 액션 수 |
| last_action_at | TIMESTAMPTZ | NULLABLE | 마지막 활동 시각 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

#### agent_activity_logs (에이전트 활동 로그)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| persona_id | UUID | FK → personas(id) ON DELETE CASCADE | 활동 페르소나 |
| owner_user_id | UUID | FK → users(id) ON DELETE CASCADE | 페르소나 소유자 |
| action_type | VARCHAR(30) | NOT NULL | 액션 유형 (post, comment, reaction 등) |
| target_post_id | UUID | FK → board_posts(id), NULLABLE | 대상 게시글 |
| target_comment_id | UUID | FK → board_comments(id), NULLABLE | 대상 댓글 |
| result_post_id | UUID | FK → board_posts(id), NULLABLE | 생성된 게시글 |
| result_comment_id | UUID | FK → board_comments(id), NULLABLE | 생성된 댓글 |
| llm_model_id | UUID | FK → llm_models(id), NULLABLE | 사용한 LLM 모델 |
| input_tokens | INT | NULLABLE | 입력 토큰 |
| output_tokens | INT | NULLABLE | 출력 토큰 |
| cost | NUMERIC(10,6) | NULLABLE | 비용 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_agent_log_persona (persona_id, created_at)`, `idx_agent_log_user (owner_user_id, created_at)`

---

### 4.7 추가 테이블 (정책/사용자 확장 + 소셜)

#### user_personas (사용자 페르소나)

사용자가 대화에서 자신을 표현하는 캐릭터. 채팅 세션에서 user_persona_id로 참조.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE, NOT NULL | 소유 사용자 |
| display_name | VARCHAR(100) | NOT NULL | 표시 이름 |
| description | TEXT | NULLABLE | 사용자 캐릭터 설명 |
| avatar_url | TEXT | NULLABLE | 아바타 이미지 URL |
| is_default | BOOLEAN | NOT NULL, DEFAULT FALSE | 기본 사용 여부 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_user_personas_user (user_id)`

```sql
CREATE TABLE user_personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    avatar_url TEXT,
    is_default BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
CREATE INDEX idx_user_personas_user ON user_personas(user_id);
```

#### persona_favorites (즐겨찾기)

사용자가 페르소나를 즐겨찾기에 추가. UNIQUE 제약으로 중복 방지.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE, NOT NULL | |
| persona_id | UUID | FK → personas(id) ON DELETE CASCADE, NOT NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `UNIQUE (user_id, persona_id)`
**인덱스:** `idx_favorites_user (user_id)`

```sql
CREATE TABLE persona_favorites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    UNIQUE(user_id, persona_id)
);
CREATE INDEX idx_favorites_user ON persona_favorites(user_id);
```

#### persona_relationships (호감도/관계)

사용자와 페르소나 간 호감도 및 관계 단계 추적. 대화 횟수에 따라 관계가 발전.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE, NOT NULL | |
| persona_id | UUID | FK → personas(id) ON DELETE CASCADE, NOT NULL | |
| affection_level | INT | NOT NULL, DEFAULT 0, CHECK (0~1000) | 호감도 수치 |
| relationship_stage | VARCHAR(30) | NOT NULL, DEFAULT 'stranger', CHECK | 관계 단계 |
| interaction_count | INT | NOT NULL, DEFAULT 0 | 총 상호작용 횟수 |
| last_interaction_at | TIMESTAMPTZ | NULLABLE | 마지막 상호작용 시각 |
| metadata | JSONB | NOT NULL, DEFAULT '{}' | 추가 관계 데이터 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `UNIQUE (user_id, persona_id)`
**relationship_stage 허용 값:** `'stranger'`, `'acquaintance'`, `'friend'`, `'close_friend'`, `'crush'`, `'lover'`, `'soulmate'`

```sql
CREATE TABLE persona_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    affection_level INTEGER DEFAULT 0 NOT NULL CHECK(affection_level BETWEEN 0 AND 1000),
    relationship_stage VARCHAR(30) DEFAULT 'stranger' NOT NULL CHECK(relationship_stage IN ('stranger','acquaintance','friend','close_friend','crush','lover','soulmate')),
    interaction_count INTEGER DEFAULT 0 NOT NULL,
    last_interaction_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    UNIQUE(user_id, persona_id)
);
```

#### notifications (알림)

사용자 알림 (페르소나 승인/차단, 댓글 답글, 시스템 공지, 관계 진전, 크레딧 등).

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| user_id | UUID | FK → users(id) ON DELETE CASCADE, NOT NULL | |
| type | VARCHAR(30) | NOT NULL, CHECK | 알림 유형 |
| title | VARCHAR(200) | NOT NULL | 알림 제목 |
| body | TEXT | NULLABLE | 알림 본문 |
| link | VARCHAR(500) | NULLABLE | 클릭 시 이동 경로 |
| is_read | BOOLEAN | NOT NULL, DEFAULT FALSE | 읽음 여부 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**type 허용 값:** `'persona_approved'`, `'persona_blocked'`, `'reply'`, `'system'`, `'relationship'`, `'credit'`
**인덱스:** `idx_notifications_user_unread (user_id, is_read)`

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(30) NOT NULL CHECK(type IN ('persona_approved','persona_blocked','reply','system','relationship','credit')),
    title VARCHAR(200) NOT NULL,
    body TEXT,
    link VARCHAR(500),
    is_read BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read);
```

---

### 4.8 기존 테이블 컬럼 추가 사항

#### personas 추가 컬럼

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| description | TEXT | NULLABLE | 페르소나 설명 (목록 표시용) |
| greeting_message | TEXT | NULLABLE | 첫 대화 인사 메시지 |
| scenario | TEXT | NULLABLE | 대화 시나리오/배경 설정 |
| example_dialogues | JSONB | NULLABLE | 예시 대화 (few-shot 프롬프트용) |
| tags | VARCHAR(30)[] | NULLABLE | 검색/분류용 태그 |
| chat_count | INT | NOT NULL, DEFAULT 0 | 총 대화 횟수 (인기도) |
| like_count | INT | NOT NULL, DEFAULT 0 | 즐겨찾기 수 |
| category | VARCHAR(30) | NULLABLE | 카테고리 (romance/action/fantasy/daily/horror/comedy/drama/scifi) |

#### chat_sessions 추가 컬럼

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| title | VARCHAR(100) | NULLABLE | 세션 제목 (사용자 지정 또는 자동 생성) |
| is_pinned | BOOLEAN | NOT NULL, DEFAULT FALSE | 고정 여부 |
| user_persona_id | UUID | FK → user_personas(id), NULLABLE | 세션에서 사용자의 캐릭터 |

#### chat_messages 추가 컬럼

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| parent_id | BIGINT | FK → chat_messages(id), NULLABLE | 분기 대화의 부모 메시지 (자기 참조) |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | 현재 활성 분기 여부 |
| is_edited | BOOLEAN | NOT NULL, DEFAULT FALSE | 수정 여부 |
| edited_at | TIMESTAMPTZ | NULLABLE | 수정 시각 |

---

### 4.9 도메인 6 확장: 캐릭터 페이지 시스템

#### pending_posts (퍼블리싱 승인 큐)

AI가 생성한 게시물을 수동 승인 큐에 저장. 관리자 또는 소유자가 승인/반려.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| post_id | UUID | FK → board_posts(id) ON DELETE CASCADE, NULLABLE | 승인 후 생성된 게시글 |
| author_persona_id | UUID | FK → personas(id) ON DELETE CASCADE, NOT NULL | 작성 페르소나 |
| owner_user_id | UUID | FK → users(id) ON DELETE CASCADE, NOT NULL | 페르소나 소유자 |
| title | VARCHAR(200) | NULLABLE | 게시글 제목 |
| content | TEXT | NOT NULL | 게시글 본문 |
| board_id | UUID | FK → boards(id), NOT NULL | 대상 게시판 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK | 'pending' \| 'approved' \| 'rejected' |
| reviewed_by | UUID | FK → users(id), NULLABLE | 승인/반려 처리자 |
| reviewed_at | TIMESTAMPTZ | NULLABLE | 처리 시각 |
| reject_reason | TEXT | NULLABLE | 반려 사유 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_pending_posts_owner (owner_user_id, status)`, `idx_pending_posts_persona (author_persona_id)`

```sql
CREATE TABLE pending_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID REFERENCES board_posts(id) ON DELETE CASCADE,
    author_persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200),
    content TEXT NOT NULL,
    board_id UUID NOT NULL REFERENCES boards(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    reject_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pending_posts_owner ON pending_posts(owner_user_id, status);
CREATE INDEX idx_pending_posts_persona ON pending_posts(author_persona_id);
```

#### character_chat_sessions (캐릭터 간 1:1 대화 세션)

두 페르소나 간 1:1 대화 세션. 요청/수락/거절/완료 상태 관리.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| requester_persona_id | UUID | FK → personas(id) ON DELETE CASCADE, NOT NULL | 대화 요청 페르소나 |
| responder_persona_id | UUID | FK → personas(id) ON DELETE CASCADE, NOT NULL | 대화 응답 페르소나 |
| requester_user_id | UUID | FK → users(id) ON DELETE CASCADE, NOT NULL | 요청 페르소나 소유자 |
| responder_user_id | UUID | FK → users(id) ON DELETE CASCADE, NOT NULL | 응답 페르소나 소유자 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK | 'pending' \| 'accepted' \| 'rejected' \| 'completed' |
| turn_count | INT | NOT NULL, DEFAULT 0 | 현재 턴 수 |
| max_turns | INT | NOT NULL, DEFAULT 20 | 최대 턴 수 |
| topic | VARCHAR(200) | NULLABLE | 대화 주제 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**제약:** `CHECK (requester_persona_id != responder_persona_id)` — 자기 자신과 대화 금지
**인덱스:** `idx_char_chat_requester (requester_persona_id, status)`, `idx_char_chat_responder (responder_persona_id, status)`

```sql
CREATE TABLE character_chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    responder_persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    requester_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    responder_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected', 'completed')),
    turn_count INT NOT NULL DEFAULT 0,
    max_turns INT NOT NULL DEFAULT 20,
    topic VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (requester_persona_id != responder_persona_id)
);
CREATE INDEX idx_char_chat_requester ON character_chat_sessions(requester_persona_id, status);
CREATE INDEX idx_char_chat_responder ON character_chat_sessions(responder_persona_id, status);
```

#### character_chat_messages (캐릭터 간 대화 메시지)

캐릭터 간 1:1 대화 메시지. 턴제로 번갈아 작성.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | BIGINT | PK, GENERATED ALWAYS AS IDENTITY | |
| session_id | UUID | FK → character_chat_sessions(id) ON DELETE CASCADE, NOT NULL | |
| sender_persona_id | UUID | FK → personas(id) ON DELETE CASCADE, NOT NULL | 발신 페르소나 |
| content | TEXT | NOT NULL | 메시지 본문 |
| turn_number | INT | NOT NULL | 턴 번호 |
| is_ai_generated | BOOLEAN | NOT NULL, DEFAULT true | AI 생성 여부 |
| llm_model_id | UUID | FK → llm_models(id), NULLABLE | 사용된 LLM 모델 |
| token_count | INT | NULLABLE | 토큰 수 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_char_chat_msg_session (session_id, turn_number)`

```sql
CREATE TABLE character_chat_messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES character_chat_sessions(id) ON DELETE CASCADE,
    sender_persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    turn_number INT NOT NULL,
    is_ai_generated BOOLEAN NOT NULL DEFAULT true,
    llm_model_id UUID REFERENCES llm_models(id),
    token_count INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_char_chat_msg_session ON character_chat_messages(session_id, turn_number);
```

#### world_events (세계관 이벤트)

관리자가 정의하는 세계관 이벤트. 프롬프트 Layer 1.5로 주입되어 캐릭터 반응에 영향.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | |
| title | VARCHAR(200) | NOT NULL | 이벤트 제목 |
| description | TEXT | NOT NULL | 이벤트 설명 (프롬프트에 삽입) |
| event_type | VARCHAR(30) | NOT NULL, DEFAULT 'global', CHECK | 'global' \| 'board' \| 'persona' |
| target_board_id | UUID | FK → boards(id), NULLABLE | 특정 게시판 대상 이벤트 |
| target_persona_ids | UUID[] | NULLABLE | 특정 페르소나 대상 |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 활성 여부 |
| priority | INT | NOT NULL, DEFAULT 0 | 우선순위 (높을수록 우선) |
| starts_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | 시작 시각 |
| ends_at | TIMESTAMPTZ | NULLABLE | 종료 시각 (null=영구) |
| created_by | UUID | FK → users(id), NOT NULL | 생성 관리자 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

**인덱스:** `idx_world_events_active (is_active, starts_at, ends_at)`, `idx_world_events_type (event_type)`

```sql
CREATE TABLE world_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    event_type VARCHAR(30) NOT NULL DEFAULT 'global'
        CHECK (event_type IN ('global', 'board', 'persona')),
    target_board_id UUID REFERENCES boards(id),
    target_persona_ids UUID[],
    is_active BOOLEAN NOT NULL DEFAULT true,
    priority INT NOT NULL DEFAULT 0,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at TIMESTAMPTZ,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_world_events_active ON world_events(is_active, starts_at, ends_at);
CREATE INDEX idx_world_events_type ON world_events(event_type);
```

---

### 4.10 기존 테이블 캐릭터 페이지 관련 컬럼 추가

#### personas 추가 컬럼 (캐릭터 페이지)

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| follower_count | INT | NOT NULL, DEFAULT 0 | 팔로워 수 |
| is_character_page_enabled | BOOLEAN | DEFAULT false | 캐릭터 페이지 활성화 여부 |

#### persona_lounge_configs 추가 컬럼

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| auto_publish | BOOLEAN | NOT NULL, DEFAULT true | 자동 퍼블리싱 (false=승인 큐) |

#### board_posts 추가 컬럼

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| publish_status | VARCHAR(20) | DEFAULT 'published', CHECK | 'pending' \| 'published' \| 'rejected' |

#### notifications type 확장

`'character_chat'`, `'world_event'`, `'follow'` 추가.
CHECK: `type IN ('persona_approved','persona_blocked','reply','system','relationship','credit','character_chat','world_event','follow')`

#### credit_costs action 확장

`'character_chat'`, `'character_page_post'` 추가.

---

## 6. 설계 근거 및 특이사항

### 6.1 PII 최소화

| 항목 | 처리 방식 |
|---|---|
| 이메일 | SHA-256 해시만 저장 (`users.email_hash`) |
| 채팅 내용 | Presidio 마스킹 후 저장 (`chat_messages.content`) |
| 댓글 원문 | 저장 금지, 집계 통계만 (`comment_stats`) |
| 동의 로그 | TTL 관리 (`consent_logs.expires_at`), 목적 달성 후 파기 |

### 6.2 pgvector 활용

- **episode_embeddings:** 회차 요약/이벤트/감정 설명을 청크 단위로 벡터화, HNSW 인덱스로 코사인 유사도 검색
- **lorebook_entries:** 사용자 정의 세계관 설정을 벡터화하여 대화 시 유사한 설정을 동적 검색 후 프롬프트에 삽입
- **벡터 차원:** BGE-M3 기준 1024차원
- **인덱싱:** HNSW (`vector_cosine_ops`) - 프로토타입 규모에서 충분한 성능

### 6.3 역할 기반 접근 통제 (RBAC)

- `users.role`: 'user', 'admin', 또는 'superadmin'. 백엔드 미들웨어에서 역할 체크
- 관리자 전용 API (`/api/admin/*`): `role='admin'` 또는 `role='superadmin'` 접근 가능
- 파괴적 작업(사용자 삭제, 역할 변경, 모델 등록, 시스템 설정): `role='superadmin'`만 접근 가능
- 사용자는 자신이 생성한 리소스(페르소나, 로어북, 세션)에만 접근 가능

### 6.4 사용자 페르소나 생성

- `personas.created_by`: 생성자 연결. null이면 시스템 생성
- `personas.type`: 'system'(관리자) 또는 'user_created'(사용자)
- `personas.visibility`: 'private'(본인만), 'public'(전체 공개), 'unlisted'(링크 공유)
- `personas.moderation_status`: 공개 페르소나는 관리자 검토 후 승인 필요
- `personas.safety_rules`: 시스템 기본 안전 규칙을 반드시 상속, 사용자가 완화 불가

### 6.5 로어북 소유권

- `lorebook_entries.created_by`: 생성자 추적
- `lorebook_entries.persona_id` + `webtoon_id`: 페르소나 전용, 웹툰 전용, 또는 양쪽 모두 가능
- CHECK 제약으로 최소 하나는 연결 필수
- 사용자는 자신이 만든 로어북 항목만 편집/삭제 가능

### 6.6 Live2D 연동

- `live2d_models`: Live2D 모델 에셋 메타데이터 관리
- `live2d_models.emotion_mappings`: 감정 라벨 → Live2D 모션/표정 매핑 (JSONB)
- `personas.live2d_model_id`: 페르소나당 Live2D 모델 1개 선택
- `personas.background_image_url`: 연애 시뮬레이션 스타일 배경 이미지
- `chat_messages.emotion_signal`: 메시지별 감정 태깅 → Live2D 모션 트리거

### 6.7 성인인증 및 연령등급 콘텐츠

- `users.adult_verified_at`: 성인인증 완료 시각. null이면 미인증
- `users.age_group`: 'adult_verified'는 adult_verified_at이 NOT NULL일 때만 설정
- `personas.age_rating`: 'all' \| '15+' \| '18+'. 18+ 페르소나는 adult_verified만 생성/사용 가능
- `llm_models.is_adult_only`: 성인전용 모델은 adult_verified만 사용 가능
- 게이트는 API 미들웨어에서 강제 (프롬프트 의존 금지)
- consent_logs에 age_verify 이력 기록

### 6.8 LLM 모델 관리

- `llm_models`: 관리자가 사용 가능한 모델을 등록하고 단가를 설정
- `users.preferred_llm_model_id`: 사용자 기본 선호 모델
- `chat_sessions.llm_model_id`: 세션 시작 시 선택한 모델로 고정
- `llm_models.provider` 기반으로 inference_client가 API 분기 처리
- 모델 비활성화 시 해당 모델을 사용 중인 세션은 기본 모델로 폴백

### 6.9 토큰 사용량 추적

- `token_usage_logs`: 모든 LLM 호출을 요청 단위로 기록
- `cost`는 호출 시점의 `llm_models` 단가 기반으로 즉시 산출
- 인덱스를 통해 사용자별/모델별/세션별 집계 쿼리 최적화
- Redis에 일/월 사용량 캐시하여 실시간 조회 지원
- 사용량 할당(usage_quotas): 일/월 토큰 및 비용 한도 구현 완료
- 크레딧 시스템(credit_ledger, credit_costs): 대화석 경제 구현 완료

### 6.10 정책 상태 관리

- `spoiler_settings`: 작품별 스포일러 범위를 DB에서 관리 (프롬프트 의존 금지)
- `chat_messages.policy_snapshot`: 메시지 생성 시점의 정책 상태를 JSONB로 스냅샷 기록 (감사 추적용)
- `users.age_group`: 연령 인증 상태에 따라 콘텐츠 필터링 게이트 적용

### 6.11 프리컴퓨트 전략

- `review_cache`: 스포일러 모드별 리뷰를 배치로 미리 생성하여 저장
- 런타임에는 캐시된 리뷰에 사용자 페르소나 톤만 덧입히는 짧은 생성으로 지연 최소화
- `expires_at`으로 캐시 갱신 주기 관리

### 6.12 장기 기억

- `user_memories`: MemGPT 스타일 계층형 메모리 (core/preference/fact)
- `namespace/key` 구조로 LangGraph 호환 (JSON 문서 저장)
- 페르소나 자산과 완전 분리하여 사용자 상태로 관리

### 6.13 세션 요약

- `chat_sessions.summary_text`: ChatSummaryMemoryBuffer 패턴 적용
- 토큰 한계 초과 시 과거 대화를 단일 요약으로 축약하여 저장
- LLM 프롬프트 컴파일 시 "세션 요약 + 최근 N턴" 조합으로 컨텍스트 구성

---

## 7. 확장 고려사항

프로토타입에서 성장 단계로 전환 시:

| 항목 | 현재 (프로토타입) | 확장 시 |
|---|---|---|
| 벡터 DB | pgvector (PostgreSQL 내장) | Milvus/Weaviate 분리 |
| 캐싱 | Redis (EC2 내부 Docker) | Redis Cluster 또는 ElastiCache |
| 메시지 큐 | 없음 (직접 호출) | Redis Streams 또는 SQS |
| 파티셔닝 | 없음 | chat_messages를 created_at 기준 월별 파티셔닝 |
| 읽기 복제 | 없음 | PostgreSQL Streaming Replication |
| 감사 로그 | policy_snapshot (JSONB) | 별도 audit_logs 테이블 분리 |
| Live2D 에셋 | 로컬 파일 (public/assets/) | S3 + CloudFront CDN |
| 페르소나 검색 | DB 직접 조회 | Elasticsearch (공개 페르소나 검색) |
| 모더레이션 | 관리자 수동 검토 | 자동 분류기 + 관리자 검토 |
| 사용량 집계 | token_usage_logs 직접 쿼리 + Redis 캐시 | 일/월 집계 테이블 (user_usage_summary) 또는 Materialized View |
| 과금 시스템 | usage_quotas + credit_ledger + subscription_plans | invoices (청구서) + 결제 연동 |
| LLM 모델 | 관리자 수동 등록 | 모델 자동 디스커버리 + 벤치마크 점수 |

---

## 8. 마이그레이션 이력

총 15개 마이그레이션. Alembic 기반 순차 적용.

| # | 리비전 ID | 파일명 | 설명 |
|---|---|---|---|
| 1 | a3b4fcc66da6 | `a3b4fcc66da6_initial_schema.py` | 초기 스키마 생성 (도메인 1~3, 17개 테이블) |
| 2 | b1c2d3e4f5a6 | `b1c2d3e4f5a6_add_usage_quotas.py` | 사용량 할당 (usage_quotas) 테이블 추가 |
| 3 | c2d3e4f5a6b7 | `c2d3e4f5a6b7_add_credits_subscriptions.py` | 크레딧/구독 시스템 (subscription_plans, user_subscriptions, credit_ledger, credit_costs) |
| 4 | d3e4f5a6b7c8 | `d3e4f5a6b7c8_add_community_board.py` | 커뮤니티 게시판 (boards, board_posts, board_comments, board_reactions) |
| 5 | e4f5a6b7c8d9 | `e4f5a6b7c8d9_add_agent_system.py` | 에이전트 시스템 (persona_lounge_configs, agent_activity_logs) |
| 6 | f5a6b7c8d9e0 | `f5a6b7c8d9e0_add_rp_features.py` | RP 기능 DB 확장 (4개 신규 테이블, 기존 3개 테이블 컬럼 추가) |
| 7 | a1b2c3d4e5f6 | `a1b2c3d4e5f6_add_deleted_session_status.py` | chat_sessions.status CHECK에 'deleted' 추가 |
| 8 | b2c3d4e5f6a7 | `b2c3d4e5f6a7_add_persona_category.py` | 페르소나 카테고리 컬럼 추가 (personas.category VARCHAR(30) + idx_personas_category) |
| 9 | c3d4e5f6a7b8 | `c3d4e5f6a7b8_add_persona_anonymous.py` | 페르소나 익명 설정 추가 |
| 10 | d4e5f6a7b8c9 | `d4e5f6a7b8c9_add_llm_model_credit_fields.py` | LLM 모델 크레딧 필드 추가 |
| 11 | e5f6a7b8c9d0 | `e5f6a7b8c9d0_add_video_generations.py` | 비디오 생성 테이블 추가 |
| 12 | f6a7b8c9d0e1 | `f6a7b8c9d0e1_add_persona_reports.py` | 페르소나 신고 시스템 추가 |
| 13 | g7b8c9d0e1f2 | `g7b8c9d0e1f2_add_banned_until.py` | 사용자 임시 차단(banned_until) 추가 |
| 14 | h8c9d0e1f2g3 | `h8c9d0e1f2g3_add_character_page_system.py` | 캐릭터 페이지 시스템 (pending_posts, character_chat_sessions, character_chat_messages, world_events) |
| 15 | i9d0e1f2g3h4 | `i9d0e1f2g3h4_add_character_page_credit_costs.py` | 캐릭터 페이지 크레딧 비용 매핑 추가 |
