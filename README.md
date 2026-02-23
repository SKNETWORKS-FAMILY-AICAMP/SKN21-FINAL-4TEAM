# 웹툰 리뷰 챗봇

> AI 캐릭터와 대화하며 웹툰 리뷰를 즐기는 Live2D 챗봇 플랫폼

## 프로젝트 소개

웹툰 리뷰 챗봇은 사용자가 직접 페르소나(캐릭터)를 생성하고, Live2D 캐릭터와 연애 시뮬레이션 스타일로 대화하며 웹툰 회차별 리뷰/감정 분석을 제공받는 AI 챗봇 서비스입니다.

사용자는 캐릭터의 성격, 말투, 세계관을 자유롭게 정의하고, 다양한 LLM 모델(Llama 3, GPT-4o, Claude, Gemini)을 선택하여 대화할 수 있습니다. 관리자는 대시보드를 통해 사용자/콘텐츠/정책을 관리하며, 세계관 이벤트로 캐릭터 반응을 제어할 수 있습니다.

- **단계:** 프로토타입 (동시 접속 10명 이하)
- **아키텍처:** 하이브리드 스플릿 브레인 — EC2 서울(제어) + RunPod US Serverless(GPU 추론)

## 주요 기능

### 사용자 기능

- **Live2D 챗 UI** — 배경 이미지 위 Live2D 캐릭터가 감정에 따라 실시간 반응 (연애 시뮬레이션 스타일)
- **페르소나 생성/편집** — 캐릭터 성격, 말투, 시스템 프롬프트, 로어북(세계관 설정) 직접 정의
- **캐릭터 페이지** — 인스타그램 스타일 프로필, 팔로우, 게시물 피드
- **캐릭터 간 1:1 대화** — 요청/수락/턴제 대화, LLM 기반 AI 응답
- **커뮤니티** — 게시판, 댓글, 리액션, AI 에이전트 자동 활동
- **크레딧/구독** — 대화석 경제, 일일 무료 크레딧, 유료 구독 플랜
- **LLM 모델 선택** — 4개 프로바이더(RunPod/OpenAI/Anthropic/Google) 중 선택
- **호감도/관계** — 7단계 관계 시스템 (stranger → soulmate)
- **성인인증** — 18+ 콘텐츠 연령등급 게이트

### 관리자 기능

- **대시보드** — 사용자/세션/페르소나 관리, 정책 설정
- **세계관 이벤트** — 프롬프트 Layer 1.5로 주입, 캐릭터 반응 제어
- **콘텐츠 모더레이션** — 페르소나 검토/승인/차단, 승인 큐 관리
- **LLM 모델 관리** — 모델 등록/비활성화, 비용 단가 설정
- **사용량/과금** — 토큰 사용량 통계, 모델별 비용 분석
- **모니터링** — Langfuse 트레이싱, Prometheus + Grafana 대시보드

## 기술 스택

| 역할 | 기술 |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Frontend | Next.js 15 + React 19 + Zustand + Tailwind CSS |
| Live2D | pixi-live2d-display + PixiJS (Cubism SDK 4) |
| Database | PostgreSQL 16 + pgvector (Docker) |
| Cache | Redis 7 (Docker) |
| LLM Inference | RunPod Serverless (SGLang) + OpenAI/Anthropic/Google API |
| Streaming | SSE (Server-Sent Events) |
| Sentiment | KcELECTRA (KOTE 43감정) |
| Embedding | BGE-M3 (1024차원) |
| Korean NLP | Kiwi (kiwipiepy) |
| Observability | Langfuse + Prometheus + Grafana + Sentry |
| Infra | AWS EC2 t4g.small (서울) + RunPod Serverless (미국) |
| Container | Docker Compose |

## 아키텍처

```
┌─ 프론트엔드 (Next.js 15) ─────────────────────────────────────┐
│  Tailwind CSS + Dynamic Import + React.memo                    │
│  Live2D (PixiJS + pixi-live2d-display + Cubism 4)             │
│  SSE (POST + Authorization header + ReadableStream)            │
└───────────────────────┬────────────────────────────────────────┘
                        │ HTTPS + SSE
┌───────────────────────▼────────────────────────────────────────┐
│  EC2 t4g.small (서울)                                           │
│  ┌─ FastAPI ────────────────────────────────────────────────┐  │
│  │  143개 API 엔드포인트 (사용자 107 + 관리자 36)              │  │
│  │  Rate Limiting (Redis 슬라이딩 윈도우)                    │  │
│  │  Usage Quota (일일/월간 토큰+비용 한도)                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌─ PostgreSQL + pgvector ──┐  ┌─ Redis ────────────────────┐  │
│  │  36개 테이블              │  │  세션/캐시/Rate Limit      │  │
│  └──────────────────────────┘  └────────────────────────────┘  │
│  ┌─ 관측성 ─────────────────────────────────────────────────┐  │
│  │  Prometheus → Grafana │ Langfuse │ Sentry                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────┬────────────────────────────────────────┘
                        │ HTTP (RTT ~150ms)
┌───────────────────────▼────────────────────────────────────────┐
│  RunPod Serverless (미국) / 외부 LLM API                        │
│  RunPod SGLang (Llama 3 70B) │ OpenAI │ Anthropic │ Google     │
└────────────────────────────────────────────────────────────────┘
```

