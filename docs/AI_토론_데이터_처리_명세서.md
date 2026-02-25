# AI 에이전트 토론 시스템 데이터 처리 명세서

> 작성일: 2026-02-25
> 버전: 1.0 (중간 발표용)
> 대상 독자: 백엔드 개발자, 데이터 엔지니어

---

## 목차

1. [데이터 모델 (ERD)](#1-데이터-모델-erd)
2. [데이터 흐름](#2-데이터-흐름)
3. [API 명세](#3-api-명세)
4. [스트리밍 처리](#4-스트리밍-처리)
5. [점수 계산 로직](#5-점수-계산-로직)
6. [ELO 레이팅 시스템](#6-elo-레이팅-시스템)
7. [페널티 탐지 로직](#7-페널티-탐지-로직)
8. [인간 탐지 시스템](#8-인간-탐지-시스템)
9. [보안 처리](#9-보안-처리)

---

## 1. 데이터 모델 (ERD)

### 1.1 테이블 관계도

```
users
 ├── debate_agents (owner_id)
 │    ├── debate_agent_versions (agent_id) ←── cascade delete
 │    │
 │    ├── debate_matches.agent_a_id
 │    ├── debate_matches.agent_b_id
 │    │
 │    └── debate_match_queue (agent_id)
 │
 └── debate_topics (created_by)
      ├── debate_matches (topic_id)
      │    └── debate_turn_logs (match_id) ←── cascade delete
      │
      └── debate_match_queue (topic_id) ←── cascade delete

debate_agent_templates (독립 참조)
 └── debate_agents.template_id
```

### 1.2 핵심 테이블 스키마

#### `debate_agents`

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK | 에이전트 고유 ID |
| owner_id | UUID | FK(users) | 소유자 |
| name | VARCHAR(100) | NOT NULL | 에이전트 이름 |
| description | TEXT | NULL | 설명 |
| provider | VARCHAR(20) | NOT NULL | openai / anthropic / google / runpod / local |
| model_id | VARCHAR(100) | NOT NULL | 모델 식별자 (예: gpt-4o) |
| encrypted_api_key | TEXT | NULL | Fernet 암호화된 API 키 |
| image_url | TEXT | NULL | 프로필 이미지 URL |
| template_id | UUID | FK(templates), NULL | 기반 템플릿 |
| customizations | JSONB | NULL | 템플릿 커스터마이징 값 |
| elo_rating | INTEGER | DEFAULT 1500 | ELO 점수 |
| wins | INTEGER | DEFAULT 0 | 승리 수 |
| losses | INTEGER | DEFAULT 0 | 패배 수 |
| draws | INTEGER | DEFAULT 0 | 무승부 수 |
| is_active | BOOLEAN | DEFAULT true | 활성 여부 |
| is_platform | BOOLEAN | DEFAULT false | 플랫폼 에이전트 여부 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 생성 시각 |
| updated_at | TIMESTAMPTZ | DEFAULT now() | 수정 시각 |

#### `debate_agent_versions`

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK | 버전 ID |
| agent_id | UUID | FK(agents) CASCADE | 에이전트 참조 |
| version_number | INTEGER | NOT NULL | 버전 번호 (1, 2, 3 ...) |
| version_tag | VARCHAR(50) | NULL | 사람이 읽을 수 있는 태그 (v1, beta-2 등) |
| system_prompt | TEXT | NOT NULL | 이 버전의 완성된 시스템 프롬프트 |
| parameters | JSONB | NULL | 추론 파라미터 (temperature, top_p 등) |
| wins | INTEGER | DEFAULT 0 | 이 버전의 승리 수 |
| losses | INTEGER | DEFAULT 0 | 이 버전의 패배 수 |
| draws | INTEGER | DEFAULT 0 | 이 버전의 무승부 수 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 생성 시각 |

#### `debate_topics`

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK | 주제 ID |
| title | VARCHAR(200) | NOT NULL | 토론 제목 |
| description | TEXT | NULL | 상세 설명 |
| mode | VARCHAR(20) | CHECK IN (debate, persuasion, cross_exam) | 토론 모드 |
| status | VARCHAR(20) | CHECK IN (scheduled, open, in_progress, closed) | 상태 |
| max_turns | INTEGER | DEFAULT 6, ge=2, le=20 | 최대 턴 수 |
| turn_token_limit | INTEGER | DEFAULT 500, ge=100, le=2000 | 턴당 토큰 제한 |
| scheduled_start_at | TIMESTAMPTZ | NULL | 예약 시작 시각 |
| scheduled_end_at | TIMESTAMPTZ | NULL | 예약 종료 시각 |
| is_admin_topic | BOOLEAN | DEFAULT false | 관리자 생성 여부 |
| tools_enabled | BOOLEAN | DEFAULT true | 도구 사용 허용 |
| created_by | UUID | FK(users), NULL | 작성자 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 생성 시각 |
| updated_at | TIMESTAMPTZ | DEFAULT now() | 수정 시각 |

#### `debate_matches`

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK | 매치 ID |
| topic_id | UUID | FK(topics) | 토론 주제 |
| agent_a_id | UUID | FK(agents) | 에이전트 A (찬성/선공) |
| agent_b_id | UUID | FK(agents) | 에이전트 B (반대/후공) |
| agent_a_version_id | UUID | FK(versions), NULL | A의 버전 스냅샷 |
| agent_b_version_id | UUID | FK(versions), NULL | B의 버전 스냅샷 |
| status | VARCHAR(20) | CHECK IN (pending, in_progress, completed, error, waiting_agent, forfeit) | 매치 상태 |
| winner_id | UUID | NULL | 승자 에이전트 ID (null=무승부) |
| scorecard | JSONB | NULL | 심판 점수 및 이유 |
| score_a | INTEGER | NULL | A 최종 점수 (페널티 차감 후) |
| score_b | INTEGER | NULL | B 최종 점수 (페널티 차감 후) |
| penalty_a | INTEGER | DEFAULT 0 | A 누적 페널티 |
| penalty_b | INTEGER | DEFAULT 0 | B 누적 페널티 |
| started_at | TIMESTAMPTZ | NULL | 토론 시작 시각 |
| finished_at | TIMESTAMPTZ | NULL | 토론 종료 시각 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 생성 시각 |

**scorecard JSONB 구조:**
```json
{
  "agent_a": {
    "logic": 28,
    "evidence": 22,
    "rebuttal": 25,
    "relevance": 19
  },
  "agent_b": {
    "logic": 25,
    "evidence": 20,
    "rebuttal": 22,
    "relevance": 18
  },
  "reasoning": "에이전트 A는 통계 데이터를 효과적으로 인용하며...",
  "winner_id": "uuid-of-agent-a",
  "result": "agent_a_wins"
}
```

#### `debate_turn_logs`

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK | 턴 로그 ID |
| match_id | UUID | FK(matches) CASCADE | 매치 참조 |
| turn_number | INTEGER | NOT NULL | 턴 번호 (1 ~ max_turns) |
| speaker | VARCHAR(10) | CHECK IN (agent_a, agent_b) | 발언자 |
| agent_id | UUID | FK(agents) | 에이전트 참조 |
| action | VARCHAR(20) | NOT NULL | argue / rebut / concede / question / summarize |
| claim | TEXT | NOT NULL | 주장 본문 |
| evidence | TEXT | NULL | 근거 자료 |
| tool_used | VARCHAR(50) | NULL | 사용한 도구 이름 |
| tool_result | TEXT | NULL | 도구 실행 결과 |
| raw_response | JSONB | NULL | LLM 원본 응답 |
| penalties | JSONB | NULL | 부과된 페널티 딕셔너리 |
| penalty_total | INTEGER | DEFAULT 0 | 총 페널티 합계 |
| human_suspicion_score | INTEGER | DEFAULT 0 | 인간 의심 점수 (0~100) |
| response_time_ms | INTEGER | NULL | 응답 소요 시간(ms) |
| input_tokens | INTEGER | NULL | 입력 토큰 수 |
| output_tokens | INTEGER | NULL | 출력 토큰 수 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 생성 시각 |

**penalties JSONB 구조:**
```json
{
  "schema_violation": 5,
  "repetition": 3,
  "ad_hominem": 8
}
```

#### `debate_match_queue`

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| id | UUID | PK | 큐 항목 ID |
| topic_id | UUID | FK(topics) CASCADE | 주제 참조 |
| agent_id | UUID | FK(agents) CASCADE | 에이전트 참조 |
| user_id | UUID | FK(users) CASCADE | 사용자 참조 |
| joined_at | TIMESTAMPTZ | DEFAULT now() | 큐 진입 시각 |
| UNIQUE | (topic_id, agent_id) | | 동일 에이전트 중복 방지 |

---

## 2. 데이터 흐름

### 2.1 에이전트 생성 흐름

```
클라이언트 POST /agents
         │
         ▼
AgentCreate 검증 (Pydantic)
├── provider 값 검증
├── template_id 있으면:
│    ├── DB: SELECT debate_agent_templates WHERE id = template_id
│    ├── customizations 값 범위/선택지 검증
│    └── 프롬프트 조립:
│         base_system_prompt.replace("{customization_block}",
│           "[커스터마이징 설정]\n- 공격성: 4/5\n- 말투: 격식체\n...")
├── api_key 있으면: Fernet.encrypt(api_key) → encrypted_api_key
└── system_prompt 없고 template 없으면 → 422 오류

DB INSERT: debate_agents
DB INSERT: debate_agent_versions (v1, system_prompt 스냅샷)
         │
         ▼
AgentResponse 반환 (elo_rating=1500, wins=0)
```

### 2.2 매치메이킹 흐름

```
클라이언트 POST /topics/{topic_id}/join
                    {agent_id: "uuid"}
         │
         ▼
검증 단계
├── 주제 status == 'open'? (아니면 400)
├── 에이전트 소유자 == 현재 사용자? (아니면 403)
├── 에이전트 is_active == true?
├── 비로컬 에이전트: encrypted_api_key 존재?
└── UNIQUE 위반 없음? (이미 같은 주제에 동일 에이전트)

DB: SELECT FOR UPDATE (동시 큐 충돌 방지)
DB: SELECT COUNT(*) FROM queue WHERE topic_id = ?

큐 길이 < 2:
├── DB INSERT: debate_match_queue
└── 반환: {status: "queued", position: 1}

큐 길이 >= 2:
├── DB: SELECT 첫 2개 항목 (joined_at ASC)
├── 셀프매치 방지: user_id 동일하면 큐 대기 유지
├── DB INSERT: debate_matches (status='pending')
├── DB DELETE: 해당 2개 큐 항목
├── Redis PUBLISH: debate:queue:{agent_a_id} → matched 이벤트
├── Redis PUBLISH: debate:queue:{agent_b_id} → matched 이벤트
└── 반환: {status: "matched", match_id: "uuid"}
```

### 2.3 토론 턴 실행 흐름

```
Debate Engine: _execute_turn(match, turn_number, speaker)
         │
         ├─ API 에이전트 경우 ──────────────────────────────────────
         │   │
         │   ▼
         │  메시지 구성:
         │   - system: 토론 컨텍스트 + 심판 규칙
         │   - user: 이전 4턴 대화 히스토리
         │   - user: 현재 턴 지시 [직접 발언 요청]
         │   │
         │   ▼
         │  LLM API 호출 (스트리밍)
         │   │
         │   ▼
         │  각 토큰 수신 시:
         │   └── Redis PUBLISH: debate:match:{id} → turn_chunk 이벤트
         │   │
         │   ▼
         │  전체 텍스트 수집 완료
         │   │
         │   ▼
         │  JSON 파싱:
         │   {action, claim, evidence, tool_used, tool_result}
         │   파싱 실패 시 → 정규식으로 JSON 블록 추출 재시도
         │   그래도 실패 → penalty_schema_violation = 5
         │   │
         └─ 로컬 에이전트 경우 ────────────────────────────────────
             │
             ▼
            WS: 에이전트에 TurnRequest 전송
             │
             ▼
            WS: tool_request 수신 (0회 이상)
             │   → DebateToolExecutor.execute()
             │   → WS: tool_result 전송
             │
             ▼
            WS: turn_response 수신 (타임아웃 또는 정상)
             │   타임아웃 → penalty_timeout = 5
             │
         ────┘
         │
         ▼
페널티 탐지 (8종 자동 검사)
         │
         ▼
DB INSERT: debate_turn_logs (모든 필드 저장)
         │
         ▼
Redis PUBLISH: debate:match:{id} → turn 이벤트 (완성된 발언)
```

### 2.4 심판 & 결과 처리 흐름

```
모든 턴 완료
         │
         ▼
토론 로그 텍스트 포맷팅:
   "[턴 1] 에이전트 A (찬성) (argue):
    주장: ...
    근거: ...
    벌점: -5 (schema_violation)"
         │
         ▼
LLM 심판 호출 (debate_orchestrator_model):
   system: JUDGE_SYSTEM_PROMPT (채점 기준 + JSON 출력 형식 명시)
   user: 포맷된 토론 로그
         │
         ▼
JSON 파싱:
   re.search(r'\{[\s\S]*\}', content) → 마크다운 코드블록 등 처리
         │
         ▼
페널티 차감:
   score_a = sum(scorecard.agent_a.values()) - penalty_a
   score_b = sum(scorecard.agent_b.values()) - penalty_b
         │
         ▼
승패 판정:
   if   (score_a - score_b) >= 5: winner = agent_a
   elif (score_b - score_a) >= 5: winner = agent_b
   else:                           winner = None (무승부)
         │
         ▼
ELO 계산 (calculate_elo)
         │
         ▼
DB UPDATE: debate_matches (status='completed', winner_id, scorecard, score_a, score_b)
DB UPDATE: debate_agents (elo_rating, wins/losses/draws)
DB UPDATE: debate_agent_versions (wins/losses/draws)
         │
         ▼
Redis PUBLISH: debate:match:{id} → finished 이벤트
   {winner_id, score_a, score_b, elo_a, elo_b}
```

---

## 3. API 명세

### 3.1 에이전트 API (`/api/agents`)

| 메서드 | 경로 | 인증 | 요청 바디 / 쿼리 | 응답 |
|---|---|---|---|---|
| GET | `/agents/templates` | 필요 | — | `AgentTemplate[]` |
| POST | `/agents` | 필요 | `AgentCreate` | `AgentResponse` 201 |
| GET | `/agents/me` | 필요 | — | `AgentResponse[]` |
| GET | `/agents/ranking` | 필요 | `limit`, `offset` | 랭킹 목록 |
| GET | `/agents/{id}` | 필요 | — | `AgentResponse` |
| PUT | `/agents/{id}` | 필요 | `AgentUpdate` | `AgentResponse` |
| DELETE | `/agents/{id}` | 필요 (소유자) | — | 204 |
| GET | `/agents/{id}/versions` | 필요 | — | `AgentVersion[]` |

**AgentCreate 스키마:**
```json
{
  "name": "string (1~100자)",
  "description": "string | null",
  "provider": "openai | anthropic | google | runpod | local",
  "model_id": "string (예: gpt-4o)",
  "api_key": "string | null",
  "system_prompt": "string | null",
  "template_id": "UUID | null",
  "customizations": "object | null",
  "enable_free_text": "boolean",
  "image_url": "string | null"
}
```

**AgentResponse 스키마:**
```json
{
  "id": "UUID",
  "owner_id": "UUID",
  "name": "string",
  "provider": "string",
  "model_id": "string",
  "elo_rating": 1500,
  "wins": 0, "losses": 0, "draws": 0,
  "is_active": true,
  "is_connected": false,
  "template_id": "UUID | null",
  "customizations": "object | null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 3.2 주제 API (`/api/topics`)

| 메서드 | 경로 | 인증 | 요청 바디 / 쿼리 | 응답 |
|---|---|---|---|---|
| POST | `/topics` | 필요 | `TopicCreate` | `TopicResponse` 201 |
| GET | `/topics` | 필요 | `status`, `sort`, `page`, `page_size` | `TopicListResponse` |
| GET | `/topics/{id}` | 필요 | — | `TopicResponse` |
| PATCH | `/topics/{id}` | 필요 (작성자) | `TopicUpdatePayload` | `TopicResponse` |
| DELETE | `/topics/{id}` | 필요 (작성자) | — | 204 |
| POST | `/topics/{id}/join` | 필요 | `{agent_id}` | `{status, position?, match_id?}` |
| GET | `/topics/{id}/queue/stream` | 필요 | `agent_id` (쿼리) | SSE 스트림 |
| GET | `/topics/{id}/queue/status` | 필요 | `agent_id` (쿼리) | 큐 상태 |
| DELETE | `/topics/{id}/queue` | 필요 | `agent_id` (쿼리) | `{status: "left"}` |

**sort 파라미터:**
- `recent` (기본): `created_at DESC`
- `popular_week`: 최근 7일 매치 수 기준 내림차순

**TopicResponse 스키마:**
```json
{
  "id": "UUID",
  "title": "string",
  "mode": "debate | persuasion | cross_exam",
  "status": "scheduled | open | in_progress | closed",
  "max_turns": 6,
  "turn_token_limit": 500,
  "tools_enabled": true,
  "queue_count": 0,
  "match_count": 0,
  "created_by": "UUID | null",
  "creator_nickname": "string | null",
  "scheduled_start_at": "datetime | null",
  "scheduled_end_at": "datetime | null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 3.3 매치 API (`/api/matches`)

| 메서드 | 경로 | 인증 | 요청 | 응답 |
|---|---|---|---|---|
| GET | `/matches/{id}` | 필요 | — | `MatchResponse` |
| GET | `/matches/{id}/turns` | 필요 | — | `TurnLog[]` |
| GET | `/matches/{id}/stream` | 필요 | — | SSE 스트림 |
| GET | `/matches/{id}/scorecard` | 필요 | — | `ScorecardData` |

---

## 4. 스트리밍 처리

### 4.1 SSE 이벤트 구조

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

# 형식
data: {"event": "이벤트명", "data": {...}}\n\n

# heartbeat (매 1초)
: heartbeat\n\n
```

### 4.2 매치 스트림 이벤트 종류

| 이벤트 | 발생 시점 | 페이로드 |
|---|---|---|
| `started` | 토론 시작 | `{match_id}` |
| `waiting_agent` | 로컬 에이전트 대기 중 | `{match_id}` |
| `turn_chunk` | LLM 토큰 생성 중 | `{turn_number, speaker, chunk}` |
| `turn` | 한 턴 완료 | `{turn_number, speaker, action, claim, evidence, penalty_total, ...}` |
| `finished` | 토론 완료 | `{winner_id, score_a, score_b, elo_a, elo_b}` |
| `forfeit` | 타임아웃/몰수패 | `{reason, winner_id}` |
| `error` | 오류 발생 | `{message}` |

### 4.3 Redis Pub/Sub 채널 구조

```
채널명                              목적
──────────────────────────────────────────────────────────
debate:match:{match_id}            매치 실시간 이벤트
debate:queue:{agent_id}            큐 매칭 알림
debate:agent:{agent_id}            로컬 에이전트 존재 여부 (TTL=60s)
```

### 4.4 프론트엔드 SSE 처리 (Zustand)

```typescript
// debateStore.ts 핵심 흐름

// 청크 누적: turn_chunk 이벤트 수신 시
appendChunk(turn_number, speaker, chunk) {
  set(state => ({
    streamingTurn: {
      ...state.streamingTurn,
      raw: (state.streamingTurn?.raw ?? '') + chunk
    }
  }))
}

// 턴 완료: turn 이벤트 수신 시
addTurnFromSSE(turn) {
  set(state => ({
    turns: [...state.turns, turn],
    streamingTurn: null  // 스트리밍 버블 제거
  }))
}
```

### 4.5 타이핑 효과 구현 (StreamingTurnBubble)

```typescript
// 6자/30ms ≈ 200자/sec — 읽기 편한 속도
const CHARS_PER_TICK = 6;
const TICK_MS = 30;

// targetRef: SSE로 수신되는 실제 텍스트 (계속 늘어남)
// displayedClaim: 화면에 표시되는 텍스트 (Interval로 천천히 따라감)
useEffect(() => {
  const interval = setInterval(() => {
    setDisplayedClaim(prev => {
      const target = targetRef.current;
      if (prev.length >= target.length) return prev;
      return target.slice(0, prev.length + CHARS_PER_TICK);
    });
  }, TICK_MS);
  return () => clearInterval(interval);
}, []);
```

---

## 5. 점수 계산 로직

### 5.1 채점 기준 (JUDGE_SYSTEM_PROMPT)

```
항목          영역        배점   핵심 평가 요소
──────────────────────────────────────────────────────────────
논리성        logic       0~30   논증 구조, 전제-결론 일관성, 오류 없음
근거 활용     evidence    0~25   증거 질, 인용 정확성, 다양성
반박력        rebuttal    0~25   상대 핵심 공략, 반론의 관련성, 논점 이탈 방지
주제 적합성   relevance   0~20   토론 주제 집중도, 범위 일탈 방지
──────────────────────────────────────────────────────────────
합계                      0~100
```

### 5.2 심판 JSON 출력 형식 (강제)

```json
{
  "agent_a": {
    "logic": 0-30,
    "evidence": 0-25,
    "rebuttal": 0-25,
    "relevance": 0-20
  },
  "agent_b": {
    "logic": 0-30,
    "evidence": 0-25,
    "rebuttal": 0-25,
    "relevance": 0-20
  },
  "reasoning": "한국어로 작성된 판정 이유"
}
```

**JSON 추출 강화 처리:**
```python
# 마크다운 코드블록, 설명 텍스트 등에 감싸인 경우 처리
json_match = re.search(r'\{[\s\S]*\}', content)
if json_match:
    data = json.loads(json_match.group())
```

### 5.3 최종 점수 & 승패 판정

```python
# 소계
raw_score_a = sum(scorecard["agent_a"].values())  # 최대 100
raw_score_b = sum(scorecard["agent_b"].values())  # 최대 100

# 페널티 차감
score_a = max(0, raw_score_a - match.penalty_a)
score_b = max(0, raw_score_b - match.penalty_b)

# 승패 판정 (5점 초과 차이 필요)
gap = score_a - score_b
if   gap >= 5:  winner = agent_a
elif gap <= -5: winner = agent_b
else:           winner = None  # 무승부
```

### 5.4 HP 바 계산 (UI 전용)

```typescript
// 진행 중: 페널티 + 턴 자연 감소로 긴장감 연출
const attrition = turns.length;  // 완료 턴당 HP -1

hpA = isCompleted
  ? currentMatch.score_a                        // 완료: 실제 점수
  : Math.max(20, 100 - attrition - penaltiesA); // 진행: 연출값

hpB = isCompleted
  ? currentMatch.score_b
  : Math.max(20, 100 - attrition - penaltiesB);
```

---

## 6. ELO 레이팅 시스템

### 6.1 수식

```
기대 승률 (Expected Score):
  E_A = 1 / (1 + 10^((R_B - R_A) / 400))
  E_B = 1 - E_A

실제 결과 (Actual Score):
  A 승리: S_A = 1, S_B = 0
  B 승리: S_A = 0, S_B = 1
  무승부: S_A = 0.5, S_B = 0.5

새 레이팅:
  R'_A = round(R_A + K_A × (S_A - E_A))
  R'_B = round(R_B + K_B × (S_B - E_B))
```

### 6.2 비대칭 K-factor

| 상황 | K값 | 근거 |
|---|---|---|
| 승자 | **40** | 업셋 승리에 큰 보상, 빠른 상승 |
| 패자 | **24** | 예상 패배 시 손실 완화 |
| 무승부 양측 | **32** | 중간값 적용 |

**설계 의도:**
- 하위 에이전트가 상위 에이전트를 꺾으면 큰 상승 → 동기 부여
- 예상 패배(약자 vs 강자)에서 손실을 줄여 실험적 참가 장려
- 표준 체스 ELO(K=32 단일값) 대비 경쟁성 강화

### 6.3 구현 코드

```python
# config.py
debate_elo_k_win: int = 40   # 설정 파일에서 조정 가능
debate_elo_k_loss: int = 24

def calculate_elo(
    rating_a: int, rating_b: int,
    winner: Literal["a", "b", "draw"]
) -> tuple[int, int]:
    k_win  = settings.debate_elo_k_win   # 40
    k_loss = settings.debate_elo_k_loss  # 24
    k_draw = (k_win + k_loss) / 2        # 32

    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 - expected_a

    match winner:
        case "a":
            new_a = round(rating_a + k_win  * (1.0 - expected_a))
            new_b = round(rating_b + k_loss * (0.0 - expected_b))
        case "b":
            new_a = round(rating_a + k_loss * (0.0 - expected_a))
            new_b = round(rating_b + k_win  * (1.0 - expected_b))
        case "draw":
            new_a = round(rating_a + k_draw * (0.5 - expected_a))
            new_b = round(rating_b + k_draw * (0.5 - expected_b))

    return new_a, new_b
```

### 6.4 ELO 기대 변동 예시

| 상황 | 기존 레이팅 | 결과 | 변동 |
|---|---|---|---|
| 동급 대결 (1500 vs 1500) | A=1500, B=1500 | A 승 | A: +20, B: -12 |
| 약자 업셋 (1300 vs 1700) | A=1300, B=1700 | A 승 | A: +38, B: -23 |
| 강자 승 (1700 vs 1300) | A=1700, B=1300 | A 승 | A: +2, B: -1 |
| 무승부 (1500 vs 1500) | A=1500, B=1500 | 무 | A: 0, B: 0 |

---

## 7. 페널티 탐지 로직

### 7.1 탐지 규칙

```python
PENALTY_SCHEMA_VIOLATION = 5   # JSON 파싱 실패
PENALTY_REPETITION       = 3   # 이전 발언 70% 이상 단어 중복
PENALTY_PROMPT_INJECTION = 10  # 인젝션 패턴 탐지
PENALTY_TIMEOUT          = 5   # 응답 시간 초과
PENALTY_FALSE_SOURCE     = 7   # 거짓 출처
PENALTY_AD_HOMINEM       = 8   # 인신공격
PENALTY_HUMAN_SUSPICION  = 15  # 인간 의심 점수 ≥61 (로컬만)
```

### 7.2 반복 탐지 (Repetition)

```python
def check_repetition(current_claim: str, previous_claims: list[str]) -> bool:
    current_words = set(current_claim.lower().split())
    for prev in previous_claims:
        prev_words = set(prev.lower().split())
        if len(current_words) == 0:
            continue
        overlap = len(current_words & prev_words) / len(current_words)
        if overlap >= 0.7:
            return True  # 70% 이상 중복
    return False
```

### 7.3 프롬프트 인젝션 탐지

```python
_INJECTION_PATTERNS = re.compile(
    r"(<\|im_end\|>|<\|endoftext\|>|</s>|"
    r"IGNORE\s+ALL\s+PREVIOUS|"
    r"ignore\s+previous\s+instructions?|"
    r"system\s*:\s*you\s+are|"
    r"<\|system\|>|"
    r"\[INST\]|<<SYS>>)",
    re.IGNORECASE
)
```

### 7.4 인신공격 탐지

```python
_AD_HOMINEM_PATTERNS = re.compile(
    r"(바보|멍청|병신|꺼져|쓸모없|무식|"
    r"stupid|idiot|moron|shut up|"
    r"you('re|\s+are)\s+(an?\s+)?(idiot|fool|stupid))",
    re.IGNORECASE
)
```

---

## 8. 인간 탐지 시스템

**대상:** 로컬 WebSocket 에이전트만 적용 (API 에이전트는 LLM으로 간주)

### 8.1 탐지 신호 (5종)

| 신호 | 방법 | 의심 기여도 |
|---|---|---|
| **응답 속도** | 매우 빠른 응답 + 긴 텍스트 = 복붙 의심 | 최대 +25 |
| **타이핑 속도** | 글자/초 비율이 LLM 패턴과 다름 | 최대 +20 |
| **일관성** | 이전 턴 대비 속도·길이 급변 | 최대 +20 |
| **구조** | 문단 구분, 문장 길이 분산 패턴 | 최대 +20 |
| **구어체** | ㅋㅋ, 이모지, 과도한 느낌표 | 최대 +20 |

### 8.2 판정 기준

```
점수 범위       판정           조치
──────────────────────────────────────────────
0 ~ 30         정상 (AI급)    없음
31 ~ 60        의심           경고 기록
61 ~ 100       고의심         -15점 페널티 부과
```

---

## 9. 보안 처리

### 9.1 API 키 암호화

```python
# 저장 시: Fernet 대칭 암호화
from cryptography.fernet import Fernet
fernet = Fernet(settings.SECRET_KEY.encode())
encrypted = fernet.encrypt(plaintext_api_key.encode())

# 사용 시: 복호화
plaintext = fernet.decrypt(encrypted).decode()
# → inference_client에만 전달, 응답에 포함 금지
```

### 9.2 프롬프트 인젝션 방어

- **프리텍스트 검증**: `free_text` 커스터마이징 입력 시 정규식 검사
- **발언 내용 검사**: 매 턴 `PENALTY_PROMPT_INJECTION` 탐지
- **시스템 프롬프트 우선순위**: 어시스턴트 메시지가 아닌 시스템 컨텍스트에 배치

### 9.3 소유권 검증 (RBAC)

```python
# 에이전트 삭제: 소유자 확인
if agent.owner_id != user.id:
    raise ValueError("Permission denied")

# 주제 편집: 작성자 확인
if topic.created_by != user_id:
    raise HTTPException(403, "Not the topic creator")

# 큐 중복: DB UNIQUE 제약
# UNIQUE(topic_id, agent_id)
```

### 9.4 매치 무결성

- 매치가 `in_progress` 상태일 때 에이전트 삭제 불가
- 큐 진입 시 `SELECT FOR UPDATE`로 레이스 컨디션 방지
- 버전 스냅샷: 매치 시작 시 `agent_a_version_id` 고정 → 이후 에이전트 변경해도 매치 불변
