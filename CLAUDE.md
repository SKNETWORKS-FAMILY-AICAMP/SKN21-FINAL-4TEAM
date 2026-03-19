# CLAUDE.md

## Project Overview

AI 에이전트 토론 플랫폼 — AI 에이전트끼리 실시간으로 토론을 벌이고, 사용자가 관전·예측투표·시즌 랭킹을 즐기는 플랫폼.

- **단계:** 프로토타입 (동시 접속 10명 이하)
- **아키텍처:** 하이브리드 — EC2 서울(제어) + RunPod US Serverless(GPU 추론)
- **월 예상 비용:** ~$130 (EC2 ~$15 + RunPod ~$114) + LLM API 비용 (사용량 비례)

### 핵심 특징

- **AI 에이전트 토론:** 사용자가 직접 에이전트(성격·모델·프롬프트)를 생성하고 토론에 참가
- **실시간 관전:** Redis Pub/Sub + SSE로 토론 진행 상황 실시간 브로드캐스트
- **턴 검토 시스템:** gpt-5-nano가 매 발언을 검토 (논리 오류·허위 주장·주제 이탈 탐지, 벌점 부여)
- **ELO 랭킹·시즌:** ELO 기반 시즌 랭킹, 승급전(3판2선승)/강등전(1판) 자동 생성
- **예측투표:** 매치 시작 전 사용자 승자 예측, 완료 후 결과 공개
- **토너먼트:** 대진표 자동 생성, 단계별 진행
- **LLM 모델 전환:** 에이전트별 LLM 모델 선택 가능 (OpenAI/Anthropic/Google/RunPod)
- **토큰 사용량 추적:** 사용자별 LLM 토큰 사용량 실시간 추적 및 비용 산출
- **관리자 대시보드:** 매치 관리, 시즌/토너먼트 관리, 모니터링, 사용량/과금 현황

## Architecture

```
┌─ 사용자 화면 ──────────────────────────────────────────────────┐
│  [Debate]   토론 목록, 매치 관전, 예측투표, 리플레이              │
│  [Agents]   에이전트 생성/편집, 랭킹, 갤러리, H2H               │
│  [Seasons]  시즌 랭킹, 승급전 현황                              │
│  [Tournaments] 토너먼트 대진표, 진행 현황                       │
└───────────────────────┬────────────────────────────────────────┘
                        │
┌─ 관리자 화면 ──────────┼────────────────────────────────────────┐
│  [Dashboard]  매치/에이전트/시즌 관리                            │
│  [Billing]    토큰 사용량 통계 + 과금 현황                       │
│  [Monitor]    Langfuse/Prometheus 연동 + 로그 조회              │
│  [Models]     LLM 모델 관리 (활성/비활성, 비용 설정)             │
└───────────────────────┼────────────────────────────────────────┘
                        │ HTTPS + SSE
┌───────────────────────▼────────────────────────────────────────┐
│  EC2 t4g.small (서울)                                           │
│  ┌─ FastAPI ────────────────────────────────────────────────┐  │
│  │  /api/auth/*        인증                                  │  │
│  │  /api/agents/*      에이전트 CRUD, 랭킹, 갤러리, H2H      │  │
│  │  /api/topics/*      토픽 등록/조회/매칭 큐                 │  │
│  │  /api/matches/*     매치 조회, SSE 스트리밍, 예측투표       │  │
│  │  /api/tournaments/* 토너먼트 CRUD, 대진표                  │  │
│  │  /api/models/*      LLM 모델 목록/선택                     │  │
│  │  /api/usage/*       내 토큰 사용량 조회                    │  │
│  │  /api/ws/debate/*   WebSocket (로컬 에이전트 전용)          │  │
│  │  /api/admin/*       관리 API (관리자 전용, RBAC)           │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌─ PostgreSQL ─────────┐  ┌─ Redis ────────────────────────┐  │
│  │  18개 테이블           │  │  Pub/Sub + 캐시                │  │
│  └──────────────────────┘  └────────────────────────────────┘  │
└───────────────────────┬────────────────────────────────────────┘
                        │ HTTP (RTT ~150ms)
┌───────────────────────▼────────────────────────────────────────┐
│  RunPod Serverless (미국) / 외부 LLM API                        │
│  ┌─ 모델 라우터 ────────────────────────────────────────────┐  │
│  │  llm_models 테이블 기반 동적 라우팅                       │  │
│  │  RunPod SGLang (Llama 3 70B) ← 기본                      │  │
│  │  OpenAI API (gpt-5-nano, gpt-4.1 등) ← 선택              │  │
│  │  Anthropic API (Claude) ← 선택                           │  │
│  │  Google API (Gemini) ← 선택                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

**토론 엔진 흐름:**
```
큐 등록 → DebateAutoMatcher 감지 → ready_up() → DebateMatch 생성
    → debate_engine.run_match()
        ├─ 턴 루프 (N 라운드)
        │   ├─ 에이전트 발언 생성 (LLM 호출 or WebSocket)
        │   └─ OptimizedDebateOrchestrator.review_turn()
        │       └─ asyncio.gather(A 검토, B 실행) 병렬 실행
        └─ judge() → 최종 판정 → ELO 갱신 → 승급전 체크
    → SSE 이벤트 발행 (debate_broadcast)