**3층 구조:**
1. **정책/권한 계층** — 스포일러, 연령, 동의, 성인인증을 DB 상태 머신으로 관리
2. **근거 데이터 계층** — 회차 요약, 감정 신호, 댓글 통계를 구조화 저장
3. **생성 계층** — LLM이 근거 번들 + 사용자 정의 페르소나 기반으로 리뷰 생성

## 빠른 시작

### 1. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 실제 값 입력 (최소 LLM API 키 1개 필요)
```

### 2. Docker 서비스 구동

```bash
# DB + Redis
docker-compose up -d db redis

# 관측성 포함
docker-compose up -d db redis prometheus grafana langfuse
```

### 3. 백엔드 실행

```bash
cd backend
pip install -r requirements-dev.txt
alembic upgrade head          # 36개 테이블 생성 (15개 마이그레이션)
uvicorn app.main:app --reload --port 8000
```

### 4. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev                   # http://localhost:3000
```

## 프로젝트 구조

```
Project_New/
├── backend/
│   ├── app/
│   │   ├── api/              # API 라우터 (사용자 27 + 관리자 16)
│   │   ├── core/             # 설정, 인증, DB, Redis, Rate Limit
│   │   ├── models/           # SQLAlchemy ORM 모델 (39개)
│   │   ├── schemas/          # Pydantic 스키마 (24개)
│   │   ├── services/         # 비즈니스 로직 (31개)
│   │   ├── pipeline/         # NLP 파이프라인 (감정/임베딩/PII/NLP/리랭커)
│   │   └── prompt/           # 프롬프트 컴파일러
│   ├── tests/                # pytest (단위 + 통합)
│   └── alembic/              # 15개 마이그레이션
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router (29개 페이지)
│   │   ├── components/       # React 컴포넌트 (57개)
│   │   ├── stores/           # Zustand 스토어 (13개)
│   │   └── lib/              # API 클라이언트, SSE, 인증
│   └── e2e/                  # Playwright E2E 테스트
├── infra/                    # Docker, Nginx, RunPod
├── docs/                     # 프로젝트 문서
└── docker-compose.yml
```

## 테스트

```bash
# 백엔드 전체 테스트
pytest backend/tests/ -v --cov=app --cov-report=term-missing

# 백엔드 단위 테스트만
pytest backend/tests/unit/ -v

# 백엔드 통합 테스트만
pytest backend/tests/integration/ -v

# 프론트엔드 컴포넌트 테스트
cd frontend && npx vitest run

# TypeScript 타입 체크
cd frontend && npx tsc --noEmit

# E2E 테스트 (Playwright)
cd frontend && npx playwright test

# 프로덕션 빌드 검증
cd frontend && npx next build
```

## 문서

| 문서 | 설명 |
|---|---|
| [CLAUDE.md](./CLAUDE.md) | 프로젝트 가이드 (아키텍처, 규칙, 컨벤션) |
| [ERD 설계서](./docs/ERD%20설계서.md) | 36개 테이블 DDL 및 설계 근거 |
| [설치 가이드](./docs/설치%20가이드.md) | 설치 및 실행 가이드 |
| [개발자 가이드](./docs/개발자%20가이드.md) | 개발 환경, 패턴, 레시피 |
| [화면별 시나리오](./docs/화면별%20시나리오.md) | 29개 라우트별 API 매핑 |
| [테스트 시나리오](./docs/테스트%20시나리오.md) | 172개 화면별 테스트 시나리오 |
| [프로젝트 현황](./docs/프로젝트%20현황%20및%20남은%20작업.md) | 현재 진행 상태 및 남은 작업 |
| [아키텍처 문서](./docs/아키텍처%20문서.md) | 시스템 아키텍처, 데이터 흐름, 보안 |
| [성능 최적화 전략](./docs/성능%20최적화%20전략.md) | 백엔드/프론트엔드/인프라 최적화 |
| [캐릭터 라운지 설계서](./docs/캐릭터%20라운지%20및%20크레딧%20시스템%20설계서.md) | 라운지/크레딧/구독 설계 |

## 라이선스

이 프로젝트는 비공개 프로토타입입니다.
