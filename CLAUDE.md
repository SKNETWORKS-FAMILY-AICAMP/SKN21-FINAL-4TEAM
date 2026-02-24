# CLAUDE.md

## Project Overview

웹툰 리뷰 챗봇 프로토타입 — 사용자가 직접 페르소나(캐릭터)를 생성하고, Live2D 캐릭터와 연애 시뮬레이션 스타일로 대화하며 웹툰 회차별 리뷰/감정 분석을 제공받는 AI 챗봇 서비스.

- **단계:** 프로토타입 (동시 접속 10명 이하)
- **아키텍처:** 하이브리드 스플릿 브레인 — EC2 서울(제어) + RunPod US Serverless(GPU 추론)
- **월 예상 비용:** ~$130 (EC2 ~$15 + RunPod ~$114) + LLM API 비용 (사용량 비례)

### 핵심 특징

- **사용자 페르소나 생성:** 사용자가 캐릭터 성격, 말투, 로어북(세계관 설정)을 직접 정의하고 적용
- **Live2D 챗 UI:** 배경 이미지 위에 Live2D 캐릭터가 감정에 따라 실시간 반응 (연애 시뮬레이션 스타일)
- **성인 인증 & 연령등급 콘텐츠:** 성인 인증 후 18+ 페르소나/챗봇 이용 가능, UI에 전연령/나이제한 배지 표시
- **LLM 모델 전환:** 사용자가 기호에 따라 LLM 모델을 선택/전환 가능
- **토큰 사용량 추적:** 사용자별 LLM 토큰 사용량 실시간 추적 및 비용 산출
- **역할 분리:** 사용자(채팅/페르소나 생성)와 관리자(대시보드/모더레이션)의 접근 화면이 다름
- **관리자 대시보드:** 사용자/세션/페르소나 관리, 정책 설정, 사용량/과금 모니터링을 위한 별도 관리 화면
- **캐릭터 페이지 시스템:** 인스타그램 스타일 캐릭터 프로필, 팔로우, 게시물 피드, 캐릭터 간 1:1 대화
- **세계관 이벤트:** 관리자 정의 세계관 이벤트가 프롬프트 Layer 1.5로 주입되어 캐릭터 반응에 영향

## Architecture

```
┌─ 사용자 화면 ──────────────────────────────────────────────────┐
│  [Chat UI]    Live2D + 배경 + SSE 스트리밍 + 연령등급 배지      │
│  [Creator]    페르소나 생성/편집 + 로어북 + 연령등급 설정        │
│  [Settings]   LLM 모델 선택 + 사용량 확인 + 성인인증            │
└───────────────────────┬────────────────────────────────────────┘
                        │
┌─ 관리자 화면 ──────────┼────────────────────────────────────────┐
│  [Dashboard]  사용자/세션/페르소나 관리 + 정책 설정              │
│  [Billing]    토큰 사용량 통계 + 과금 현황                      │
│  [Monitor]    Langfuse/Prometheus 연동 + 로그 조회              │
│  [Models]     LLM 모델 관리 (활성/비활성, 비용 설정)            │
└───────────────────────┼────────────────────────────────────────┘
                        │ HTTPS + SSE
┌───────────────────────▼────────────────────────────────────────┐
│  EC2 t4g.small (서울)                                           │
│  ┌─ FastAPI ────────────────────────────────────────────────┐  │
│  │  /api/chat/*      채팅 SSE (사용자)                       │  │
│  │  /api/personas/*  페르소나/로어북 CRUD (사용자)            │  │
│  │  /api/models/*    LLM 모델 목록/선택 (사용자)             │  │
│  │  /api/usage/*     내 토큰 사용량 조회 (사용자)            │  │
│  │  /api/auth/*      성인인증 (사용자)                       │  │
│  │  /api/admin/*     관리 API (관리자 전용, RBAC)            │  │
│  │  /api/character-pages/*  캐릭터 페이지 (사용자)           │  │
│  │  /api/character-chats/*  캐릭터 1:1 대화 (사용자)         │  │
│  │  /api/pending-posts/*    승인 큐 (사용자)                 │  │
│  │  /api/world-events/*     세계관 이벤트 관리 (관리자)      │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌─ PostgreSQL + pgvector ──┐  ┌─ Redis ────────────────────┐  │
│  │  36개 테이블              │  │  세션/캐시                  │  │
│  └──────────────────────────┘  └────────────────────────────┘  │
└───────────────────────┬────────────────────────────────────────┘
                        │ HTTP (RTT ~150ms)
┌───────────────────────▼────────────────────────────────────────┐
│  RunPod Serverless (미국) / 외부 LLM API                        │
│  ┌─ 모델 라우터 ────────────────────────────────────────────┐  │
│  │  llm_models 테이블 기반 동적 라우팅                       │  │
│  │  RunPod SGLang (Llama 3 70B) ← 기본                      │  │
│  │  OpenAI API (GPT-4o) ← 선택                              │  │
│  │  Anthropic API (Claude) ← 선택                           │  │
│  │  Google API (Gemini) ← 선택                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

**3층 구조:**
1. 정책/권한 계층 — 스포일러, 연령, 동의, 성인인증을 DB 상태 머신으로 관리 (프롬프트 의존 금지)
2. 근거 데이터 계층 — 회차 요약, 감정 신호, 댓글 통계를 구조화 저장
3. 생성 계층 — 사용자 선택 LLM이 근거 번들 + 사용자 정의 페르소나 기반으로 리뷰 생성, 토큰 사용량 기록

## Tech Stack

| 역할 | 기술 |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Frontend | Next.js 15 + React 19 + Zustand |
| Live2D | pixi-live2d-display + PixiJS (Cubism SDK 연동) |
| Database | PostgreSQL 16 + pgvector (Docker) |
| Cache | Redis (Docker) |
| LLM Inference | RunPod Serverless + SGLang (기본) + 외부 API (OpenAI/Anthropic/Google 등) |
| Streaming | SSE (Server-Sent Events) |
| Sentiment | KcELECTRA (KOTE 43감정 파인튜닝) |
| Embedding | BGE-M3 (1024차원) |
| Reranker | bge-reranker-v2-m3 |
| Korean NLP | Kiwi (kiwipiepy) — Mecab은 Windows 미지원 |
| PII | Presidio |
| Observability | Langfuse + Prometheus + Grafana + Sentry |
| Infra | AWS EC2 t4g.small (서울) + RunPod Serverless (미국) |
| Container | Docker Compose |
| Local Dev GPU | RTX 5060 8GB, CUDA 12.8, PyTorch 2.7+ |

## User Roles & Access Control

| 역할 | 접근 범위 | 주요 기능 |
|---|---|---|
| **user** | 채팅 UI, 페르소나 생성/편집, 로어북 관리, 내 세션/사용량 조회, 커뮤니티, 크레딧/구독, 캐릭터 페이지, 캐릭터 채팅, 승인 큐 | 대화, 캐릭터 커스터마이징, 스포일러 설정, LLM 모델 선택, 성인인증, 캐릭터 팔로우, 1:1 대화 요청 |
| **admin** | 관리자 대시보드 + 사용자 화면 전체 (읽기 위주) | 사용자 조회, 페르소나 모더레이션, 모니터링, 콘텐츠/게시판 관리, 세계관 이벤트 관리, 승인 큐 관리 |
| **superadmin** | admin 전체 + 파괴적 작업 | 사용자 삭제/역할 변경, LLM 모델 등록/수정, 정책 수정, 시스템 설정, 크레딧 지급, 할당 설정, 세계관 이벤트 CRUD |

### 사용자 화면

- **채팅 화면:** Live2D 캐릭터 + 배경 이미지 + 대화 창 (연애 시뮬레이션 레이아웃) + 연령등급 배지
- **페르소나 생성/편집:** 캐릭터 이름, 성격, 말투, 시스템 프롬프트, Live2D 모델 선택, 배경 이미지, 연령등급 설정
- **로어북 관리:** 페르소나별/웹툰별 세계관 설정 항목 CRUD (제목, 본문, 태그)
- **내 세션 목록:** 진행 중인 대화 세션 관리
- **LLM 모델 선택:** 사용 가능한 모델 목록 + 비용 안내 + 모델 전환
- **사용량 확인:** 토큰 사용량 대시보드 (일별/월별, 모델별, 비용 추이)
- **성인인증:** 본인인증 → adult_verified 상태 전환 → 18+ 콘텐츠 접근
- **캐릭터 페이지:** 인스타 스타일 캐릭터 프로필 + 게시물 피드 + 팔로우/언팔로우
- **캐릭터 채팅:** 캐릭터 간 1:1 대화 요청/수락/턴제 대화
- **승인 큐:** 수동 퍼블리싱 대기 게시물 승인/반려

### 관리자 대시보드

- **사용자 관리:** 사용자 목록, 역할 변경, 계정 상태 관리, 성인인증 현황
- **페르소나 모더레이션:** 사용자 생성 페르소나 검토/승인/차단, 연령등급 검수, 시스템 페르소나 관리
- **정책 설정:** 연령등급 기준, 안전 규칙 기본값, 금칙어 관리
- **콘텐츠 관리:** 웹툰/회차 데이터 CRUD, Live2D 모델/배경 에셋 관리
- **LLM 모델 관리:** 모델 등록/비활성화, 비용 단가 설정, 성인전용 모델 지정
- **사용량/과금:** 전체 토큰 사용량 통계, 사용자별 사용량, 모델별 비용 분석
- **모니터링:** Langfuse 트레이싱 뷰어, 세션/메시지 통계, 정책 위반 로그
- **시스템 설정:** RunPod 엔드포인트, 모델 설정, 캐시 관리
- **세계관 이벤트 관리:** 세계관 이벤트 CRUD, 프롬프트 Layer 1.5 주입 관리
- **승인 큐 관리:** 대기 중인 게시물 승인/반려

## Adult Content & Age Verification

### 성인인증 흐름

```
사용자 가입 (age_group: 'unverified')
         │
         ▼
  성인인증 요청 (/api/auth/adult-verify)
         │
         ├─ 본인인증 (휴대폰/카드/SSO) → 성공 시:
         │     users.age_group = 'adult_verified'
         │     users.adult_verified_at = now()
         │     consent_logs에 기록
         │
         └─ 미인증 유지 → age_group: 'minor_safe' 또는 'unverified'
                            18+ 콘텐츠 접근 차단
