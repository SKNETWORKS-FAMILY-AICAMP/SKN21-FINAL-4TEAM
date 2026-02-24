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

## Project Structure

```
Project_New/
├── CLAUDE.md                        # 프로젝트 개요/아키텍처 (이 파일)
├── backend/CLAUDE.md                # 백엔드 컨벤션/DB/기능 명세
├── frontend/CLAUDE.md               # 프론트엔드 컨벤션/컴포넌트 규칙
├── docker-compose.yml
├── docker-compose.prod.yml
├── deploy.sh                        # EC2 배포 스크립트 (/opt/chatbot, SSH key: ~/Downloads/chatbot-key.pem)
├── .env.example
├── docs/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                     # 라우터 (auth, chat, personas, lorebook 등 + admin/)
│   │   ├── core/                    # config, database, redis, auth, deps, observability
│   │   ├── models/                  # SQLAlchemy ORM (39개)
│   │   ├── schemas/                 # Pydantic 스키마
│   │   ├── services/                # 비즈니스 로직
│   │   ├── pipeline/                # emotion, embedding, reranker, pii, korean_nlp
│   │   └── prompt/                  # compiler, persona_loader
│   ├── tests/
│   ├── alembic/                     # 마이그레이션
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (user)/              # 사용자 라우트 그룹
│   │   │   ├── admin/               # 관리자 라우트 그룹
│   │   │   └── api/[...path]/       # Next.js → FastAPI SSE 프록시
│   │   ├── components/
│   │   ├── stores/                  # Zustand 스토어
│   │   └── lib/                     # api.ts, sse.ts, auth.ts
│   └── public/assets/
└── infra/
    ├── docker/
    ├── nginx/                       # nginx.conf (dev), nginx.http.conf (prod)
    └── runpod/
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

### Git 규칙

- 커밋 메시지: Conventional Commits (feat/fix/refactor/docs/chore)
- 브랜치: `feature/`, `fix/`, `refactor/` 접두사

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

## Deployment (EC2)

| 항목 | 값 |
|---|---|
| **EC2 퍼블릭 IP** | `54.180.202.169` (Elastic IP 없음 — 재시작 시 변경) |
| **리전** | ap-northeast-2 (서울) |
| **인스턴스** | t4g.small |
| **SSH 키** | `~/Downloads/chatbot-key.pem` |
| **배포 경로** | `/opt/chatbot` |
| **OS 사용자** | `ubuntu` |

### 배포 명령

```bash
# 코드 업데이트 배포 (일반적인 경우)
ssh -i ~/Downloads/chatbot-key.pem ubuntu@54.180.202.169 \
  "cd /opt/chatbot && git pull && bash deploy.sh update"

# 최초 배포 (서버 초기 세팅)
ssh -i ~/Downloads/chatbot-key.pem ubuntu@54.180.202.169 \
  "cd /opt/chatbot && sudo bash deploy.sh"

# 서비스 상태 확인
ssh -i ~/Downloads/chatbot-key.pem ubuntu@54.180.202.169 \
  "cd /opt/chatbot && docker compose -f docker-compose.prod.yml ps"

# 백엔드 로그 실시간 확인
ssh -i ~/Downloads/chatbot-key.pem ubuntu@54.180.202.169 \
  "cd /opt/chatbot && docker compose -f docker-compose.prod.yml logs -f backend"
```

## Reference Documents

- `docs/아키텍처 문서.md` — 시스템 아키텍처, 데이터 흐름, 보안, DB, 배포 구조
- `docs/챗봇 설계 보고서.md` — 챗봇 상세 설계 (정책, 감정 파이프라인, 보안, 페르소나)
- `docs/ERD 설계서.md` — 36개 테이블 DDL 및 설계 근거
- `docs/설치 가이드.md` — 설치 및 실행 가이드
- `docs/개발자 가이드.md` — 개발 환경/패턴/레시피
- `docs/테스트 시나리오.md` — 화면별 172개 테스트 시나리오
- `docs/캐릭터 라운지 및 크레딧 시스템 설계서.md` — 라운지/크레딧/구독 설계
- `docs/프로젝트 현황 및 남은 작업.md` — 현재 진행 상태
