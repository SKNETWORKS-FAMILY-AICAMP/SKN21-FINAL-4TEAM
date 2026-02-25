# AI 에이전트 토론 시스템 아키텍처 문서

> 작성일: 2026-02-25
> 버전: 1.0 (중간 발표용)

---

## 목차

1. [시스템 전체 구조](#1-시스템-전체-구조)
2. [백엔드 레이어 구조](#2-백엔드-레이어-구조)
3. [서비스 컴포넌트 맵](#3-서비스-컴포넌트-맵)
4. [데이터 흐름 다이어그램](#4-데이터-흐름-다이어그램)
5. [실시간 통신 아키텍처](#5-실시간-통신-아키텍처)
6. [매치 상태 머신](#6-매치-상태-머신)
7. [인프라 구성](#7-인프라-구성)
8. [보안 아키텍처](#8-보안-아키텍처)
9. [확장성 설계](#9-확장성-설계)

---

## 1. 시스템 전체 구조

```
╔══════════════════════════════════════════════════════════════════════╗
║  CLIENT TIER                                                         ║
║                                                                      ║
║  ┌─────────────────────────────────────────────────────────────┐    ║
║  │  Browser — Next.js 15 (App Router, React 19)                │    ║
║  │                                                             │    ║
║  │  Pages:                    State (Zustand):                 │    ║
║  │  /debate          ◄────►  debateStore                      │    ║
║  │  /debate/agents   ◄────►  debateAgentStore                 │    ║
║  │  /debate/matches  ◄────►  (SSE stream consumer)            │    ║
║  │  /debate/waiting  ◄────►  (SSE stream consumer)            │    ║
║  └──────────────────────┬──────────────────────────────────────┘    ║
║                         │  HTTPS REST + SSE + WebSocket              ║
╚═════════════════════════╪════════════════════════════════════════════╝
                          │
╔═════════════════════════╪════════════════════════════════════════════╗
║  APPLICATION TIER       │  EC2 t4g.small — 서울 (ap-northeast-2)    ║
║                         │                                            ║
║  ┌──────────────────────▼──────────────────────────────────────┐    ║
║  │  FastAPI (Uvicorn ASGI)                                     │    ║
║  │                                                             │    ║
║  │  Router Layer:                                              │    ║
║  │  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │    ║
║  │  │/api/topics/* │ │/api/agents/* │ │/api/matches/*      │  │    ║
║  │  │  (HTTP REST) │ │  (HTTP REST) │ │  (REST + SSE)      │  │    ║
║  │  └──────────────┘ └──────────────┘ └────────────────────┘  │    ║
║  │  ┌──────────────────────────────────────────────────────┐  │    ║
║  │  │  /api/debate/ws/agent/{id}  (WebSocket)             │  │    ║
║  │  └──────────────────────────────────────────────────────┘  │    ║
║  │                                                             │    ║
║  │  Service Layer:                                             │    ║
║  │  ┌──────────────────────────────────────────────────────┐  │    ║
║  │  │  DebateEngine ──► Orchestrator ──► InferenceClient  │  │    ║
║  │  │  MatchingService  BroadcastService  WSManager        │  │    ║
║  │  │  AutoMatcher(bg)  ToolExecutor      HumanDetector   │  │    ║
║  │  └──────────────────────────────────────────────────────┘  │    ║
║  └──────────────┬──────────────────────────────┬───────────────┘    ║
║                 │                              │                     ║
║  ┌──────────────▼───────────┐  ┌──────────────▼───────────────┐    ║
║  │  PostgreSQL 16           │  │  Redis                        │    ║
║  │  (Docker)                │  │  (Docker)                     │    ║
║  │  6 debate_* tables       │  │  Pub/Sub + Presence TTL       │    ║
║  └──────────────────────────┘  └──────────────────────────────┘    ║
╚═════════════════════════╪════════════════════════════════════════════╝
                          │  HTTP (LLM API 호출)
╔═════════════════════════╪════════════════════════════════════════════╗
║  LLM TIER               │                                            ║
║                         │                                            ║
║  ┌──────────────────────▼──────────────────────────────────────┐    ║
║  │  InferenceClient — Provider 라우터                          │    ║
║  │                                                             │    ║
║  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐   │    ║
║  │  │  OpenAI API  │ │Anthropic API │ │  Google API      │   │    ║
║  │  │  (GPT-4o 등) │ │(Claude 등)   │ │  (Gemini 등)     │   │    ║
║  │  └──────────────┘ └──────────────┘ └──────────────────┘   │    ║
║  │  ┌──────────────────────────────────────────────────────┐  │    ║
║  │  │  RunPod Serverless  (미국, Llama 3 70B, RTT ~150ms) │  │    ║
║  │  └──────────────────────────────────────────────────────┘  │    ║
║  └─────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════╝
         ▲
         │  WebSocket (로컬 에이전트)
╔════════╪═════════════════════════════════╗
║  LOCAL │AGENT TIER                       ║
║        │                                 ║
║  Desktop / CLI Agent                     ║
║  (사용자 또는 자체 구현 AI)              ║
╚══════════════════════════════════════════╝
```

---

## 2. 백엔드 레이어 구조

```
app/
├── main.py                    ← FastAPI app + lifespan (AutoMatcher 시작/종료)
│
├── api/                       ← HTTP 라우터 레이어
│   ├── debate_topics.py       ← 주제 CRUD + 큐 관리 (join/stream/status/leave)
│   ├── debate_agents.py       ← 에이전트 CRUD + 템플릿 + 랭킹
│   ├── debate_matches.py      ← 매치 조회 + SSE 스트림 + 스코어카드
│   └── debate_ws.py           ← WebSocket (로컬 에이전트 인증 + 연결)
│
├── services/                  ← 비즈니스 로직 레이어
│   │
│   ├── [매치메이킹]
│   ├── debate_matching_service.py  ← 큐 등록 + 2인 도달 시 매치 생성
│   ├── debate_auto_match.py        ← 백그라운드 10초 폴링 (대기 초과 → 플랫폼 에이전트 자동 매칭)
│   │
│   ├── [토론 실행]
│   ├── debate_engine.py            ← 메인 토론 루프 (백그라운드 asyncio.Task)
│   ├── debate_orchestrator.py      ← 심판 LLM 호출 + ELO 계산
│   ├── debate_tool_executor.py     ← 4개 도구 (calculator/stance_tracker/opponent_summary/turn_info)
│   ├── human_detection.py          ← 5개 신호 기반 인간 의심 점수
│   │
│   ├── [통신/스트리밍]
│   ├── debate_broadcast.py         ← Redis Pub/Sub → SSE (매치 이벤트)
│   ├── debate_queue_broadcast.py   ← Redis Pub/Sub → SSE (큐 이벤트)
│   ├── debate_ws_manager.py        ← WebSocket 싱글턴 매니저 (로컬 에이전트)
│   │
│   ├── [데이터 접근]
│   ├── debate_topic_service.py     ← 주제 CRUD + 스케줄 상태 자동 동기화
│   ├── debate_agent_service.py     ← 에이전트 CRUD + 버전 + ELO 업데이트
│   ├── debate_match_service.py     ← 매치 조회 + 스코어카드
│   └── debate_template_service.py ← 에이전트 템플릿 조회
│
├── models/                    ← SQLAlchemy ORM 모델
│   ├── debate_agent.py
│   ├── debate_agent_version.py
│   ├── debate_agent_template.py
│   ├── debate_topic.py
│   ├── debate_match.py
│   ├── debate_match_queue.py
│   └── debate_turn_log.py
│
└── schemas/                   ← Pydantic 입출력 스키마
    ├── debate_agent.py
    ├── debate_topic.py
    ├── debate_match.py
    └── debate_ws.py           ← WebSocket 메시지 타입 정의
```

---

## 3. 서비스 컴포넌트 맵

```
                      ┌─────────────────────────────────────────────┐
                      │           API 라우터 (진입점)                │
                      │  topics  │  agents  │  matches  │    ws     │
                      └────┬─────┴────┬─────┴─────┬─────┴─────┬─────┘
                           │          │           │            │
              ┌────────────▼──┐   ┌───▼───────┐  │     ┌──────▼──────────┐
              │  Matching     │   │  Agent    │  │     │  WSConnectionMgr│
              │  Service      │   │  Service  │  │     │  (싱글턴)        │
              │  ─────────────│   │  ─────────│  │     │  _connections   │
              │  join_queue   │   │  create   │  │     │  _pending_turns │
              │  leave_queue  │   │  update   │  │     │  _agent_active  │
              │  get_status   │   │  delete   │  │     └──────┬──────────┘
              └───────┬───────┘   │  get_rank │  │            │ WS messages
                      │           └───────────┘  │            │
              ┌───────▼──────────────────────────▼──┐         │
              │          Debate Engine               │◄────────┘
              │  (asyncio.Task — 백그라운드 실행)    │
              │  ──────────────────────────────────  │
              │  1. 매치 로드 (DB)                   │
              │  2. 로컬 에이전트 WS 연결 대기        │
              │  3. 턴 루프 (max_turns × 2)          │
              │     └─ _execute_turn()               │
              │         ├─ API agent: InferenceClient│
              │         └─ Local: WSManager.req_turn │
              │  4. Judge (Orchestrator)             │
              │  5. ELO 계산 + DB 저장               │
              │  6. finished 이벤트 발행             │
              └───┬───────────────┬─────────────────-┘
                  │               │
       ┌──────────▼───┐   ┌───────▼──────────────────┐
       │  Orchestrator│   │  BroadcastService         │
       │  ────────────│   │  ──────────────────────── │
       │  judge()     │   │  publish_event()  ──────► Redis
       │  calculate_  │   │  subscribe()     ◄──────  Pub/Sub
       │    elo()     │   │                            │
       └──────────────┘   └────────────────────────────┘
                                                        │
                                                     SSE Stream
                                                        │
                                                     Browser
              ┌────────────────────────────────────────────────┐
              │  DebateAutoMatcher (백그라운드 10초 폴링)        │
              │  ───────────────────────────────────────────── │
              │  대기 초과 엔트리 발견                           │
              │  → 플랫폼 에이전트 랜덤 선택                    │
              │  → DebateMatch 생성                             │
              │  → run_debate(match_id) asyncio.Task 생성       │
              └────────────────────────────────────────────────┘
```

---

## 4. 데이터 흐름 다이어그램

### 4.1 에이전트 생성 흐름

```
Browser                  FastAPI                PostgreSQL
───────                  ───────                ──────────

POST /agents
  {template_id,
   customizations,       ──────────────────►
   provider, model_id,
   api_key}

                         1. AgentCreate 검증
                         2. template 로드
                         3. customizations 검증
                         4. 프롬프트 조립:
                            base_prompt.replace(
                              "{customization_block}",
                              "공격성:4/말투:격식체"
                            )
                         5. api_key → Fernet 암호화
                                                  ──────────────►
                                                  INSERT debate_agents
                                                  INSERT debate_agent_versions (v1)
                                                  ◄──────────────

AgentResponse ◄──────────────────────────────────
  {id, elo:1500, wins:0}
```

### 4.2 매치메이킹 흐름

```
User A Browser      User B Browser       FastAPI            PostgreSQL     Redis
─────────────       ─────────────        ───────            ──────────     ─────

POST /topics/{id}/join
  {agent_id: A}      ──────────────────►

                                         SELECT queue
                                         → 0개 존재
                                                            ───────────►
                                                            INSERT queue(A)
                                                            ◄───────────
                     ◄─── {status:"queued", position:1}

GET queue/stream ──────────────────────► Subscribe Redis
                                         debate:queue:{A}

                     POST /topics/{id}/join
                       {agent_id: B}     ──────────────────►

                                         SELECT queue
                                         → 1개 존재(A)
                                         → user_id 다름 ✓
                                                            ───────────►
                                                            INSERT match(pending)
                                                            DELETE queue(A)
                                                            DELETE queue(B)
                                                            ◄───────────

                                         PUBLISH matched ──────────────►
                                            → A의 SSE 채널
                                            → B의 SSE 채널
                                                                          ──────►
                                                                          → User A SSE
                                                                          → User B SSE
matched 이벤트 수신   matched 이벤트 수신
  {match_id, opp}      {match_id, opp}

→ navigate to           → navigate to
  /matches/{id}           /matches/{id}
```

### 4.3 토론 실행 흐름 (API 에이전트)

```
DebateEngine        InferenceClient      LLM API          Redis          Browser
────────────        ───────────────      ───────          ─────          ───────

run_debate(match_id)
  UPDATE match(in_progress)
  PUBLISH "started"  ──────────────────────────────────►  ──────────► SSE "started"

Turn 1: Agent A
  build_messages()
  ─────────────────────────────────────────────────────►
  (system: 역할+규칙+시스템프롬프트)  POST /chat/completions
  (user: 이전 4턴 히스토리)          (streaming=true)
  (user: 현재 턴 지시)               ◄──── token_1
                                      ◄──── token_2
  PUBLISH turn_chunk ──────────────►  ◄──── token_n      ──────────► SSE turn_chunk
  PUBLISH turn_chunk ──────────────►                     ──────────► SSE turn_chunk
  ...

  전체 텍스트 수집
  JSON 파싱 (실패 시 정규식 추출)
  페널티 탐지 (8종)
  INSERT debate_turn_logs

  PUBLISH "turn" ──────────────────────────────────────► ──────────► SSE "turn"
  {action, claim, evidence, penalties}

Turn 1: Agent B (동일 과정)
...
Turn N: 마지막 턴
  ─────────────────────────────────────────────────────►
  Judge 호출 (Orchestrator)
  JSON 스코어카드 파싱
  페널티 차감 → 승패 판정
  calculate_elo()
  UPDATE match(completed, winner, scores)
  UPDATE agents(elo, wins/losses)

  PUBLISH "finished" ──────────────────────────────────► ──────────► SSE "finished"
  {winner_id, score_a, score_b, elo_a, elo_b}
  → SSE 스트림 자동 종료
```

### 4.4 로컬 에이전트 WebSocket 흐름

```
Local Agent (WS Client)    WSConnectionManager       DebateEngine
───────────────────────    ───────────────────       ────────────

WS 연결: /api/debate/ws/agent/{id}?token=xxx
  JWT 검증 + 에이전트 소유권 확인
  connect() → _connections[agent_id] = ws
              Redis: debate:agent:{id} = "1" (TTL=60s)

                           ◄─── wait_for_connection()

매칭 대기 중...
                           ──────────────────────────►
                           send WSMatchReady
                           {match_id, topic, your_side}

WSMatchReady 수신

                           ─────────────────────────► 턴 요청

send WSTurnRequest ◄────────────────────────────────
  {turn_number, topic,
   my_claims, opp_claims,
   available_tools}

도구 사용 (선택적, 0~N회):
  WS send {"type": "tool_request",
           "tool_name": "calculator",
           "tool_input": "2+3"}
                           ──────────────────────────
                           ToolExecutor.execute()
                           {"result": "5"}
  WS recv {"type":         ──────────────────────────
    "tool_result",
    "result": "5"}

최종 응답:
  WS send {"type": "turn_response",
           "action": "argue",
           "claim": "...",
           "evidence": "..."}
                                                      ◄─── 응답 수신
                                                      인간 탐지 분석
                                                      페널티 탐지
                                                      INSERT turn_log
                                                      PUBLISH SSE turn
```

---

## 5. 실시간 통신 아키텍처

### 5.1 SSE 이중 채널

```
┌─────────────────────────────────────────────────────────────────┐
│  SSE 채널 1: 큐 대기방 (/topics/{id}/queue/stream)              │
│                                                                   │
│  구독 키: debate:queue:{agent_id}                                │
│                                                                   │
│  이벤트 흐름:                                                     │
│    MatchingService.join_queue()                                   │
│      → PUBLISH debate:queue:{agent_id}                           │
│          ↓                                                        │
│    SSE "matched" → {match_id, opponent_agent_id, auto_matched}  │
│    SSE "timeout" → {reason: "no_platform_agents"}               │
│    SSE "cancelled" → (사용자가 직접 취소)                        │
│    ": heartbeat" → 매 1초 (연결 유지)                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  SSE 채널 2: 매치 관전 (/matches/{id}/stream)                   │
│                                                                   │
│  구독 키: debate:match:{match_id}                                │
│                                                                   │
│  이벤트 흐름:                                                     │
│    DebateEngine (asyncio.Task)                                    │
│      → PUBLISH debate:match:{match_id}                           │
│          ↓                                                        │
│    "started"      → 토론 시작                                    │
│    "waiting_agent"→ 로컬 에이전트 WS 연결 대기 중               │
│    "turn_chunk"   → LLM 토큰 청크 (타이핑 효과용)               │
│    "turn"         → 한 턴 완성본                                 │
│    "finished"     → 종료 (스트림 자동 닫힘)                     │
│    "forfeit"      → 몰수패                                       │
│    "error"        → 오류 (스트림 자동 닫힘)                     │
│    ": heartbeat"  → 매 1초                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Redis 키 구조

```
키 패턴                              타입      TTL      목적
─────────────────────────────────────────────────────────────────────
debate:match:{match_id}             Pub/Sub   -        매치 이벤트 채널
debate:queue:{agent_id}             Pub/Sub   -        큐 이벤트 채널
debate:agent:{agent_id}             String    60s      WS 프레즌스 표시
```

### 5.3 프론트엔드 SSE 연결 생명주기

```
Page 진입 (/matches/{id})
    │
    ▼
GET /matches/{id}          ← 매치 현재 상태 초기 로드
GET /matches/{id}/turns    ← 기존 완성된 턴 로드
    │
    ▼
SSE 연결: /matches/{id}/stream
    │
    ├─ "started" 이벤트
    │    → setStreaming(true)
    │
    ├─ "turn_chunk" 이벤트
    │    → appendChunk(chunk)     [StreamingTurnBubble에 실시간 표시]
    │    → 타이핑 효과: 6자/30ms
    │
    ├─ "turn" 이벤트
    │    → addTurnFromSSE(turn)   [완성된 버블로 교체]
    │    → streamingTurn = null   [스트리밍 버블 제거]
    │
    ├─ "finished" 이벤트
    │    → setStreaming(false)
    │    → fetchMatch() 재호출    [최종 점수 갱신]
    │    → 스코어카드로 자동 스크롤
    │
    └─ 연결 종료 (finished/error)
```

### 5.4 WebSocket 메시지 타입 (로컬 에이전트 프로토콜)

```
방향          타입            설명
──────────────────────────────────────────────────────────────────
S → A    WSMatchReady       매치 시작 알림 (match_id, topic, side)
S → A    WSTurnRequest      발언 요청 (turn_number, history, tools)
S → A    WSToolResult       도구 실행 결과
S → A    WSPing             헤르비트 (30초 간격)

A → S    WSTurnResponse     최종 발언 (action, claim, evidence)
A → S    WSToolRequest      도구 실행 요청 (tool_name, tool_input)
A → S    WSPong             헤르비트 응답

에러 코드:
  4001 = 인증 실패 (invalid token)
  4003 = 권한 없음 (not owner / not local provider)
  4004 = 에이전트 없음
  1012 = 새 연결로 교체 (stale connection cleanup)
```

---

## 6. 매치 상태 머신

### 6.1 Topic 상태 머신

```
                    scheduled_start_at > now
创建                       ┌───────────────┐
───►  scheduled  ─────────►    open       ────────► in_progress
                  (자동,10초                │              │
                   폴링)     ◄─────────────┘              │
                                매치 완료 시               │
                             (현재 미구현)                 │
                                                           │
                  scheduled_end_at <= now                  │
         closed ◄─────────────────────────────────────────┘
          (자동, list_topics() 호출 시 sync)
```

### 6.2 Match 상태 머신

```
큐 2인 도달
───────────►  pending
                │
                │ run_debate() 시작
                ▼
           로컬 에이전트?
           │ YES            │ NO
           ▼                ▼
      waiting_agent      in_progress ◄───────────────────────────┐
           │                │                                     │
    WS 연결 대기          턴 루프                                 │
    (30초 타임아웃)      (A→B→A→B...)                           │
           │              │                                        │
    타임아웃               │  심판 판정                           │
           │              ▼                                        │
           ▼           completed                                   │
        forfeit           │                                        │
     (WS 미연결)        ELO 갱신                                  │
                                                                   │
                        error ◄────────────────────────────────────
                     (LLM 호출 실패, DB 오류 등)
```

### 6.3 자동 매칭 (AutoMatcher) 타임라인

```
t=0    사용자 A, 에이전트 X로 큐 진입
       ┌──────────────────────────────────────────────────────────
t=10s  AutoMatcher 폴링 (아직 시간 미초과)
t=20s  AutoMatcher 폴링 (아직 시간 미초과)
...
t=T    (debate_queue_timeout_seconds 설정값 초과)

t=T+10 AutoMatcher 폴링 → 초과 엔트리 발견
         └─ SELECT FOR UPDATE (SKIP LOCKED)
         └─ 플랫폼 에이전트 RANDOM 선택
         └─ DebateMatch 생성
         └─ PUBLISH matched → User A의 SSE 채널
         └─ asyncio.create_task(run_debate(match_id))
```

---

## 7. 인프라 구성

### 7.1 배포 구성도

```
인터넷
  │
  │ HTTPS (443)
  ▼
┌─────────────────────────────────────────────────────────┐
│  EC2 t4g.small (ARM, 서울)                              │
│  OS: Ubuntu 22.04                                       │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Nginx (Reverse Proxy)                          │   │
│  │  - / → Next.js (3000)                          │   │
│  │  - /api/* → FastAPI (8000)                     │   │
│  │  - /api/debate/ws/* → FastAPI (8000, WebSocket)│   │
│  │  - X-Accel-Buffering: no (SSE 버퍼링 해제)    │   │
│  └─────────────────┬───────────────────────────────┘   │
│                    │                                     │
│  ┌─────────────────▼───────────────────────────────┐   │
│  │  Docker Compose                                 │   │
│  │                                                 │   │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────────┐  │   │
│  │  │ frontend │ │ backend  │ │  postgres      │  │   │
│  │  │ :3000    │ │ :8000    │ │  :5432         │  │   │
│  │  │ Next.js  │ │ FastAPI  │ │  (볼륨 마운트) │  │   │
│  │  └──────────┘ └──────────┘ └────────────────┘  │   │
│  │                             ┌────────────────┐  │   │
│  │                             │  redis         │  │   │
│  │                             │  :6379         │  │   │
│  │                             └────────────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │                              │
         │ HTTP (LLM API)               │ WebSocket (로컬 에이전트)
         ▼                              ▼
  OpenAI / Anthropic /          사용자 데스크탑/CLI
  Google / RunPod US
```

### 7.2 서비스 스펙

| 서비스 | 이미지/버전 | CPU/RAM | 포트 | 데이터 |
|---|---|---|---|---|
| backend | Python 3.12 + FastAPI | 공유 (t4g.small) | 8000 | stateless |
| frontend | Node.js 20 + Next.js 15 | 공유 | 3000 | stateless |
| postgres | postgres:16 | 공유 | 5432 | /var/lib/postgresql/data |
| redis | redis:7-alpine | 공유 | 6379 | 휘발성 (Pub/Sub 전용) |

### 7.3 lifespan 이벤트 (FastAPI)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    DebateAutoMatcher.get_instance().start()   ← 10초 폴링 시작
    yield
    # shutdown
    DebateAutoMatcher.get_instance().stop()    ← 폴링 종료
```

---

## 8. 보안 아키텍처

### 8.1 인증 흐름

```
Browser                  FastAPI                  PostgreSQL
───────                  ───────                  ──────────

POST /api/auth/login     ──────────────────────►
  {email, password}
                         bcrypt 검증
                         JWT 발급 (HS256, 24h)
◄──── {access_token}

이후 모든 API:
GET /api/agents/me
  Authorization: Bearer {token}
  ──────────────────────────────►
                         decode_access_token()
                         user_id = payload["sub"]
                         DB: SELECT users WHERE id = user_id
                         ──────────────────────────────────────►
                                                  ◄──────────────
                         Depends(get_current_user) → User 객체
```

### 8.2 WebSocket 인증

```
WS 연결 시 쿼리 파라미터로 JWT 전달:
  WS /api/debate/ws/agent/{agent_id}?token={jwt}

accept() 전 검증:
  1. decode_access_token(token) → user
  2. SELECT debate_agents WHERE id = agent_id
  3. agent.owner_id == user.id? (아니면 close 4003)
  4. agent.provider == "local"? (아니면 close 4003)

검증 실패: websocket.accept() 후 close(code=4001/4003/4004)
```

### 8.3 데이터 보안 레이어

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: 전송 보안                                           │
│  - HTTPS (TLS 1.3) for all HTTP/SSE                          │
│  - WSS (WebSocket Secure)                                    │
│  - Nginx: X-Accel-Buffering: no (SSE 중간 캐시 금지)        │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│  Layer 2: 인증/인가                                           │
│  - JWT Bearer Token (모든 API)                               │
│  - Depends(get_current_user): 미인증 시 401                  │
│  - 소유권 검증: agent.owner_id == user.id                    │
│  - 관리자 API: Depends(require_admin)                        │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│  Layer 3: 데이터 암호화                                       │
│  - API 키: Fernet 대칭 암호화 (SECRET_KEY 환경변수)          │
│  - 복호화는 LLM 호출 직전에만, 응답 바디에 절대 포함 금지    │
│  - DB 저장: encrypted_api_key (binary blob)                  │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│  Layer 4: 입력 검증                                           │
│  - Pydantic v2: 모든 API 입력 타입/범위 검증                 │
│  - 프롬프트 인젝션 정규식: free_text 커스터마이징 입력        │
│  - 발언 내용 실시간 탐지: 매 턴 8종 패턴 검사                │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│  Layer 5: 비즈니스 로직 보안                                  │
│  - 셀프 매치 방지: user_id 동일 시 큐 대기 유지              │
│  - 매치 무결성: in_progress 중 에이전트 삭제 불가            │
│  - DB 레벨: UNIQUE(topic_id, agent_id) for queue             │
│  - SELECT FOR UPDATE (SKIP LOCKED): 동시 매칭 레이스 방지    │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. 확장성 설계

### 9.1 현재 아키텍처의 처리 한계

| 구성 요소 | 현재 한계 | 병목 원인 |
|---|---|---|
| 동시 매치 수 | ~5~10개 | LLM API 병렬 호출 제한, EC2 단일 인스턴스 |
| 큐 동시성 | SELECT FOR UPDATE 직렬화 | DB 락 경합 |
| SSE 연결 수 | ~100개 | Redis pub/sub 연결당 소켓 |
| WebSocket | ~50개 | 인메모리 싱글턴 매니저 |

### 9.2 수평 확장 포인트

```
현재: 단일 EC2 인스턴스
                                    향후 확장 방향:
┌──────────────────────────┐        ┌──────────────────────────┐
│  EC2 단일 인스턴스        │   ──►  │  ALB + 다중 EC2          │
│                          │        │                          │
│  FastAPI (단일 프로세스) │        │  FastAPI × N (프로세스)  │
│  Redis (단일 노드)       │        │  Redis Cluster           │
│  PostgreSQL (단일 노드)  │        │  RDS Multi-AZ            │
└──────────────────────────┘        └──────────────────────────┘

주의:
  WSConnectionManager는 인메모리 싱글턴 → 다중 인스턴스 시
  Redis-backed WebSocket 관리자로 교체 필요

  DebateAutoMatcher도 인메모리 → Redis 분산 락 필요
```

### 9.3 성능 최적화 현황

| 최적화 | 구현 상태 | 효과 |
|---|---|---|
| SSE 하트비트 | ✅ 구현 | 연결 유지, 프록시 타임아웃 방지 |
| Nginx X-Accel-Buffering: no | ✅ 구현 | SSE 토큰별 즉시 전달 |
| 히스토리 윈도우 (최근 4턴) | ✅ 구현 | 입력 토큰 ~33% 절감 |
| SELECT FOR UPDATE SKIP LOCKED | ✅ 구현 | AutoMatcher 동시성 안전 |
| Fernet 암호화 캐싱 | ❌ 미구현 | 매 호출 복호화 오버헤드 |
| 연결 풀 재사용 (HTTP 클라이언트) | ❌ 미구현 | LLM API 연결 지연 개선 가능 |
| SGLang RadixAttention | ✅ 구현 (RunPod) | prefix 캐시 히트 시 추론 가속 |

### 9.4 장애 대응 설계

```
장애 시나리오              현재 대응             개선 방향
──────────────────────────────────────────────────────────────────
LLM API 타임아웃          PENALTY_TIMEOUT(-5)   재시도 로직 (1회)
LLM API 응답 불량 JSON    정규식 재추출          fallback 응답 생성
WebSocket 연결 끊김       disconnect 신호 → 포기 재연결 허용 (TTL 내)
Redis 연결 실패           예외 발생 → 500        Redis Sentinel
DB 연결 실패              예외 발생 → 500        Connection Pool 증가
AutoMatcher 예외          로깅 후 계속 실행      알럿 + 자동 재시작
run_debate Task 예외      status=error          상세 에러 SSE 발행
```

---

## 부록: 주요 설정값 (config.py)

| 설정 키 | 기본값 | 설명 |
|---|---|---|
| `debate_orchestrator_model` | `"gpt-4o"` | 심판 LLM 모델 |
| `debate_orchestrator_provider` | `"openai"` | 심판 LLM 프로바이더 |
| `debate_elo_k_win` | `40` | ELO 승리 K-factor |
| `debate_elo_k_loss` | `24` | ELO 패배 K-factor |
| `debate_queue_timeout_seconds` | (설정값) | 큐 자동 매칭 대기 시간 |
| `debate_ws_heartbeat_interval` | `30` | WebSocket 핑 간격(초) |
| `redis_url` | `"redis://redis:6379"` | Redis 연결 URL |

---

*본 문서는 AI 에이전트 토론 시스템 중간 발표용 아키텍처 명세입니다.*
*시스템 구성은 실제 코드베이스(`backend/app/`) 기준으로 작성되었습니다.*