```

### 연령등급 콘텐츠 게이트

| 사용자 상태 | 전연령(all) 콘텐츠 | 15+ 콘텐츠 | 18+ 콘텐츠 |
|---|:---:|:---:|:---:|
| unverified | O | X | X |
| minor_safe | O | O | X |
| adult_verified | O | O | O |

### UI 연령등급 배지

- 페르소나 목록/카드에 연령등급 배지 표시 (버튼형)
  - `[전체]` — 초록색 배지
  - `[15+]` — 노란색 배지
  - `[18+]` — 빨간색 배지 (adult_verified가 아니면 흐리게 표시 + 잠금 아이콘)
- 채팅 화면 상단에 현재 페르소나의 연령등급 배지 상시 표시
- 18+ 페르소나 선택 시 성인인증 미완료면 인증 유도 모달 표시

### 백엔드 게이트 로직

- 모든 채팅/페르소나 접근 API에서 `age_rating` vs `user.age_group` 교차 검증
- 18+ 페르소나: `adult_verified`만 접근 가능
- 18+ 페르소나 생성: `adult_verified`만 생성 가능
- 게이트는 프롬프트가 아닌 **API 미들웨어**에서 강제

## LLM Model Management

### 모델 라우팅 구조

```
사용자 요청 → inference_client.py
               │
               ├─ user.preferred_llm_model_id 또는 session.llm_model_id 확인
               │
               ├─ llm_models 테이블에서 provider/model_id/endpoint 조회
               │
               ├─ provider별 분기:
               │   ├─ 'runpod'    → RunPod Serverless API (SGLang)
               │   ├─ 'openai'    → OpenAI API
               │   ├─ 'anthropic' → Anthropic API
               │   └─ 'google'    → Google Gemini API
               │
               └─ 응답 + 토큰 수 → token_usage_logs에 기록
```

### llm_models 테이블 주요 필드

| 필드 | 설명 |
|---|---|
| provider | 'runpod' \| 'openai' \| 'anthropic' \| 'google' 등 |
| model_id | API에서 사용하는 모델 식별자 (예: 'gpt-4o', 'claude-sonnet-4-5-20250929') |
| display_name | UI에 표시할 모델 이름 |
| input_cost_per_1m | 입력 100만 토큰당 비용 ($) |
| output_cost_per_1m | 출력 100만 토큰당 비용 ($) |
| max_context_length | 최대 컨텍스트 길이 (토큰) |
| is_adult_only | 성인전용 모델 여부 (true면 adult_verified만 사용 가능) |
| is_active | 관리자가 활성/비활성 전환 |

### 사용자 모델 선택

- 기본값: 관리자가 설정한 기본 모델 (예: RunPod Llama 3 70B)
- 사용자가 설정에서 preferred_llm_model_id 변경 가능
- 세션 시작 시 선택한 모델로 고정 (세션 중간 변경은 새 세션 생성)
- 모델별 비용 차이를 UI에 명확히 안내

## Token Usage & Billing

### 사용량 추적 흐름

```
LLM API 호출 완료
      │
      ▼