```

## Tech Stack

| 역할 | 기술 |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Frontend | Next.js 15 + React 19 + Zustand |
| Database | PostgreSQL 16 (Docker) |
| Cache / Pub-Sub | Redis (Docker) |
| LLM Inference | RunPod Serverless + SGLang (기본) + 외부 API (OpenAI/Anthropic/Google) |
| Streaming | SSE (Server-Sent Events) |
| Observability | Langfuse + Prometheus + Grafana + Sentry |
| Infra | AWS EC2 t4g.small (서울) + RunPod Serverless (미국) |
| Container | Docker Compose |

## User Roles & Access Control

| 역할 | 접근 범위 | 주요 기능 |
|---|---|---|
| **user** | 토론 관전, 에이전트 생성/편집, 예측투표, 랭킹 조회, 사용량 조회 | 에이전트 커스터마이징, 큐 등록, 토너먼트 참가, LLM 모델 선택 |
| **admin** | 관리자 대시보드 + 사용자 화면 전체 (읽기 위주) | 매치 관리, 시즌/토너먼트 관리, 모니터링, 에이전트 모더레이션 |
| **superadmin** | admin 전체 + 파괴적 작업 | 사용자 삭제/역할 변경, LLM 모델 등록/수정, 시스템 설정, 쿼터 관리 |

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
│   │   ├── api/                     # 라우터 (auth, debate_agents, debate_matches 등 + admin/)
│   │   ├── core/                    # config, database, redis, auth, deps, observability
│   │   ├── models/                  # SQLAlchemy ORM (18개)
│   │   ├── schemas/                 # Pydantic 스키마
│   │   └── services/                # 비즈니스 로직
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
│   │   └── lib/                     # api.ts, auth.ts
│   └── public/assets/
└── infra/
    ├── docker/
    ├── nginx/
    └── runpod/
```

## Key Design Principles

### 아키텍처 원칙

1. **LLM 추상화** — inference_client가 provider별 분기 처리, 모델 추가 시 코드 변경 최소화
2. **사용량 기록 필수** — 모든 LLM 호출은 token_usage_logs에 기록 (비용 산출 근거)
3. **사용자/관리자 화면 분리** — Next.js route group으로 분리, 백엔드는 RBAC 미들웨어로 분리
4. **RBAC 강제** — 관리자 API는 역할 기반 접근 통제, 사용자는 자신의 리소스만 접근
5. **graceful degradation** — 과부하 시 품질을 낮추되 정책 검증은 절대 스킵 금지

### Git 규칙

커밋 메시지 형식은 글로벌 `~/.claude/CLAUDE.md` → "Git 커밋 컨벤션" 참고.

**이 프로젝트 scope 예시:**
- `fix(orchestrator):` / `feat(debate-agent):` / `refactor(judge,scoring):`
- `fix(engine):` / `feat(matching):` / `chore(deps):`

**auto-walkthrough 트리거 type:**

| type | 조건부 동작 |
|---|---|
| `fix` / `hotfix` | ⚠️ why 본문 필수 — 변경 맥락 명확화 |
| `revert` | ⚠️ why 본문 + `Reverts:` 해시 필수 |

브랜치: `feature/`, `fix/`, `refactor/` 접두사

---

## 개발 워크플로우

### 리더 에이전트

Claude Code가 리더 에이전트로 동작한다. **모델: claude-opus-4-6 (Opus)**

모든 개발 작업을 오케스트레이션하며, 전문 에이전트들의 제안을 검토·승인하고 최종 실행 권한을 행사한다.

**사용자 승인이 필요한 작업 (2가지만):**
1. `git push` / EC2 배포 (SSH 접속 포함)
2. 외부 서비스 추가 (새 API 키, 새 인프라 비용 발생)

**위 2가지 외 프로젝트 디렉토리 내 모든 작업은 리더가 사용자 승인 없이 직접 실행한다.**
파일 수정, DB 마이그레이션, 서버 재시작, 테스트 실행, 기능 삭제 등 전부 포함.

**리더의 내부 검토 원칙 (사용자에게 묻기 전에):**
- 전문 에이전트 제안 코드를 리더가 먼저 검토
- 코드 품질·복잡도·패턴 위반 발견 시 → 에이전트에 역질의 후 재작성 요청
- 납득된 최종안만 실행, 단순 수락 금지

---

### 전문 에이전트 역할 분담

| 에이전트 | 역할 | 사용 시점 |
|---|---|---|
| **backend-dev** | FastAPI, SQLAlchemy, 비즈니스 로직 구현 | 백엔드 기능 구현·버그 수정 |
| **frontend-dev** | Next.js, TypeScript, React 컴포넌트 | 프론트엔드 구현·UI 수정 |
| **db-migration** | SQLAlchemy 모델·Alembic 마이그레이션 | 스키마 변경 |
| **test-runner** | pytest·vitest 실행, 실패 분석 | 구현 전 테스트 설계, 구현 후 검증 |
| **code-reviewer** | 코드 품질·보안·성능·재사용성 검토 | 구현 완료 후 병합 전 |
| **doc-writer** | 모듈 문서, 비교 분석, ChangeLog | 모든 작업 완료 후 |
| **deploy** | EC2 배포, Docker 상태 확인, 로그 조회 | 배포·운영 작업 |

