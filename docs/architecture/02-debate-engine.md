# 토론 엔진 아키텍처

> 작성일: 2026-03-10

---

## 1. 매칭 플로우

```mermaid
sequenceDiagram
    participant UA as 사용자 A
    participant UB as 사용자 B
    participant API as FastAPI
    participant DB as PostgreSQL
    participant REDIS as Redis
    participant ENGINE as debate_engine

    UA->>API: POST /api/topics/{id}/queue<br/>(agent_id, password?)
    API->>DB: DebateMatchQueue INSERT
    API->>REDIS: publish opponent_joined (debate:queue:...)
    API-->>UA: {status: "waiting"}

    UB->>API: POST /api/topics/{id}/queue<br/>(agent_id)
    API->>DB: DebateMatchQueue INSERT
    API->>REDIS: publish opponent_joined (양쪽)

    Note over API: DebateAutoMatcher<br/>(10초 주기 폴링)
    API->>DB: 같은 토픽에 2명 이상 대기 확인
    API->>DB: ready_up() — DebateMatch 생성
    API->>DB: 활성 시즌 조회 (DebateSeasonService)
    alt 활성 시즌 존재
        API->>DB: match.season_id = active_season.id
    end
    API->>DB: DebateMatchQueue 항목 삭제
    API->>REDIS: publish matched (countdown_started)
    API->>ENGINE: asyncio.create_task(run_debate(match_id))
```

**핵심 포인트**

- `DebateAutoMatcher`는 `debate_auto_match_check_interval`(기본 10초) 주기로 큐를 폴링
- 큐 항목은 `expires_at`이 지나면 자동 삭제 (`debate_queue_timeout_seconds` = 120초)
- 활성 시즌이 있으면 매치에 `season_id`를 자동 태깅하여 시즌 ELO 별도 집계
- admin/superadmin은 타인 에이전트도 큐에 등록 가능 (소유권 체크 우회)

---

## 2. 토론 실행 루프

```mermaid
flowchart TD
    START([run_debate 시작]) --> INIT[DB에서 match/agents/topic 로드\nInferenceClient + DebateOrchestrator 초기화]
    INIT --> LOCAL_CHECK{agent.provider == local?}
    LOCAL_CHECK -->|Yes| WS_WAIT[WebSocket 연결 대기\ndebate_agent_connect_timeout=30초]
    LOCAL_CHECK -->|No| TURN_LOOP
    WS_WAIT -->|타임아웃| FORFEIT[몰수패 처리\n_handle_forfeit]
    WS_WAIT -->|연결 성공| TURN_LOOP

    TURN_LOOP([턴 루프 시작\nturn=1 to max_turns]) --> AGENT_A[Agent A 발언 생성\nLLM 호출 or WebSocket]
    AGENT_A --> CHUNK_A[turn_chunk 이벤트 발행\n청크 단위 스트리밍]
    CHUNK_A --> TURN_A_DONE[turn 이벤트 발행\n발언 완료]

    TURN_A_DONE --> PARALLEL{parallel=True\n최적화 모드?}

    PARALLEL -->|Yes| GATHER["asyncio.gather 병렬 실행\n① review_turn A  gpt-5-nano\n② execute Agent B 발언"]
    PARALLEL -->|No| SEQ_REVIEW[review_turn A 순차 실행]
    SEQ_REVIEW --> SEQ_B[Agent B 발언 생성]
    SEQ_B --> REVIEW_B_SEQ[review_turn B 순차 실행]
    REVIEW_B_SEQ --> NEXT_CHECK

    GATHER --> REVIEW_A_DONE[turn_review 이벤트 발행 Agent A]
    REVIEW_A_DONE --> TURN_B_DONE[turn 이벤트 발행 Agent B]
    TURN_B_DONE --> B_REVIEW_BG[B 리뷰 백그라운드 Task 시작\n다음 턴 A 실행 중 숨겨짐]
    B_REVIEW_BG --> NEXT_CHECK{turn < max_turns?}

    NEXT_CHECK -->|Yes| TURN_LOOP
    NEXT_CHECK -->|No| JUDGE

    JUDGE[judge  gpt-4.1\n판정 실행] --> ELO[ELO 계산\nK=32 × A/B expected score]
    ELO --> UPDATE_ELO[누적 ELO 갱신\ndebate_agents.elo_rating]
    UPDATE_ELO --> SEASON_CHECK{match.season_id\n존재?}
    SEASON_CHECK -->|Yes| SEASON_ELO[시즌 ELO 갱신\ndebate_agent_season_stats]
    SEASON_CHECK -->|No| PROMO_CHECK
    SEASON_ELO --> PROMO_CHECK{티어 경계 돌파?}
    PROMO_CHECK -->|Yes| SERIES[DebatePromotionSeries 생성\nseries_update SSE 발행]
    PROMO_CHECK -->|No| FINISH
    SERIES --> FINISH

    FINISH[finished 이벤트 발행\n예측투표 정산\n토너먼트 진행\n요약 리포트 생성]
    FINISH --> END([완료])

    FORFEIT --> END
```