token_usage_logs INSERT:
  - user_id, session_id, llm_model_id
  - input_tokens, output_tokens
  - cost = (input_tokens * input_cost / 1M) + (output_tokens * output_cost / 1M)
  - created_at
      │
      ▼
Redis 캐시 갱신: user:{id}:daily_usage, user:{id}:monthly_usage
```

### 사용량 조회 API

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/usage/me` | 내 사용량 요약 (일/월/총계, 모델별) |
| `GET /api/usage/me/history` | 일별 사용량 히스토리 (차트용) |
| `GET /api/admin/usage/summary` | 전체 사용자 사용량 통계 (관리자) |
| `GET /api/admin/usage/users/{id}` | 특정 사용자 상세 사용량 (관리자) |

### 크레딧(대화석) & 사용량 할당

- **크레딧 시스템:** 대화석 경제 구현 완료. 일일 무료 크레딧 지급 + 유료 구매/구독 플랜
- **사용량 할당(Quota):** 일일/월간 토큰 한도 + 월간 비용 한도. 초과 시 429 반환
- **구독 플랜:** subscription_plans 테이블 기반 무료/프리미엄 플랜 관리
- **거래 내역:** credit_ledger에 모든 크레딧 변동 기록 (충전, 사용, 환불, 관리자 지급)

## Project Structure