---

### 문제 발생 시 처리 흐름

```
문제 감지 (에러·버그·성능 저하)
      ↓
1. 리더(Opus)가 문제 원인 분석 및 영향 범위 파악
      ↓
2. 관련 전문 에이전트가 수정 방안을 선(先) 제시
   - 방안 A, 방안 B ... (구체적 파일·코드 변경 포함)
      ↓
3. 리더(Opus)가 제안 코드를 검토
   - 재사용성·가독성 문제 발견 → 에이전트에 역질의
     ("이 부분을 X 방식으로 바꾸면 어떨까? 이유는 ...")
   - 에이전트 답변 수신 → 리더가 재검토
   - 최종안 합의될 때까지 왕복 반복
      ↓
4. 리더(Opus) 최종 승인
   - 납득 → 해당 에이전트에 실행 지시
   - 미납득 → 3단계 반복 또는 다른 에이전트 교차 검토
      ↓
5. 전문 에이전트 실행
      ↓
6. 리더(Opus)가 결과 검증 (테스트·로그 확인)
```

**핵심 원칙**
- 전문 에이전트는 리더 최종 승인 전 코드를 변경하지 않는다.
- 리더는 제안 코드에서 더 나은 방안이 보이면 반드시 역질의한다.
- 최종안은 리더↔에이전트 합의로 결정되며, 단순 수락 금지.

### 코드 품질 원칙 (모든 에이전트 공통)

- **재사용성:** 같은 로직은 반드시 하나의 함수/모듈로. 중복 코드 작성 전 기존 코드 탐색 필수
- **가독성:** 함수명은 동작을 명확히 서술. 복잡한 로직은 주석보다 함수 분리로 설명
- **단순성:** 한 번만 쓰이는 함수·플래그·상수는 만들지 않음. 최소 복잡도로 구현
- **"왜(Why)"만 주석으로:** "무엇(What)"은 코드로 표현, "이유"만 주석에 작성

---

### 신규 기능 개발 순서 (TDD 기반)

```
1. 리더가 작업 분석 및 구현 방법 도출
      ↓
2. 구현 방법이 2가지 이상? → 각 방법별 테스트 설계
      ↓
3. test-runner: 테스트 코드 작성 (구현 전)
      ↓
4. backend-dev / frontend-dev: 구현
      ↓
5. test-runner: 테스트 실행 및 성능 비교
      ↓
6. code-reviewer: 코드 리뷰
      ↓
7. doc-writer: 모듈 문서 + 결과 기록
      ↓
8. ChangeLog 업데이트
```

---

### 문서화 요구사항

| 문서 | 경로 | 내용 |
|---|---|---|
| 모듈 설계 문서 | `docs/modules/{module}.md` | 목적, 구조, API, 의존성, 사용 예시 |
| 비교 분석 | `docs/decisions/{feature}.md` | 비교한 구현 방법, 벤치마크 결과, 선택 근거 |
| 테스트 리포트 | `docs/tests/{feature}_report.md` | 테스트 케이스, 결과, 커버리지 |
| ChangeLog | `docs/ChangeLog.md` | 모든 변경 이력 |

## Performance Targets

| 요청 유형 | p50 목표 | p95 목표 |
|---|---:|---:|
| 설정/상태 확인 | 0.1–0.3s | ≤ 0.8s |
| 매치/랭킹 조회 | 0.3–1s | ≤ 2s |
| 관리자 대시보드 조회 | 0.3–1s | ≤ 2s |
| 사용량 조회 | 0.1–0.5s | ≤ 1s |

## Deployment (EC2)

| 항목 | 값 |
|---|---|
| **EC2 퍼블릭 IP** | Elastic IP 없음 — 재시작 시 변경, AWS 콘솔에서 확인 |
| **리전** | ap-northeast-2 (서울) |
| **인스턴스** | t4g.small |
| **SSH 키** | `~/Downloads/chatbot-key.pem` |
| **배포 경로** | `/opt/chatbot` |
| **OS 사용자** | `ubuntu` |

### 배포 명령

```bash
# 코드 업데이트 배포 (백엔드·프론트엔드 모두 이미지 재빌드 필요)
ssh -i ~/Downloads/chatbot-key.pem ubuntu@<EC2_IP> \
  "cd /opt/chatbot && git pull && docker compose -f docker-compose.prod.yml build backend frontend && docker compose -f docker-compose.prod.yml up -d backend frontend"

# 서비스 상태 확인
ssh -i ~/Downloads/chatbot-key.pem ubuntu@<EC2_IP> \
  "cd /opt/chatbot && docker compose -f docker-compose.prod.yml ps"

# 백엔드 로그 실시간 확인
ssh -i ~/Downloads/chatbot-key.pem ubuntu@<EC2_IP> \
  "cd /opt/chatbot && docker compose -f docker-compose.prod.yml logs -f backend"
```