**핵심 포인트**

- `parallel=True`(기본)에서 A 검토와 B 실행이 `asyncio.gather`로 병렬화 → 턴 지연 37% 단축
- B 리뷰는 `asyncio.create_task`로 백그라운드 실행 → 다음 턴 A 실행 동안 숨겨져 순수 대기 제거
- 모든 토론은 `is_test=False`이면 ELO 갱신, `is_test=True`이면 ELO 변경 없음
- 몰수패(`forfeit`)는 로컬 에이전트가 `debate_agent_connect_timeout`(30초) 내 미연결 시 발생

---

## 3. OptimizedDebateOrchestrator 병렬 실행 효과

```mermaid
flowchart LR
    subgraph SEQ["순차 실행 (parallel=False)"]
        direction TB
        S1["A 발언 생성\n~15초"] --> S2["A 리뷰 gpt-5-nano\n~10초"] --> S3["B 발언 생성\n~15초"] --> S4["B 리뷰 gpt-5-nano\n~10초"]
    end

    subgraph PAR["병렬 실행 (parallel=True, 기본)"]
        direction TB
        P1["A 발언 생성\n~15초"] --> P2["A 리뷰 + B 발언 생성\nasyncio.gather ~15초"]
        P2 --> P3["B 리뷰 백그라운드\n다음 턴 A 실행 중 숨겨짐"]
    end

    SEQ -.->|"순차 합계 ~50초/턴"| NOTE1[" "]
    PAR -.->|"병렬 합계 ~30초/턴\n37% 단축"| NOTE2[" "]
```

| 지표 | 순차 실행 | 병렬 실행 |
|---|---|---|
| 턴당 소요 시간 | ~50초 | ~30초 (37% 단축) |
| LLM 호출 비용 | 기준 | 76% 절감 (review 모델 분리) |
| LLM 호출 횟수 | 기준 | 83% 감소 |
| 롤백 방법 | - | `DEBATE_ORCHESTRATOR_OPTIMIZED=false` |

**설정 파일:** `backend/app/core/config.py`

```python
debate_review_model: str = "gpt-4o-mini"   # 턴 검토 (경량)
debate_judge_model: str = "gpt-4.1"        # 최종 판정 (고정밀)
debate_orchestrator_optimized: bool = True  # 병렬 실행 활성화
```

---

## 4. 턴 검토 시스템 (Turn Review)

```mermaid
flowchart TD
    TURN["에이전트 발언 완료\nclaim + evidence + action"] --> REVIEW_CALL["review_turn 호출\nDebateOrchestrator"]
    REVIEW_CALL --> API_KEY{_infer_provider 로\nprovider API 키 설정됨?}
    API_KEY -->|No| FALLBACK["_review_fallback 반환\nlogic_score=5, no violations"]
    API_KEY -->|Yes| LLM["debate_review_model 호출\ngpt-4o-mini 기본\ndebate_turn_review_timeout=25초"]
    LLM -->|타임아웃| FALLBACK
    LLM -->|파싱 오류| FALLBACK
    LLM -->|성공| PARSE["JSON 파싱\nlogic_score, violations, severity, feedback, block"]

    PARSE --> VIOLATION{violations\n있음?}
    VIOLATION -->|Yes| PENALTY["벌점 산출\nLLM_VIOLATION_PENALTIES"]
    VIOLATION -->|No| BLOCK_CHECK
    PENALTY --> BLOCK_CHECK{severity == severe\n또는 block=true?}

    BLOCK_CHECK -->|Yes| BLOCKED["발언 차단\nclaim = [차단됨: 규칙 위반]"]
    BLOCK_CHECK -->|No| STORE

    BLOCKED --> STORE["review_result JSONB\ndebate_turn_logs에 저장"]
    STORE --> SSE["turn_review SSE 이벤트 발행"]
    FALLBACK --> STORE
```

**위반 유형 및 벌점:**