```
Project_New/
├── CLAUDE.md
├── docker-compose.yml
├── .env.example                     # 환경변수 템플릿
├── docs/
│   ├── AI 챗봇 플랫폼 기술 스택 및 비용 분석.md
│   ├── EC2_RunPod 프로토타입 구현 최적화 방안.md
│   ├── 챗봇 설계 보고서.md
│   ├── ERD 설계서.md
│   ├── 설치 가이드.md
│   ├── 개발자 가이드.md
│   ├── 디렉토리 구조 가이드.md
│   ├── 화면 시나리오 문서.md
│   ├── 캐릭터 라운지 및 크레딧 시스템 설계서.md
│   ├── 프로젝트 현황 및 남은 작업.md
│   └── 테스트 시나리오.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── auth.py              # 인증/회원가입/성인인증
│   │   │   ├── chat.py              # 채팅 SSE 엔드포인트
│   │   │   ├── personas.py          # 페르소나 CRUD (사용자용)
│   │   │   ├── lorebook.py          # 로어북 CRUD (사용자용)
│   │   │   ├── webtoons.py          # 웹툰/회차 조회
│   │   │   ├── policy.py            # 스포일러/연령/동의 관리
│   │   │   ├── models.py            # LLM 모델 목록/선택 (사용자용)
│   │   │   ├── usage.py             # 내 토큰 사용량 조회
│   │   │   ├── user_personas.py     # 사용자 페르소나 CRUD
│   │   │   ├── favorites.py         # 즐겨찾기
│   │   │   ├── relationships.py     # 호감도/관계
│   │   │   ├── notifications.py     # 알림
│   │   │   ├── character_cards.py   # 캐릭터 카드 Import/Export
│   │   │   ├── memories.py          # 메모리 대시보드
│   │   │   ├── credits.py           # 크레딧 잔액/거래/구매
│   │   │   ├── subscriptions.py     # 구독 관리
│   │   │   ├── board.py             # 커뮤니티 게시판
│   │   │   ├── lounge.py            # 캐릭터 라운지
│   │   │   ├── character_pages.py   # 캐릭터 페이지
│   │   │   ├── character_chats.py   # 캐릭터 간 1:1 대화
│   │   │   ├── pending_posts.py     # 승인 큐
│   │   │   ├── world_events.py      # 세계관 이벤트
│   │   │   ├── uploads.py           # 파일 업로드
│   │   │   ├── image_gen.py         # AI 이미지 생성
│   │   │   ├── tts.py               # TTS
│   │   │   ├── health.py
│   │   │   └── admin/               # 관리자 전용 API (16개 라우터)
│   │   │       ├── users.py         # 사용자 관리
│   │   │       ├── personas.py      # 페르소나 모더레이션
│   │   │       ├── content.py       # 웹툰/에셋 관리
│   │   │       ├── policy.py        # 정책 설정
│   │   │       ├── llm_models.py    # LLM 모델 관리
│   │   │       ├── usage.py         # 전체 사용량/과금 통계
│   │   │       ├── monitoring.py    # 통계/로그 조회
│   │   │       ├── system.py        # 시스템 설정
│   │   │       ├── credits.py       # 크레딧 관리
│   │   │       ├── subscriptions.py # 구독 관리
│   │   │       ├── board.py         # 게시판 모더레이션
│   │   │       ├── agents.py        # 에이전트 관리
│   │   │       ├── reports.py       # 신고 관리
│   │   │       ├── video_gen.py     # 비디오 생성 관리
│   │   │       └── world_events.py  # 세계관 이벤트 관리
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py          # SQLAlchemy + pgvector
│   │   │   ├── redis.py
│   │   │   ├── auth.py              # 인증 + RBAC + 성인인증 미들웨어
│   │   │   ├── deps.py              # FastAPI 의존성 (현재 사용자, 역할 체크, 연령 게이트)
│   │   │   ├── observability.py     # Langfuse + Sentry + Prometheus
│   │   │   └── rate_limit.py        # Redis 슬라이딩 윈도우 레이트 리미터
│   │   ├── models/                  # SQLAlchemy ORM 모델 (39개)
│   │   ├── schemas/                 # Pydantic 스키마
│   │   ├── services/
│   │   │   ├── chat_service.py
│   │   │   ├── persona_service.py   # 페르소나 생성/편집 + 연령등급 검증
│   │   │   ├── lorebook_service.py  # 로어북 CRUD + 임베딩
│   │   │   ├── policy_service.py
│   │   │   ├── review_service.py
│   │   │   ├── rag_service.py
│   │   │   ├── moderation_service.py
│   │   │   ├── inference_client.py  # LLM 모델 라우터 (provider별 분기)
│   │   │   ├── usage_service.py     # 토큰 사용량 기록/집계
│   │   │   ├── adult_verify_service.py # 성인인증 처리
│   │   │   ├── user_service.py      # 사용자 CRUD
│   │   │   ├── quota_service.py     # 사용량 한도 검증
│   │   │   ├── batch_scheduler.py   # 배치 작업 스케줄러
│   │   │   ├── user_persona_service.py
│   │   │   ├── favorite_service.py
│   │   │   ├── relationship_service.py
│   │   │   ├── notification_service.py
│   │   │   ├── character_card_service.py
│   │   │   ├── credit_service.py    # 크레딧 차감/충전/잔액
│   │   │   ├── subscription_service.py # 구독 관리
│   │   │   ├── board_service.py     # 게시판 CRUD
│   │   │   ├── tts_service.py         # TTS 스텁
│   │   │   ├── image_gen_service.py   # 이미지 생성 스텁
│   │   │   ├── agent_scheduler.py   # 에이전트 스케줄러
│   │   │   ├── agent_activity_service.py # 에이전트 활동 로그
│   │   │   ├── character_page_service.py  # 캐릭터 페이지
│   │   │   ├── character_chat_service.py  # 캐릭터 간 1:1 대화
│   │   │   ├── pending_post_service.py    # 승인 큐
│   │   │   ├── world_event_service.py     # 세계관 이벤트
│   │   │   ├── report_service.py          # 신고 관리
│   │   │   └── video_gen_service.py       # 비디오 생성
│   │   ├── pipeline/
│   │   │   ├── emotion.py
│   │   │   ├── embedding.py
│   │   │   ├── reranker.py
│   │   │   ├── pii.py
│   │   │   ├── korean_nlp.py
│   │   │   └── batch.py             # 배치 함수
│   │   └── prompt/
│   │       ├── compiler.py
│   │       └── persona_loader.py
│   ├── tests/
│   ├── alembic/                     # 15개 마이그레이션
│   ├── requirements.txt             # 프로덕션 의존성
│   └── requirements-dev.txt         # 개발/테스트 의존성
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (user)/
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── chat/[sessionId]/page.tsx
│   │   │   │   ├── personas/page.tsx         # 홈 — 퀵 액세스 카드 + 챗봇 탐색
│   │   │   │   ├── personas/create/page.tsx
│   │   │   │   ├── personas/[id]/edit/page.tsx
│   │   │   │   ├── personas/[id]/lorebook/page.tsx
│   │   │   │   ├── sessions/page.tsx
│   │   │   │   ├── favorites/page.tsx       # 즐겨찾기
│   │   │   │   ├── relationships/page.tsx   # 관계도
│   │   │   │   ├── notifications/page.tsx   # 알림
│   │   │   │   ├── mypage/page.tsx           # 마이페이지 (7탭)
│   │   │   │   ├── community/page.tsx        # 캐릭터 라운지
│   │   │   │   ├── community/post/[id]/page.tsx
│   │   │   │   ├── character/[id]/page.tsx  # 캐릭터 페이지
│   │   │   │   ├── character-chats/page.tsx # 캐릭터 간 1:1 대화
│   │   │   │   ├── pending-posts/page.tsx   # 승인 큐
│   │   │   │   └── usage/page.tsx           # 사용량 대시보드
│   │   │   ├── admin/
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx
│   │   │   │   ├── users/page.tsx
│   │   │   │   ├── personas/page.tsx
│   │   │   │   ├── content/page.tsx
│   │   │   │   ├── policy/page.tsx
│   │   │   │   ├── models/page.tsx           # LLM 모델 관리
│   │   │   │   ├── usage/page.tsx            # 전체 사용량/과금
│   │   │   │   ├── monitoring/page.tsx
│   │   │   │   ├── reports/page.tsx          # 신고 관리
│   │   │   │   ├── video-gen/page.tsx        # 비디오 생성 관리
│   │   │   │   └── world-events/page.tsx     # 세계관 이벤트 관리
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── UserSidebar.tsx           # 사용자 네비게이션
│   │   │   │   ├── ErrorBoundary.tsx         # 에러 경계
│   │   │   │   └── NotificationBell.tsx      # 알림 벨
│   │   │   ├── chat/
│   │   │   │   ├── ChatWindow.tsx
│   │   │   │   ├── MessageInput.tsx
│   │   │   │   ├── SpoilerGate.tsx
│   │   │   │   ├── MessageActions.tsx        # 메시지 재생성/수정/복사
│   │   │   │   └── RelationshipBar.tsx       # 호감도 바
│   │   │   ├── live2d/                       # Live2DCanvas, Live2DController, BackgroundLayer
│   │   │   ├── persona/
│   │   │   │   ├── PersonaForm.tsx
│   │   │   │   ├── LorebookEditor.tsx
│   │   │   │   ├── Live2DPicker.tsx
│   │   │   │   ├── AgeRatingBadge.tsx
│   │   │   │   └── TagChips.tsx              # 태그 칩
│   │   │   ├── character/                     # CharacterPageHeader, FollowButton, CharacterPostFeed, CharacterChatRoom, PendingPostCard, WorldEventBanner
│   │   │   ├── auth/                         # AdultVerifyModal, AgeGateModal
│   │   │   ├── mypage/
│   │   │   │   ├── ProfileTab.tsx
│   │   │   │   ├── SettingsTab.tsx
│   │   │   │   ├── UsageTab.tsx
│   │   │   │   ├── SubscriptionTab.tsx
│   │   │   │   ├── UserPersonaTab.tsx
│   │   │   │   ├── MemoriesTab.tsx
│   │   │   │   └── CreatorTab.tsx
│   │   │   ├── community/                    # PostCard, PostEditor, CommentTree, ReactionButton 등
│   │   │   ├── credits/
│   │   │   │   ├── CreditBadge.tsx
│   │   │   │   └── PurchaseModal.tsx
│   │   │   ├── subscription/                 # SubscriptionCard
│   │   │   ├── usage/                        # UsageChart, ModelCostCard
│   │   │   ├── ui/                           # Toast, Skeleton, EmptyState, ConfirmDialog
│   │   │   └── admin/                        # Sidebar, DataTable, StatCard, UserDetailDrawer
│   │   ├── stores/
│   │   │   ├── chatStore.ts
│   │   │   ├── personaStore.ts
│   │   │   ├── live2dStore.ts
│   │   │   ├── userStore.ts              # 사용자 상태 (인증, 모델 선택, 사용량)
│   │   │   ├── toastStore.ts             # 토스트 알림
│   │   │   ├── communityStore.ts         # 커뮤니티 데이터
│   │   │   ├── creditStore.ts            # 크레딧 잔액
│   │   │   ├── notificationStore.ts      # 알림 상태
│   │   │   ├── characterPageStore.ts     # 캐릭터 페이지 상태
│   │   │   ├── characterChatStore.ts     # 캐릭터 간 대화 상태
│   │   │   ├── pendingPostStore.ts       # 승인 큐 상태
│   │   │   └── worldEventStore.ts        # 세계관 이벤트 상태
│   │   └── lib/
│   │       ├── api.ts
│   │       ├── sse.ts
│   │       └── auth.ts
│   ├── public/
│   │   └── assets/
│   │       ├── live2d/
│   │       └── backgrounds/
│   ├── package.json
│   └── next.config.js
└── infra/
    ├── docker/
    │   ├── Dockerfile.backend
    │   └── Dockerfile.frontend
    ├── nginx/
    │   └── nginx.conf
    └── runpod/
        └── handler.py
```

## Database

