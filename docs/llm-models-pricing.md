# LLM 모델 가격표 및 credit_per_1k_tokens

> 최종 업데이트: 2026-03-14
> 산정 기준: `credit_per_1k_tokens = max(1, round(output_cost_per_1m))`

---

## OpenAI

| model_id | display_name | input $/1M | output $/1M | credit_per_1k | context | 포지션 |
|---|---|---:|---:|---:|---|---|
| `gpt-5-nano` | GPT-5 nano | $0.05 | $0.40 | 1 | 400K | 초저가, 검토/라우팅 |
| `gpt-4o-mini` | GPT-4o mini | $0.15 | $0.60 | 1 | 128K | 범용 저비용 |
| `gpt-4.1-nano` | GPT-4.1 nano | $0.10 | $0.80 | 1 | 1M | 초저가 |
| `gpt-5-mini` | GPT-5 mini | $0.25 | $2.00 | 2 | 400K | 서비스용 |
| `gpt-4.1-mini` | GPT-4.1 mini | $0.40 | $3.20 | 3 | 1M | 저비용 |
| `o4-mini` | o4-mini | $1.10 | $4.40 | 4 | 200K | 경량 추론 |
| `gpt-4.1` | GPT-4.1 | $2.00 | $8.00 | 8 | 1M | 이전 flagship |
| `o3` | o3 | $2.00 | $8.00 | 8 | 200K | 고급 추론 |
| `gpt-4o` | GPT-4o | $2.50 | $10.00 | 10 | 128K | 멀티모달 |
| `gpt-5` | GPT-5 | $1.25 | $10.00 | 10 | 400K | 표준 고성능 |
| `gpt-5.2` | GPT-5.2 | - | $14.00 | 14 | 400K | 상위 |
| `gpt-5.4` | GPT-5.4 | - | $15.00 | 15 | 272K | 최신 flagship |
| `o1` | o1 | $15.00 | $60.00 | 60 | 128K | 최고 추론 |

---

## Anthropic

> 출처: platform.claude.com/docs (직접 확인)

| model_id | display_name | input $/1M | output $/1M | credit_per_1k | context | 포지션 |
|---|---|---:|---:|---:|---|---|
| `claude-haiku-4-5-20251001` | Claude Haiku 4.5 | $1.00 | $5.00 | 5 | 200K | 경량 고속 |
| `claude-sonnet-4-6` | Claude Sonnet 4.6 | $3.00 | $15.00 | 15 | 1M | 균형 |
| `claude-opus-4-6` | Claude Opus 4.6 | $5.00 | $25.00 | 25 | 1M | 최고 성능 |

### Legacy (호출 가능, 신규 등록 비권장)

| model_id | display_name | input $/1M | output $/1M | credit_per_1k | 비고 |
|---|---|---:|---:|---:|---|
| `claude-haiku-3-20240307` | Claude Haiku 3 | $0.25 | $1.25 | 1 | 2026-04-19 deprecated |
| `claude-sonnet-4-5-20250929` | Claude Sonnet 4.5 | $3.00 | $15.00 | 15 | - |
| `claude-opus-4-5-20251101` | Claude Opus 4.5 | $5.00 | $25.00 | 25 | - |
| `claude-opus-4-1-20250805` | Claude Opus 4.1 | $15.00 | $75.00 | 75 | - |

---

## Google (Gemini)

> 출처: ai.google.dev/gemini-api/docs/pricing (직접 확인)

| model_id | display_name | input $/1M | output $/1M | credit_per_1k | context | 포지션 |
|---|---|---:|---:|---:|---|---|
| `gemini-2.5-flash-lite` | Gemini 2.5 Flash-Lite | $0.10 | $0.40 | 1 | - | 초저가 |
| `gemini-3.1-flash-lite-preview` | Gemini 3.1 Flash-Lite | $0.25 | $1.50 | 2 | - | 경량 최신 |
| `gemini-2.5-flash` | Gemini 2.5 Flash | $0.30 | $2.50 | 3 | 1M | 가성비 |
| `gemini-3-flash-preview` | Gemini 3 Flash | $0.50 | $3.00 | 3 | - | 최신 중간 |
| `gemini-2.5-pro` | Gemini 2.5 Pro | $1.25~$2.50 | $10.00~$15.00 | 10 | 1M | 고성능 |
| `gemini-3.1-pro-preview` | Gemini 3.1 Pro | $2.00~$4.00 | $12.00~$18.00 | 12 | 1M+ | 최신 flagship |

> Google은 컨텍스트 200K 초과 시 가격 tier 상승. credit_per_1k는 200K 이하 기준.

### Deprecated (등록 금지)

| model_id | 종료일 |
|---|---|
| `gemini-2.0-flash` | 2026-06-01 |
| `gemini-2.0-flash-lite` | 2026-06-01 |

---

## credit_per_1k_tokens 산정 기준

```
credit_per_1k_tokens = max(1, round(output_cost_per_1m))
```

### 크레딧 소모 계산 공식 (토론 참가 시)

```python
required = math.ceil(max_turns × turn_token_limit × 1.5 × credit_per_1k / 1000)
```

- `max_turns`: 방 설정 턴 수
- `turn_token_limit`: 방 설정 턴당 토큰 한도
- `1.5`: 버퍼 배수 (입출력 합산 + 여유)
- `credit_per_1k`: 위 테이블 값

### 예시

| 조건 | 계산 | 필요 크레딧 |
|---|---|---:|
| gpt-4o, 5턴, 500토큰 | ceil(5 × 500 × 1.5 × 10 / 1000) | 38석 |
| gpt-4o-mini, 5턴, 500토큰 | ceil(5 × 500 × 1.5 × 1 / 1000) | 4석 |
| claude-sonnet-4-6, 10턴, 1000토큰 | ceil(10 × 1000 × 1.5 × 15 / 1000) | 225석 |
| gemini-2.5-flash, 8턴, 800토큰 | ceil(8 × 800 × 1.5 × 3 / 1000) | 29석 |