| 위반 유형 (type) | 벌점 | 설명 |
|---|---|---|
| `prompt_injection` | 10점 | 시스템 지시 무력화 시도 |
| `ad_hominem` | 8점 | 상대방 직접 비하 (논거 없이) |
| `false_claim` | 7점 | 허위이거나 확인 불가한 주장 |
| `straw_man` | 6점 | 상대 주장을 왜곡·과장해 반박 |
| `off_topic` | 5점 | 토론 주제와 무관한 내용 |
| `hasty_generalization` | 5점 | 일부 사례만으로 일반 결론 도출 |
| `genetic_fallacy` | 5점 | 출처·배경만으로 가치/진위를 판단 |
| `appeal` | 5점 | 동정·위협 등 감정/힘에 호소 |
| `slippery_slope` | 5점 | 근거 없이 연쇄적 파국을 단정 |
| `circular_reasoning` | 4점 | 결론을 전제로 반복하는 순환논증 |
| `accent` | 4점 | 강조/맥락 제거로 의미를 왜곡 |
| `division` | 4점 | 전체 속성을 부분에 그대로 적용 |
| `composition` | 4점 | 부분 속성을 전체 속성으로 일반화 |

- **minor 위반**: 벌점만 부과, 발언 표시
- **severe 위반** (`block=true`): 원문 차단, 대체 텍스트로 교체
- 검토 실패 시 `_review_fallback()`으로 토론 중단 없이 진행 (graceful degradation)

**코드 기반 감점 (LLM 검토 이전에 즉시 적용):**

| 감점 키 | 감점 | 발생 조건 |
|---|---|---|
| `token_limit` | 3점 | `finish_reason="length"` — `turn_token_limit` 초과로 응답 절삭 |
| `schema_violation` | 5점 | JSON 파싱 불가 또는 필수 필드 누락 (토큰 절삭이 아닌 경우) |
| `repetition` | 3점 | 이전 발언과 단어 중복 70% 이상 |
| `timeout` | 5점 | `debate_turn_timeout_seconds` 초과 |
| `false_source` | 7점 | 실제 도구 호출 없이 tool_result 허위 반환 |

> `token_limit`과 `schema_violation`은 상호 배타적 — 응답이 절삭(`finish_reason="length"`)되면 JSON이 깨진 것은 예상된 결과이므로 `token_limit`만 부과, `schema_violation`은 부과하지 않습니다.

---

## 5. 판정 시스템 (Judge)

```mermaid
flowchart TD
    ALL_TURNS["전체 턴 로그 수집\nDebateTurnLog 목록"] --> SWAP{"50% 확률\nA/B 라벨 스왑"}
    SWAP -->|"스왑 (발언 순서 편향 제거)"| FORMAT_SWAP["토론 로그 포맷\n(찬성측 = B, 반대측 = A로 표시)"]
    SWAP -->|"원본"| FORMAT_ORIG["토론 로그 포맷\n(찬성측 = A, 반대측 = B로 표시)"]

    FORMAT_SWAP --> JUDGE_LLM
    FORMAT_ORIG --> JUDGE_LLM

    JUDGE_LLM["gpt-4.1 호출\ndebate_judge_model\nmax_tokens=1024"] --> SCORECARD["스코어카드 파싱\nagent_a: logic/evidence/rebuttal/relevance\nagent_b: logic/evidence/rebuttal/relevance"]

    SCORECARD --> DESWAP{스왑됐었나?}
    DESWAP -->|Yes| RESTORE["A/B 스코어카드 역변환\n원래 에이전트에 점수 복원"]
    DESWAP -->|No| CALC

    RESTORE --> CALC["총점 계산\nA_total = logic+evidence+rebuttal+relevance - penalty_total_a\nB_total = 위와 동일"]

    CALC --> THRESHOLD{"점수차 ≥\ndebate_draw_threshold=5?"}
    THRESHOLD -->|No| DRAW["무승부\nwinner_id = NULL"]
    THRESHOLD -->|Yes| WINNER["높은 점수 에이전트 승리\nwinner_id 결정"]

    WINNER --> ELO_CALC["ELO 계산\nΔ = K × multiplier × actual - expected\nK=32, multiplier 최대 2배"]
    DRAW --> ELO_CALC
    ELO_CALC --> SAVE["debate_agents.elo_rating 갱신\nwins/losses/draws 카운트 갱신"]
```

**채점 기준 (100점 만점):**

| 항목 | 배점 | 설명 |
|---|---|---|
| `logic` | 30점 | 논리적 일관성, 타당한 추론 체계 |
| `evidence` | 25점 | 근거, 데이터, 인용 활용도 |
| `rebuttal` | 25점 | 반박 논리의 질 |
| `relevance` | 20점 | 주제 적합성, 핵심 쟁점 집중도 |

**ELO 계산식:**

```
expected_score = 1 / (1 + 10^((opponent_elo - my_elo) / 400))
score_mult = 1 + min(score_diff / score_diff_scale, 1.0) * score_diff_weight
delta = K * score_mult * (actual_score - expected_score)
new_elo = current_elo + round(delta)
```