- **엔진:** PostgreSQL 16 + pgvector
- **호스팅:** EC2 내부 Docker 컨테이너 (RDS 사용하지 않음)
- **테이블:** 36개 (ERD 설계서 참조)
  - 정책/사용자 (8): users, consent_logs, spoiler_settings, user_personas, notifications, persona_favorites, persona_relationships, usage_quotas
  - 근거 데이터 (7): webtoons, episodes, episode_emotions, episode_embeddings, comment_stats, lorebook_entries, review_cache
  - 대화/생성 (5): personas, live2d_models, chat_sessions, chat_messages, user_memories
  - LLM/과금 (3): llm_models, token_usage_logs, credit_ledger
  - 크레딧/구독 (4): subscription_plans, user_subscriptions, credit_costs, credit_ledger
  - 커뮤니티/에이전트 (11): boards, board_posts, board_comments, board_reactions, persona_lounge_configs, agent_activity_logs, pending_posts, character_chat_sessions, character_chat_messages, world_events
- **ORM:** SQLAlchemy 2.0 (async)
- **마이그레이션:** Alembic
- **벡터 인덱스:** HNSW (vector_cosine_ops), BGE-M3 1024차원
- **백업:** pg_dump → S3, 크론잡

### 핵심 변경점 (이전 버전 대비)

- `users` — `role` 추가, `adult_verified_at` 추가, `preferred_llm_model_id` 추가
- `personas` — `created_by`, `type`, `visibility`, `moderation_status`, `age_rating`, `live2d_model_id`, `background_image_url`, `category` 추가
- `lorebook_entries` — `persona_id`, `created_by` 추가. webtoon_id NULLABLE로 변경
- `live2d_models` — 신규. Live2D 모델 에셋 + 감정→모션 매핑
- `llm_models` — 신규. LLM 모델 메타데이터 + 비용 단가
- `token_usage_logs` — 신규. 요청별 토큰 사용량 + 비용 기록
- `chat_sessions` — `llm_model_id` 추가 (세션에서 사용 중인 모델)
- `users` — `password_hash`, `credit_balance`, `last_credit_grant_at`, `preferred_themes` 추가. role CHECK에 'superadmin' 추가
- `personas` — `description`, `greeting_message`, `scenario`, `example_dialogues`, `tags`, `chat_count`, `like_count` 추가
- `chat_sessions` — `title`, `is_pinned`, `user_persona_id` (FK → user_personas) 추가
- `chat_messages` — `parent_id` (self FK, 분기용), `is_active`, `is_edited`, `edited_at` 추가
- `user_personas` — 신규. 사용자 페르소나 (대화에서 사용자의 캐릭터)
- `persona_favorites` — 신규. 페르소나 즐겨찾기
- `persona_relationships` — 신규. 호감도/관계 단계 (stranger→soulmate)
- `notifications` — 신규. 사용자 알림
- `usage_quotas` — 신규. 사용자별 일/월 토큰 및 비용 한도
- `subscription_plans` — 신규. 구독 플랜 (무료/프리미엄)
- `user_subscriptions` — 신규. 사용자 구독 상태
- `credit_ledger` — 신규. 크레딧 거래 내역
- `credit_costs` — 신규. 모델/액션별 크레딧 비용 매핑
- `boards` — 신규. 커뮤니티 게시판
- `board_posts` — 신규. 게시글 (사용자/AI 작성)
- `board_comments` — 신규. 댓글 (대댓글 지원)
- `board_reactions` — 신규. 이모지 리액션
- `persona_lounge_configs` — 신규. 라운지 페르소나 활동 설정
- `agent_activity_logs` — 신규. AI 에이전트 활동 로그
- `pending_posts` — 신규. AI 생성 게시물 수동 퍼블리싱 승인 큐
- `character_chat_sessions` — 신규. 캐릭터 간 1:1 대화 세션 (요청/수락/턴제)
- `character_chat_messages` — 신규. 캐릭터 간 대화 메시지
- `world_events` — 신규. 관리자 정의 세계관 이벤트 (프롬프트 Layer 1.5)
- `personas` — `follower_count`, `is_character_page_enabled` 추가 (캐릭터 페이지)
- `persona_lounge_configs` — `auto_publish` 추가 (승인 큐 연동)
- `board_posts` — `publish_status` 추가 (pending/published/rejected)
- `notifications` — type CHECK에 `character_chat`, `world_event`, `follow` 추가
- `credit_costs` — action에 `character_chat`, `character_page_post` 추가

## Coding Conventions

### Python (Backend)

- Python 3.12+
- 비동기 우선: `async/await` 패턴 사용 (FastAPI + SQLAlchemy async)
- 타입 힌트 필수
- Pydantic v2 모델로 입출력 검증
- 포매터: ruff (format + lint)
- 네이밍: snake_case (변수/함수), PascalCase (클래스)
- import 순서: stdlib → third-party → local
- RBAC: 관리자 API는 `Depends(require_admin)` 또는 `Depends(require_superadmin)` 의존성 적용. 파괴적 작업은 superadmin 필수
- 연령 게이트: 18+ 콘텐츠 접근 API는 `Depends(require_adult_verified)` 적용

### TypeScript (Frontend)

- TypeScript strict 모드
- 함수형 컴포넌트 + React 19 Server Components 우선
- 포매터: Prettier + ESLint
- 네이밍: camelCase (변수/함수), PascalCase (컴포넌트)
- 라우팅: Next.js App Router, route group으로 사용자/관리자 분리

### SQL

- 테이블/컬럼: snake_case
- PK: `id` (UUID 또는 BIGINT IDENTITY)
- FK: `{참조테이블_단수}_id`
- 인덱스: `idx_{테이블}_{컬럼}` 패턴
- TIMESTAMPTZ 사용 (TIME ZONE 포함)
- CHECK 제약조건으로 enum 대체

### Git

- 커밋 메시지: Conventional Commits (feat/fix/refactor/docs/chore)
- 브랜치: `feature/`, `fix/`, `refactor/` 접두사

## Testing

### 테스트 전략

| 레벨 | 도구 | 대상 | 커버리지 목표 |
|---|---|---|---|
| Unit | pytest + pytest-asyncio | 서비스 로직, 유틸, 파이프라인 | 핵심 비즈니스 로직 80%+ |
| Integration | pytest + httpx (AsyncClient) | API 엔드포인트, DB 연동 | 모든 API 엔드포인트 |
| E2E (Frontend) | Playwright | 사용자 플로우, 관리자 플로우 | 핵심 시나리오 (채팅, 페르소나 생성, 성인인증) |
| Component | Vitest + React Testing Library | React 컴포넌트 단위 | 상태 변화가 있는 컴포넌트 |

### Python 테스트 규칙

- **프레임워크:** pytest (pytest-asyncio, pytest-cov)
- **위치:** `backend/tests/` — 소스 구조를 미러링
  ```
  backend/tests/
  ├── conftest.py              # 공통 fixture (DB, Redis, 테스트 유저)
  ├── unit/
  │   ├── services/            # 서비스 단위 테스트
  │   ├── pipeline/            # NLP 파이프라인 테스트
  │   └── prompt/              # 프롬프트 컴파일러 테스트
  ├── integration/
  │   ├── api/                 # API 엔드포인트 통합 테스트
  │   └── db/                  # DB 연동 테스트
  └── fixtures/                # 테스트 데이터 (JSON, mock)
  ```
- **네이밍:** 파일 `test_*.py`, 함수 `test_동작_조건_기대결과` 패턴
  ```python
  # Good
  async def test_create_persona_returns_201_when_valid_input():
  async def test_chat_blocks_18plus_when_user_not_verified():

  # Bad
  async def test_persona():
  async def test1():
  ```
- **fixture 활용:** DB 세션, 테스트 유저(일반/관리자/성인인증), 테스트 페르소나 등은 `conftest.py`에 정의
- **mock 원칙:** 외부 의존성(RunPod API, 외부 LLM API)만 mock. 내부 서비스 간 호출은 실제 로직 사용
- **비동기 테스트:** `@pytest.mark.asyncio` 데코레이터 사용, async fixture는 `@pytest_asyncio.fixture`
- **DB 격리:** 테스트마다 트랜잭션 롤백으로 격리, 테스트 간 상태 공유 금지

### Frontend 테스트 규칙

- **컴포넌트 테스트:** Vitest + React Testing Library
- **E2E:** Playwright (크로스 브라우저)
- **위치:** `frontend/src/__tests__/` 또는 컴포넌트 옆 `*.test.tsx`
- **네이밍:** `describe('컴포넌트명')` + `it('should 동작 설명')`
- **mock:** API 호출은 MSW(Mock Service Worker)로 mock

### 정책 검증 테스트 (필수)

아래 시나리오는 반드시 테스트가 존재해야 하며, CI에서 통과하지 않으면 머지 불가:

- 미성년 사용자가 18+ 페르소나에 접근 → 403
- 성인인증 미완료 사용자가 18+ 페르소나 생성 → 403
- 스포일러 범위 밖 사건 언급 요청 → 정책 위반 감지
- 차단된(blocked) 페르소나로 채팅 시도 → 403
- 타인의 private 페르소나 접근 → 403
- 관리자 API에 일반 사용자 접근 → 403
- PII가 포함된 입력 → 마스킹 처리 확인
- 토큰 사용량 기록 누락 없음 확인

### 테스트 실행

**반드시 Python 가상환경(venv)을 활성화한 후 테스트를 실행한다.** 시스템 Python(3.10 등)으로 실행하면 `datetime.UTC` 등 Python 3.12+ 전용 API에서 ImportError가 발생한다.

```bash
# 가상환경 활성화 (Windows)
backend/.venv/Scripts/activate

# 가상환경 활성화 (Linux/Mac)
source backend/.venv/bin/activate

# 백엔드 전체 테스트
pytest backend/tests/ -v --cov=app --cov-report=term-missing

# 단위 테스트만
pytest backend/tests/unit/ -v

# 통합 테스트만
pytest backend/tests/integration/ -v

# 프론트엔드 컴포넌트 테스트
cd frontend && npx vitest run

# E2E 테스트
cd frontend && npx playwright test
```

## Comments & Documentation

### 주석 원칙

**"왜(Why)"를 쓰고, "무엇(What)"은 코드로 말하게 한다.**

- 자명한 코드에는 주석을 달지 않는다
- 비즈니스 규칙, 정책 근거, 비직관적인 결정에만 주석을 단다
- 주석이 필요한 코드 = 리팩토링을 먼저 고려

### Python 주석 규칙

```python
# Good — "왜" 이런 결정을 했는지
# 청소년유해매체물 제공 시 본인확인 의무 (청소년보호법 시행령)
if persona.age_rating == "18+" and not user.adult_verified_at:
    raise HTTPException(status_code=403)

# Good — 비직관적인 로직 설명
# RadixAttention 캐시 히트를 위해 시스템 프롬프트를 대화 히스토리 앞에 고정
prompt = build_prefix(persona) + history + user_input

# Bad — 코드가 이미 말하고 있는 것을 반복
# 사용자 ID를 가져온다
user_id = request.user.id

# Bad — 변경 이력 (git이 담당)
# 2026-02-10: 토큰 추적 추가
```

- **docstring:** 공개 API(라우터 함수, 서비스 클래스)에만 작성. 내부 헬퍼는 함수명으로 충분하면 생략
  ```python
  async def create_persona(data: PersonaCreate, user: User) -> Persona:
      """사용자 페르소나 생성. 18+ 등급은 성인인증 필수."""
  ```
- **TODO 규칙:** `# TODO(이름): 설명 — #이슈번호` 형식. 이슈 없는 TODO 금지
  ```python
  # TODO(작성자): 과금 한도 로직 추가 — #42
  ```
- **타입 힌트가 docstring을 대체:** 파라미터 타입과 반환 타입은 타입 힌트로 표현, docstring에 중복 기술하지 않음

### TypeScript 주석 규칙

```typescript
// Good — 비직관적인 UX 결정
// SSE 연결이 끊어져도 3초간 재연결 시도 후 에러 표시 (UX 팀 요청)
const RECONNECT_DELAY = 3000;

// Good — 외부 라이브러리 제약
// pixi-live2d-display는 PixiJS v7만 지원, v8 업그레이드 시 호환성 확인 필요
import { Live2DModel } from 'pixi-live2d-display';

// Bad
// 상태를 설정한다
setState(newState);
```

- **JSDoc:** 공유 유틸(`lib/`)과 커스텀 훅에만 작성. 컴포넌트는 Props 타입이 문서 역할
- **TODO:** `// TODO(이름): 설명 — #이슈번호`

### SQL 주석 규칙

- 마이그레이션 파일에 변경 사유를 주석으로 남긴다
- DDL 내 CHECK 제약조건 옆에 허용 값 나열 (ERD 설계서와 동기화)
- 복잡한 쿼리(JOIN 3개 이상, 서브쿼리)에는 의도를 주석으로 남긴다

## Code Consistency

### 프로젝트 전반 규칙

| 항목 | 규칙 |
|---|---|
| 들여쓰기 | Python: 4 spaces / TypeScript: 2 spaces / SQL: 4 spaces |
| 줄 길이 | Python: 120자 / TypeScript: 100자 |
| 줄바꿈 | LF (Unix-style). `.gitattributes`로 강제 |
| 인코딩 | UTF-8 (BOM 없음) |
| 파일 끝 | 항상 빈 줄 1개로 종료 |
| trailing whitespace | 금지 (포매터가 자동 제거) |

### Python 일관성

- **포매터/린터:** ruff (format + lint) — 저장 시 자동 실행
  ```toml
  # pyproject.toml
  [tool.ruff]
  line-length = 120
  target-version = "py312"

  [tool.ruff.lint]
  select = ["E", "F", "I", "N", "UP", "B", "SIM", "ASYNC"]
  ```
- **import 정렬:** ruff가 isort 호환으로 자동 정렬. stdlib → third-party → local 순서 강제
- **문자열:** 큰따옴표(`"`) 통일. f-string 우선, `.format()` 사용 금지
- **예외 처리:** 맨손 `except:` 금지. 구체적 예외 타입 명시
  ```python
  # Good
  except httpx.HTTPStatusError as e:

  # Bad
  except Exception:
  except:
  ```
- **비동기 일관성:** DB/Redis/HTTP 호출은 반드시 `async`. sync 함수에서 `asyncio.run()` 호출 금지
- **환경 변수:** `core/config.py`의 Pydantic `BaseSettings`로 중앙 관리. 코드 내 `os.getenv()` 직접 호출 금지

### TypeScript 일관성

- **포매터/린터:** Prettier (포맷) + ESLint (린트) — 저장 시 자동 실행
  ```json
  // .prettierrc
  {
    "semi": true,
    "singleQuote": true,
    "tabWidth": 2,
    "printWidth": 100,
    "trailingComma": "all"
  }
  ```
- **import 정렬:** ESLint `import/order` 규칙. react → next → third-party → @/ → ./ 순서
- **컴포넌트 구조:** 한 파일에 한 컴포넌트. 파일명 = 컴포넌트명 (PascalCase)
- **Props 타입:** 인라인 `type` 정의. `interface`는 외부 공유 시에만 사용
  ```typescript
  // Good — 컴포넌트 로컬
  type Props = { personaId: string; onClose: () => void };
  export function PersonaForm({ personaId, onClose }: Props) { ... }

  // interface는 lib/에서 공유할 때
  export interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; }
  ```
- **상태 관리:** Zustand 스토어는 `stores/` 디렉토리에 도메인별 분리. 컴포넌트 내 전역 상태 직접 정의 금지
- **API 호출:** `lib/api.ts`의 래퍼 함수를 통해서만 호출. 컴포넌트에서 `fetch` 직접 호출 금지

### 파일/디렉토리 네이밍

| 대상 | Python | TypeScript |
|---|---|---|
| 파일 | snake_case.py | PascalCase.tsx (컴포넌트) / camelCase.ts (유틸) |
| 디렉토리 | snake_case/ | camelCase/ 또는 kebab-case/ (Next.js 라우트) |
| 테스트 파일 | test_원본명.py | 원본명.test.tsx |
| 상수 파일 | constants.py | constants.ts |
| 타입 파일 | (타입 힌트 인라인) | types.ts (도메인별 공유 타입) |

### 에러 처리 일관성

- **백엔드:** FastAPI `HTTPException`으로 통일. 커스텀 에러는 `core/exceptions.py`에 정의
  ```python
  # 일관된 에러 응답 형식
  {"detail": "설명", "error_code": "PERSONA_BLOCKED"}
  ```
- **프론트엔드:** `lib/api.ts`에서 에러를 catch → 표준 에러 객체로 변환 → 컴포넌트에서 처리
  ```typescript
  // lib/api.ts
  class ApiError extends Error {
    constructor(public status: number, public code: string, message: string) {
      super(message);
    }
  }
  ```
- **에러 코드 체계:** `DOMAIN_ACTION` 형식 (예: `AUTH_ADULT_REQUIRED`, `PERSONA_BLOCKED`, `USAGE_LIMIT_EXCEEDED`)

### 커밋 전 체크리스트 (자동화)

```bash
# pre-commit hook (또는 CI)
ruff check backend/        # Python 린트
ruff format --check backend/ # Python 포맷
pytest backend/tests/ -x    # 테스트 (첫 실패 시 중단)
cd frontend && npx eslint . # TS 린트
cd frontend && npx prettier --check . # TS 포맷
cd frontend && npx vitest run # 컴포넌트 테스트
```

## Key Design Principles

### 보안/법률 우선 원칙

1. **PII 최소화** — 원문 저장 금지, 해시/마스킹 후 저장, Presidio 3중 방어
2. **정책은 코드로** — 스포일러/연령/동의를 프롬프트가 아닌 DB 상태 머신 + 코드 게이트로 강제
3. **원문 보관 금지** — 댓글 원문, 웹툰 대사/이미지 저장 금지. 파생만 보관
4. **개인정보 파기** — consent_logs에 expires_at 관리, 목적 달성 후 지체 없이 파기
5. **연령등급 게이트** — age_group + personas.age_rating 교차 검증. 18+ 콘텐츠는 API 미들웨어에서 차단
6. **성인인증 법령 준수** — 청소년유해매체물 제공 시 본인확인 의무 (시행령 기반)
7. **간접 프롬프트 인젝션 방어** — RAG 근거 번들은 비신뢰 데이터로 태깅
8. **RBAC 강제** — 관리자 API는 역할 기반 접근 통제, 사용자는 자신의 리소스만 접근

### 아키텍처 원칙

1. **정책/근거/생성 3층 분리** — 정책 상태는 모델 컨텍스트와 분리
2. **프리컴퓨트 우선** — 리뷰/감정 분석은 배치로 미리 생성, 런타임 LLM 호출 최소화
3. **구조화 신호 → LLM 서술** — 감정은 분류기로 구조화, LLM은 해석/서술만 담당
4. **근거 번들 강제** — LLM은 번들 밖 사실 생성 금지, confidence 낮으면 단정 금지
5. **graceful degradation** — 과부하 시 품질을 낮추되 정책 검증은 절대 스킵 금지
6. **사용자/관리자 화면 분리** — Next.js route group으로 분리, 백엔드는 RBAC 미들웨어로 분리
7. **LLM 추상화** — inference_client가 provider별 분기 처리, 모델 추가 시 코드 변경 최소화
8. **사용량 기록 필수** — 모든 LLM 호출은 token_usage_logs에 기록 (비용 산출 근거)

### 사용자 생성 콘텐츠 원칙

1. **페르소나 소유권** — 사용자가 만든 페르소나는 본인 소유, 공개/비공개 선택 가능
2. **안전 규칙 상속** — 사용자 페르소나도 시스템 안전 규칙을 반드시 상속
3. **연령등급 자기 설정** — 사용자가 페르소나 생성 시 연령등급 설정, 18+는 adult_verified만 가능
4. **로어북 자유도** — 사용자가 페르소나별/웹툰별 로어북 항목을 자유롭게 정의
5. **모더레이션** — 관리자가 공개 페르소나를 검토/승인/차단 가능

### 프롬프트 레이어 순서

1. 불변 정책 (스포일러/연령/PII/저작권 안전) — 시스템 강제
1.5. 세계관 이벤트 — [World Event] 블록 (관리자 정의, global/board/persona 타입)
2. 사용자 정의 페르소나 (캐릭터 성격/말투/시스템 프롬프트 + scenario)
2.3. 관계 상태 — [Relationship] 블록 (호감도/단계)
2.5. 사용자 페르소나 — [User Character] 블록
2.7. 예시 대화 — example_dialogues few-shot
3. 사용자 정의 로어북 (페르소나별 + 웹툰별 세계관 설정)
3.5. 사용자 기억 — [User Memories] 블록
4. 세션 요약 + 최근 대화 (is_active=True 필터)
5. 근거 번들 (검색 결과 + 감정 신호)

## Live2D Integration

### 화면 레이아웃 (연애 시뮬레이션 스타일)

```
┌──────────────────────────────────────┐
│  [전체] 또는 [15+] 또는 [18+]  배지   │  ← 연령등급 배지
│          배경 이미지 레이어            │
│  ┌──────────────────────────────┐    │
│  │                              │    │
│  │      Live2D 캐릭터 모델       │    │
│  │    (감정에 따라 모션 변화)     │    │
│  │                              │    │
│  └──────────────────────────────┘    │
│                                      │
│  ┌──────────────────────────────┐    │
│  │   대화 텍스트 오버레이         │    │
│  │   (SSE 스트리밍 + 타자기 효과) │    │
│  └──────────────────────────────┘    │
│  ┌──────────────────────────────┐    │
│  │   사용자 입력 창              │    │
│  └──────────────────────────────┘    │
└──────────────────────────────────────┘
```

### 기술 구성

- **렌더링:** PixiJS + pixi-live2d-display (Cubism SDK 4 연동)
- **모델 포맷:** Cubism 4 (.model3.json, .moc3, .physics3.json 등)
- **감정→모션 매핑:** `live2d_models.emotion_mappings` JSONB에 정의
- **배경:** 페르소나별 `background_image_url`로 설정
- **에셋 관리:** `public/assets/live2d/`에 저장, 관리자가 업로드/관리

## Persona System

### 사용자가 정의할 수 있는 항목

| 항목 | 설명 | 저장 위치 |
|---|---|---|
| 캐릭터 이름 | 페르소나 표시 이름 | personas.display_name |
| 성격/설정 | 자유 텍스트 시스템 프롬프트 | personas.system_prompt |
| 말투 규칙 | 존댓말/반말, 말버릇, 이모티콘 사용 등 | personas.style_rules (JSONB) |
| 리뷰 템플릿 | 리뷰 구조 커스터마이징 | personas.review_template (JSONB) |
| 캐치프레이즈 | 자주 쓰는 표현 풀 | personas.catchphrases (TEXT[]) |
| Live2D 모델 | 사용할 캐릭터 모델 선택 | personas.live2d_model_id |
| 배경 이미지 | 채팅 화면 배경 | personas.background_image_url |
| 연령등급 | 'all' \| '15+' \| '18+' | personas.age_rating |
| 공개 범위 | private / public / unlisted | personas.visibility |
| 카테고리 | 8개 카테고리 중 선택 (선택사항) | personas.category |
| 로어북 | 세계관/캐릭터 설정 항목들 | lorebook_entries |

### 페르소나 타입 & 연령등급

- **system:** 관리자가 생성한 기본 페르소나. 전체 사용자에게 제공.
- **user_created:** 사용자가 직접 생성. 본인만 사용(private) 또는 공개(public/unlisted) 선택.
- **연령등급 'all':** 모든 사용자 사용 가능
- **연령등급 '15+':** minor_safe 또는 adult_verified 사용 가능
- **연령등급 '18+':** adult_verified만 생성/사용 가능
- **카테고리:** romance, action, fantasy, daily, horror, comedy, drama, scifi — 회원가입 시 preferred_themes와 연결

## RunPod Integration

- **엔진:** SGLang (RadixAttention 활성화, DISABLE_RADIX_CACHE=false)
- **기본 모델:** Llama 3 70B (4-bit 양자화)
- **GPU:** A100 80GB
- **과금:** 초 단위 (Serverless)
- **콜드스타트:** FlashBoot 활성화 (~2초 기동)
- **네트워크:** 서울↔미국 RTT ~150ms, SSE 스트리밍으로 체감 지연 상쇄
- **Function Calling:** 주사위 등 게임 로직은 EC2에서 처리 후 결과를 LLM 재입력
- **멀티 모델:** llm_models 테이블 기반 동적 라우팅, RunPod 외 외부 API도 지원

## Performance Targets

| 요청 유형 | p50 목표 | p95 목표 |
|---|---:|---:|
| 설정/상태 확인 | 0.1–0.3s | ≤ 0.8s |
| 작품 추천/탐색 | 0.5–1.5s | ≤ 3s |
| 회차 리뷰 생성 | 2–4s | 6–10s |
| 감정 시계열 분석 | 1–3s | 5–8s |
| 페르소나 CRUD | 0.1–0.5s | ≤ 1s |
| 관리자 대시보드 조회 | 0.3–1s | ≤ 2s |
| 사용량 조회 | 0.1–0.5s | ≤ 1s |

## Reference Documents

- `docs/아키텍처 문서.md` — 시스템 아키텍처, 데이터 흐름, 보안, DB, 배포 구조 + 하이브리드 아키텍처 설계 근거
- `docs/챗봇 설계 보고서.md` — 챗봇 상세 설계 (정책, 감정 파이프라인, 보안, 페르소나)
- `docs/ERD 설계서.md` — 36개 테이블 DDL 및 설계 근거
- `docs/성능 최적화 전략.md` — 백엔드/프론트엔드/인프라 성능 최적화 전략 종합
- `docs/설치 가이드.md` — 설치 및 실행 가이드 + 프로젝트 디렉토리 구조
- `docs/개발자 가이드.md` — 개발 환경/패턴/레시피
- `docs/테스트 시나리오.md` — 화면별 172개 테스트 시나리오
- `docs/화면별 시나리오.md` — 29개 라우트별 API 매핑
- `docs/캐릭터 라운지 및 크레딧 시스템 설계서.md` — 라운지/크레딧/구독 설계
- `docs/프로젝트 현황 및 남은 작업.md` — 현재 진행 상태
- `docs/한국어 RP 로컬 모델 비교 분석.md` — LLM 모델 선택/비교
- `docs/RunPod Serverless LTX-Video-2 세팅 가이드.md` — 비디오 생성 모델 셋업
