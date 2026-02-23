# 한국어 RP 로컬 모델 비교 분석

> **작성일:** 2026-02-19
> **대상 환경:** RunPod Serverless, A100 80GB, SGLang
> **목적:** 한국어 롤플레이(RP) 챗봇에 적합한 셀프호스팅 LLM 모델 조사 및 비교

---

## 목차

1. [개요](#1-개요)
2. [현재 프로젝트 모델 현황](#2-현재-프로젝트-모델-현황)
3. [모델 비교 종합표](#3-모델-비교-종합표)
4. [Tier 1 — 한국어 RP 특화 모델](#4-tier-1--한국어-rp-특화-모델)
5. [Tier 2 — RP 파인튜닝 다국어 모델](#5-tier-2--rp-파인튜닝-다국어-모델)
6. [Tier 3 — 한국어 네이티브 범용 모델](#6-tier-3--한국어-네이티브-범용-모델)
7. [Tier 4 — 신규 및 예정 모델](#7-tier-4--신규-및-예정-모델)
8. [추천 배포 전략](#8-추천-배포-전략)
9. [멀티모델 전략](#9-멀티모델-전략)
10. [RunPod 배포 가이드](#10-runpod-배포-가이드)
11. [주요 동향 및 참고사항](#11-주요-동향-및-참고사항)
12. [출처](#12-출처)

---

## 1. 개요

### 1.1 배경

본 프로젝트의 RP 챗봇은 사용자 정의 페르소나 기반으로 Live2D 캐릭터와 연애 시뮬레이션 스타일 대화를 제공한다. 현재 RunPod Serverless에서 `meta-llama/Meta-Llama-3-70B-Instruct`를 기본 모델로 사용하고 있으나, 한국어 RP 품질 개선을 위해 더 적합한 모델을 탐색한다.

### 1.2 요구사항

| 항목 | 조건 |
|---|---|
| GPU | NVIDIA A100 80GB (RunPod Serverless) |
| 추론 엔진 | SGLang (RadixAttention, OpenAI 호환 API) |
| 한국어 품질 | 자연스러운 한국어 대화, 존댓말/반말 전환, 한국 문화 이해 |
| RP 품질 | 캐릭터 일관성, 감정 표현, 장문 대화 유지, 시나리오 처리 |
| 라이선스 | 상업적 사용 가능 (Apache 2.0 또는 동등) |
| 컨텍스트 | 최소 32K 토큰 (긴 대화 세션 지원) |
| 감정 연동 | Live2D 감정→모션 매핑에 활용 가능한 감정 태그 출력 |

### 1.3 핵심 발견

- **한국어 + RP 동시 특화 모델이 등장:** `developer-lunark/Qwen3-30B-Korean-Roleplay` (2025.12)
- **감정 태그 내장 모델 존재:** `{텍스트}|||emotion:{태그}` 포맷으로 Live2D에 바로 연동 가능
- **Qwen 계열이 한국어 RP 생태계를 지배:** Qwen2.5/3 기반 RP 파인튜닝이 대다수
- **Llama 4는 한국어 미지원:** 공식 12개 언어에 한국어 없음
- **한국 국산 모델(EXAONE, Solar)은 라이선스 또는 VRAM 장벽 존재**

---

## 2. 현재 프로젝트 모델 현황

### 2.1 등록된 모델

| 모델 | provider | model_id | 용도 |
|---|---|---|---|
| Llama 3 70B (RunPod) | `runpod` | `meta-llama/Meta-Llama-3-70B-Instruct` | 기본 추론 (AWQ 4bit) |
| GPT-4o Mini | `openai` | `gpt-4o-mini` | Economy 티어 |
| GPT-4o | `openai` | `gpt-4o` | Premium 티어 |

### 2.2 현재 모델의 한계

- **Llama 3 70B**: 한국어 RP 품질 보통 (★★★), 컨텍스트 8K 제한, RP 파인튜닝 없음
- **외부 API 모델**: 품질 우수하나 비용이 높고 지연시간 존재

### 2.3 모델 라우팅 구조

```
사용자 요청 → inference_client.py
  ├─ session.llm_model_id 또는 user.preferred_llm_model_id 확인
  ├─ llm_models 테이블에서 provider/model_id/endpoint 조회
  ├─ provider별 분기 (runpod / openai / anthropic / google)
  └─ 응답 + 토큰 수 → token_usage_logs 기록
```

> 참고: `llm_models` 테이블에 새 모델을 등록하면 코드 변경 없이 모델 추가 가능

---

## 3. 모델 비교 종합표

| 모델 | 파라미터 | 활성 파라미터 | 한국어 | RP | VRAM (A100 80GB) | 라이선스 | 컨텍스트 | 출시 |
|---|---|---|---|---|---|---|---|---|
| **Qwen3-30B-Korean-RP** | 30.5B | 3.3B (MoE) | ★★★★★ | ★★★★★ | BF16: 60GB | Apache 2.0 | 131K | 2025.12 |
| **Qwen3-32B** | 32.8B | 32.8B | ★★★★ | ★★★★ | BF16: 66GB | Apache 2.0 | 32K~131K | 2025.04 |
| **Qwen2.5-72B RP Ink** | 73B | 73B | ★★★★ | ★★★★★ | INT4: 40GB | Qwen License | 128K | 2024.12 |
| **EVA-Qwen2.5-72B** | 73B | 73B | ★★★★ | ★★★★★ | INT4: 40GB | Apache 2.0 | 128K | 2025 |
| **Qwen2.5-32B RP Ink** | 33B | 33B | ★★★☆ | ★★★★★ | BF16: 66GB | Apache 2.0 | 128K | 2024.12 |
| **EVA-Qwen2.5-32B v0.2** | 33B | 33B | ★★★☆ | ★★★★☆ | BF16: 66GB | Apache 2.0 | 128K | 2025 |
| **kaidol-qwen3-14b-kr-rp** | 14B | 14B | ★★★★★ | ★★★★ | BF16: 28GB | Apache 2.0 | 4K | 2025 |
| **Euryale L3.3 70B v2.3** | 70B | 70B | ★★★ | ★★★★★ | INT4: 40GB | Llama 3.3 | 131K | 2024.12 |
| **Sapphira L3.3 70B** | 70B | 70B | ★★★ | ★★★★★ | INT4: 40GB | Llama 3.3 | 32K | 2025 |
| **Llama-3.3-70B-Joyous** | 71B | 71B | ★★☆ | ★★★★☆ | INT4: 40GB | Llama 3.3 | 128K | 2025.12 |
| **CoSER-Llama-3.1-70B** | 70B | 70B | ★★☆ | ★★★★★ | INT4: 35GB | Llama 3.1 | 128K | 2025 |
| **Qwen3-30B-A3B** (베이스) | 30.5B | 3.3B (MoE) | ★★★☆ | ★★★★ | BF16: 60GB | Apache 2.0 | 131K | 2025.04 |
| **EXAONE 4.0 32B** | 31B | 31B | ★★★★★ | ★★★☆ | BF16: 64GB | 비상업용 (NC) | 131K | 2025.07 |
| **EXAONE 3.5 32B** | 31B | 31B | ★★★★★ | ★★★☆ | BF16: 64GB | 비상업용 (NC) | 32K | 2024.12 |
| **Bllossom-70B** | 71B | 71B | ★★★★★ | ★★★ | INT4: 40GB | Llama 3 | 8K | 2024.12 |
| **Solar Open 100B** | 102B | 12B (MoE) | ★★★★★ | ★★★ | 4xA100 필요 | Solar License | 128K | 2025.12 |
| **K-EXAONE 236B** | 236B | 23B (MoE) | ★★★★★+ | ★★★ | 8xH100 필요 | 제한적 상업 | 256K | 2026.01 |
| **Gemma 3 27B** | 27B | 27B | ★★★☆ | ★★★ | BF16: 54GB | Gemma ToU | 128K | 2025 |
| **Elice Korean-Qwen2.5-72B** | 72B | 72B | ★★★★★ | ★★★ | INT4: 37GB | Apache 2.0 | 128K | 2025 |

> **범례:** ★★★★★ 최우수 / ★★★★ 우수 / ★★★ 양호 / ★★☆ 보통 / ★ 미흡

---

## 4. Tier 1 — 한국어 RP 특화 모델

### 4.1 developer-lunark/Qwen3-30B-Korean-Roleplay (1순위 추천)

> **한국어 캐릭터 RP 전용으로 설계된 모델. 감정 태그 내장으로 Live2D 연동에 최적.**

| 항목 | 상세 |
|---|---|
| HuggingFace | [developer-lunark/Qwen3-30B-Korean-Roleplay](https://huggingface.co/developer-lunark/Qwen3-30B-Korean-Roleplay) |
| 파라미터 | 30.5B 총 / 3.3B 활성 (MoE, 128 experts, top-8) |
| 베이스 | Qwen/Qwen3-30B-A3B-Instruct-2507 |
| 학습 방식 | LoRA (rank=64, alpha=128), 한국어 캐릭터 RP 대화 데이터 |
| VRAM | BF16: ~60GB (A100 80GB에 여유 있음) |
| 컨텍스트 | 131K 토큰 |
| 라이선스 | Apache 2.0 (상업 사용 가능) |
| SGLang | 지원 (Qwen3 아키텍처) |

**평가 결과:**

| 지표 | 점수 |
|---|---|
| 일관성 (Consistency) | 4.1 / 5 |
| 공감 (Empathy) | 4.0 / 5 |
| 안전성 (Safety Avoidance) | 100% |

**감정 태그 출력 포맷:**

```
{캐릭터 응답 텍스트}|||emotion:{감정태그}
```

지원 감정 태그:

| 태그 | 설명 | Live2D 매핑 예시 |
|---|---|---|
| `neutral` | 평상시 | idle 모션 |
| `playful` | 장난스러운 | wink, tease 모션 |
| `joy` | 기쁨 | smile, laugh 모션 |
| `concern` | 걱정 | worried, frown 모션 |
| `confident` | 자신감 | proud, smirk 모션 |
| `cold` | 차가운 | glare, turn_away 모션 |

**프로젝트 시너지:**

- 감정 태그 → `live2d_models.emotion_mappings` JSONB에 직접 매핑
- 호감도 기반 응답 생성 → `persona_relationships` 테이블의 관계 단계와 일치
- MoE (3.3B 활성) → SSE 스트리밍 시 빠른 첫 토큰 생성
- 안전성 100% → 연령등급 정책(age_rating 게이트)과 호환

**한계:**

- 활성 파라미터 3.3B → Dense 32B 모델 대비 복잡한 시나리오에서 뉘앙스 부족 가능
- 한국어 전용 최적화 → 영어/다국어 사용자 대응 약함
- 장시간 대화(50턴+)에서 컨텍스트 유지 품질 저하 보고

---

### 4.2 developer-lunark/kaidol-qwen3-14b-korean-rp

> **K-pop 아이돌 RP에 특화된 경량 모델. 테스트/개발용 또는 저비용 티어에 적합.**

| 항목 | 상세 |
|---|---|
| HuggingFace | [developer-lunark/kaidol-qwen3-14b-korean-rp](https://huggingface.co/developer-lunark/kaidol-qwen3-14b-korean-rp) |
| 파라미터 | 14B (Dense) |
| 베이스 | Qwen/Qwen3-14B |
| 학습 방식 | DeepSpeed ZeRO-3 풀 파인튜닝, korean-role-playing 데이터셋 |
| VRAM | BF16: ~28GB |
| 컨텍스트 | 4,096 토큰 |
| 라이선스 | Apache 2.0 |

**장점:** 매우 빠른 추론, 낮은 VRAM, 한국어 아이돌 캐릭터 대화에 높은 일관성

**한계:** 14B로 복잡한 RP 시나리오 처리 한계, 컨텍스트 4K로 긴 대화 부적합, 아이돌 RP 외 범용성 낮음

---

## 5. Tier 2 — RP 파인튜닝 다국어 모델

### 5.1 allura-org/Qwen2.5-72B-RP-Ink

> **RP 커뮤니티의 골드 스탠다드. 캐릭터 일관성과 산문 품질에서 오픈소스 최강.**

| 항목 | 상세 |
|---|---|
| HuggingFace | [allura-org/Qwen2.5-72b-RP-Ink](https://huggingface.co/allura-org/Qwen2.5-72b-RP-Ink) |
| 파라미터 | 73B (Dense) |
| 베이스 | Qwen/Qwen2.5-72B-Instruct |
| 학습 방식 | LoRA (rank=16, alpha=32, dropout=0.25) |
| VRAM | BF16: ~146GB (미적합) / **INT4 AWQ: ~40GB** (A100 80GB 적합) |
| 컨텍스트 | 128K 토큰 |
| 라이선스 | Qwen License (상업 사용 시 조건 확인 필요) |
| 양자화 | GGUF (bartowski), EXL2, AWQ 제공 |

**커뮤니티 평가:**

> "역대 최고의 RP 경험" — SillyTavern 커뮤니티
> "32B 대비 일관성이 눈에 띄게 향상" — r/LocalLLaMA

**권장 설정:**

```
Temperature: 0.85
TopP: 0.8
TopA: 0.3
RepPenalty: 1.03
```

**한국어:** Qwen2.5 베이스의 29개 언어 지원으로 한국어 품질 양호. 단, RP 학습 데이터가 영어 중심.

---

### 5.2 allura-org/Qwen2.5-32B-RP-Ink

> **양자화 없이 A100 80GB에 올릴 수 있는 RP 모델. 품질 손실 없는 배포.**

| 항목 | 상세 |
|---|---|
| HuggingFace | [allura-org/Qwen2.5-32b-RP-Ink](https://huggingface.co/allura-org/Qwen2.5-32b-RP-Ink) |
| 파라미터 | 33B (Dense) |
| VRAM | **BF16: ~66GB** (A100 80GB 적합, 양자화 불필요) |
| 컨텍스트 | 128K 토큰 |
| 라이선스 | **Apache 2.0** (상업 사용 가능) |

**커뮤니티 평가:**

> "32B인데 많은 70B 모델보다 복잡한 시나리오 처리가 나음" — allura-org

**장점:** FP16/BF16 풀 정밀도 → 양자화 품질 손실 없음. Apache 2.0. 72B INT4보다 추론 속도 빠름.

---

### 5.3 EVA-Qwen2.5-72B / 32B

> **풀 파라미터 파인튜닝으로 LoRA보다 깊은 RP 적응.**

| 항목 | 72B | 32B v0.2 |
|---|---|---|
| HuggingFace | [EVA-UNIT-01/EVA-Qwen2.5-72B](https://huggingface.co/EVA-UNIT-01/EVA-Qwen2.5-72B) | [EVA-UNIT-01/EVA-Qwen2.5-32B-v0.2](https://huggingface.co/EVA-UNIT-01/EVA-Qwen2.5-32B-v0.2) |
| 학습 방식 | 풀 파라미터 파인튜닝 | 풀 파라미터 (Celeste 70B 데이터 혼합) |
| VRAM | INT4: ~40GB | BF16: ~66GB |
| 라이선스 | Apache 2.0 | Apache 2.0 |

**RP Ink vs EVA 비교:** RP Ink은 LoRA 기반으로 가볍고 베이스 모델 범용성 유지. EVA는 풀 파인튜닝으로 RP에 더 깊이 적응되었으나 범용 작업에서 약간 성능 저하 가능.

---

### 5.4 Qwen3-32B (Non-thinking 모드)

> **범용성과 한국어 RP를 동시에 잡는 밸런스 선택.**

| 항목 | 상세 |
|---|---|
| HuggingFace | [Qwen/Qwen3-32B](https://huggingface.co/Qwen/Qwen3-32B) |
| 파라미터 | 32.8B (Dense, GQA 64Q/8KV) |
| VRAM | **BF16: ~66GB** (A100 80GB 적합) |
| 컨텍스트 | 32K 기본 / YaRN으로 131K 확장 |
| 라이선스 | Apache 2.0 |
| SGLang | 공식 지원 (`--reasoning-parser qwen3`) |
| 언어 | 119개 언어 (한국어 포함) |

**듀얼 모드:**

- **Thinking 모드**: 복잡한 추론이 필요한 경우 (예: 시나리오 분석)
- **Non-thinking 모드**: 빠른 RP 대화 응답 (`/no_think` 프리픽스)

**RP 권장 설정 (Non-thinking):**

```
Temperature: 0.7
TopP: 0.8
TopK: 20
MinP: 0
```

**장점:** 공식적으로 "creative writing, role-playing, multi-turn dialogues"에 우수하다고 명시. RP 파인튜닝 없이도 프롬프트만으로 높은 RP 품질.

---

### 5.5 Sao10K/L3.3-70B-Euryale-v2.3

> **영어 RP 최강자. 한국어 지원은 제한적.**

| 항목 | 상세 |
|---|---|
| HuggingFace | [Sao10K/L3.3-70B-Euryale-v2.3](https://huggingface.co/Sao10K/L3.3-70B-Euryale-v2.3) |
| 파라미터 | 70B (Dense) |
| 베이스 | Llama 3.3 70B Instruct |
| VRAM | INT4: ~40GB |
| 컨텍스트 | 131K (출력 16K 제한) |
| 라이선스 | Llama 3.3 Community License |

**장점:** 공간 인지력, 창의적 추론, 스토리텔링에서 커뮤니티 최고 평가. 131K 컨텍스트.

**한계:** Llama 3.3 베이스의 한국어 지원 제한적 ("서비스 가능하지만 네이티브 수준은 아님"). 한국어 RP에는 Qwen 계열이 더 적합.

---

### 5.6 CoSER-Llama-3.1-70B

> **문학 기반 RP 최강. 771편 소설의 17,966 캐릭터로 학습.**

| 항목 | 상세 |
|---|---|
| HuggingFace | [Neph0s/CoSER-Llama-3.1-70B](https://huggingface.co/Neph0s/CoSER-Llama-3.1-70B) |
| 파라미터 | 70B |
| VRAM | INT4: ~35GB |
| 라이선스 | Llama 3.1 Community License |

**장점:** 캐릭터 일관성 최고 수준. GPT-4o와 비교 가능한 RP 품질.

**한계:** 영어 문학 작품 기반 학습 → 한국어 RP 품질 낮음.

---

## 6. Tier 3 — 한국어 네이티브 범용 모델

> 주의: 이 카테고리의 모델들은 한국어 품질은 최고이나, RP 파인튜닝이 되어 있지 않아 시스템 프롬프트로 RP를 유도해야 한다.

### 6.1 LGAI-EXAONE/EXAONE-4.0-32B

| 항목 | 상세 |
|---|---|
| HuggingFace | [LGAI-EXAONE/EXAONE-4.0-32B](https://huggingface.co/LGAI-EXAONE/EXAONE-4.0-32B) |
| 파라미터 | 30.95B (하이브리드 어텐션, GQA) |
| VRAM | BF16: ~64GB (A100 80GB 적합) |
| 한국어 | 네이티브 이중언어 (한국어 + 영어 + 스페인어). 어휘의 ~50%가 한국어 |
| 컨텍스트 | 131K 토큰 |
| 벤치마크 | KMMLU-Pro: 67.7. 32B 모델 중 최고 Intelligence Index |
| 라이선스 | **EXAONE AI Model License 1.2 - NC (비상업용)** |

> **중요:** 비상업용 라이선스(NC)로 상업적 챗봇 서비스에 사용 불가. 연구/프로토타입 용도로만 활용 가능.

### 6.2 LGAI-EXAONE/EXAONE-3.5-32B-Instruct

| 항목 | 상세 |
|---|---|
| HuggingFace | [LGAI-EXAONE/EXAONE-3.5-32B-Instruct](https://huggingface.co/LGAI-EXAONE/EXAONE-3.5-32B-Instruct) |
| 한국어 | KoMT-Bench: **8.05** (Qwen 2.5: 7.75 대비 우수) |
| 라이선스 | **EXAONE AI Model License 1.1 - NC (비상업용)** |

### 6.3 Bllossom/llama-3-Korean-Bllossom-70B

| 항목 | 상세 |
|---|---|
| HuggingFace | [Bllossom/llama-3-Korean-Bllossom-70B](https://huggingface.co/Bllossom/llama-3-Korean-Bllossom-70B) |
| 파라미터 | 71B |
| 베이스 | Llama 3 70B + 한국어 어휘 30,000개 확장 |
| 개발 | MLPLab (서울과기대) + Teddysum + 연세대 |
| 한국어 | 최우수 — 한국어 컨텍스트 처리 25% 향상. LogicKor 한국어 오픈소스 1위급 |
| VRAM | INT4: ~40GB |
| 컨텍스트 | **8K (제한적)** |
| 라이선스 | Llama 3 Community License |

**장점:** 한국어 문화 이해 최고. 언어학자 감수 데이터로 학습. NAACL2024/LREC-COLING2024 발표.

**한계:** Llama 3 기반으로 컨텍스트 8K 제한 (긴 RP 대화에 부적합). RP 파인튜닝 없음.

### 6.4 Upstage Solar-Open-100B

| 항목 | 상세 |
|---|---|
| HuggingFace | [upstage/Solar-Open-100B](https://huggingface.co/upstage/Solar-Open-100B) |
| 파라미터 | 102.6B 총 / **12B 활성** (MoE, 129 experts, top-8) |
| 사전학습 | 19.7T 토큰 (한국어 1.1T 토큰 포함) |
| 한국어 | KMMLU 73.0%, Ko-IFEval 87.5% |
| 컨텍스트 | 128K 토큰 |
| VRAM | **4xA100 80GB 최소** (단일 A100 부적합) |
| 라이선스 | Upstage Solar License (상업 사용 시 검토 필요) |

> **중요:** 단일 A100 80GB에 올릴 수 없음. 멀티 GPU 환경에서만 사용 가능.

### 6.5 Elice Korean-Qwen2.5-72B-Instruct

| 항목 | 상세 |
|---|---|
| 파라미터 | 72B |
| 개발 | Elice (한국 EdTech 기업) |
| 한국어 | 언어 전환 현상 ~0% (다국어 모델의 고질적 문제 해결) |
| 학습 | 18T 토큰 |
| 라이선스 | Apache 2.0 |

**장점:** 한국어 응답 중 갑작스런 영어 전환이 거의 없음 (language switching 해결).

**한계:** RP 파인튜닝 없음. Elice Cloud 배포 중심으로 셀프호스팅 유연성 확인 필요.

---

## 7. Tier 4 — 신규 및 예정 모델

### 7.1 Qwen3.5 (2026.02.16 출시, 최신)

| 항목 | 상세 |
|---|---|
| HuggingFace | [Qwen/Qwen3.5-397B-A17B](https://huggingface.co/Qwen/Qwen3.5-397B-A17B) |
| 파라미터 | 397B 총 / 17B 활성 (Sparse MoE + Hybrid Linear Attention) |
| 컨텍스트 | **1M 토큰** |
| 언어 | 201개 언어 (한국어 포함) |
| 라이선스 | Apache 2.0 |

**현재 상태:** 플래그십 397B 모델만 공개. **72B, 14B, 7B 소형 변형 모델 공개 예정.**

> **전망:** Qwen3.5-72B가 출시되면 차세대 한국어 RP 파인튜닝의 베이스 모델이 될 가능성 높음. allura-org 등 커뮤니티의 RP Ink 시리즈가 Qwen3.5 기반으로 업데이트될 것으로 예상.

### 7.2 MiniMax M2-her (2026.01.27 출시)

| 항목 | 상세 |
|---|---|
| 개발 | MiniMax |
| 특징 | RP 전용 설계. 100턴 장시간 RP 세션에서 1위 |
| 기능 | rich message roles, 예시 대화 학습, 로어 일관성 유지 |
| 접근 | **API 전용** (MiniMax Cloud / OpenRouter) |

**참고:** 로컬 배포 불가. 외부 API 모델로 `llm_models` 테이블에 등록하여 Premium 옵션으로 제공 가능.

### 7.3 Kakao Kanana-2 (2026.01 출시)

| 항목 | 상세 |
|---|---|
| 개발 | Kakao |
| 종류 | Base, Instruct, Thinking, Mid-training (4가지 변형) |
| 한국어 | 강한 한영 이중언어 (6개 언어 지원) |
| 특징 | 에이전트/도구 사용 특화 |
| 라이선스 | 오픈소스 |

**한계:** 에이전트/도구 사용 중심 설계로 RP에 직접 활용하기 어려움. RP 커뮤니티 파인튜닝이 나오면 고려 가능.

---

## 8. 추천 배포 전략

### Strategy A: 한국어 RP 최적 (1순위 추천)

```
모델: developer-lunark/Qwen3-30B-Korean-Roleplay
정밀도: BF16 (양자화 불필요)
VRAM: ~60GB / A100 80GB
추론 속도: 매우 빠름 (MoE, 3.3B 활성)
```

**적합한 경우:**
- 한국어 전용 서비스
- Live2D 감정 연동이 핵심 기능
- 빠른 응답 속도 우선 (SSE 스트리밍)
- 동시 접속자 처리량 극대화

### Strategy B: 범용 밸런스

```
모델: Qwen/Qwen3-32B (Non-thinking 모드)
정밀도: BF16 (양자화 불필요)
VRAM: ~66GB / A100 80GB
```

**적합한 경우:**
- 한국어 + 영어 다국어 지원 필요
- RP 외 범용 대화도 지원
- thinking 모드로 복잡한 시나리오 분석 필요

### Strategy C: 최고 RP 품질

```
모델: allura-org/Qwen2.5-72b-RP-Ink
정밀도: INT4 AWQ
VRAM: ~40GB / A100 80GB
```

**적합한 경우:**
- 영어/한국어 모두에서 최고 수준 RP 품질
- 캐릭터 일관성이 최우선
- 양자화로 인한 약간의 품질 손실 수용 가능

### Strategy D: 최저 비용

```
모델: developer-lunark/kaidol-qwen3-14b-korean-rp
정밀도: BF16
VRAM: ~28GB / A100 80GB
```

**적합한 경우:**
- 프로토타입/테스트 단계
- 비용 최소화 (GPU 시간 절약)
- 단순한 캐릭터 대화 위주

---

## 9. 멀티모델 전략

프로젝트의 `llm_models` 테이블 기반 동적 라우팅을 활용하여 여러 모델을 동시에 제공할 수 있다.

### 9.1 추천 모델 구성

| display_name | model_id | provider | tier | credit_per_1k | 용도 |
|---|---|---|---|---|---|
| 한국어 RP 전문 | `developer-lunark/Qwen3-30B-Korean-Roleplay` | runpod | economy | 2 | 기본값. 빠른 한국어 RP |
| 크리에이티브 | `allura-org/Qwen2.5-72b-RP-Ink` | runpod | premium | 8 | 최고 RP 품질 |
| 밸런스 | `Qwen/Qwen3-32B` | runpod | standard | 5 | 범용 + 한국어 |
| GPT-4o | `gpt-4o` | openai | premium | 10 | 외부 API |
| Claude Sonnet | `claude-sonnet-4-5-20250929` | anthropic | premium | 10 | 외부 API |

### 9.2 RunPod 엔드포인트 구성

멀티모델 전략 시 RunPod에서 모델별 별도 엔드포인트를 생성하거나, 단일 엔드포인트에서 모델을 전환할 수 있다.

**옵션 1: 모델별 별도 엔드포인트 (추천)**

```
엔드포인트 A → Qwen3-30B-Korean-Roleplay (기본)
엔드포인트 B → Qwen2.5-72B-RP-Ink INT4 (프리미엄)
엔드포인트 C → Qwen3-32B (밸런스)
```

각 엔드포인트의 `RUNPOD_ENDPOINT_ID`를 `llm_models.metadata_` JSONB에 저장하여 `inference_client.py`에서 동적 라우팅.

**옵션 2: 단일 엔드포인트 + 모델 전환**

SGLang의 `--model-path` 파라미터로 단일 서버에서 하나의 모델만 로드. 모델 전환 시 재시작 필요 → 프로토타입에서는 비추천.

### 9.3 비용 추정 (RunPod Serverless)

| 모델 | GPU 시간 단가 | 토큰/초 (추정) | 1K 토큰 비용 (추정) |
|---|---|---|---|
| Qwen3-30B-Korean-RP (MoE, BF16) | ~$0.59/hr | ~80-120 tok/s | ~$0.005 |
| Qwen3-32B (BF16) | ~$0.59/hr | ~30-50 tok/s | ~$0.012 |
| Qwen2.5-72B RP Ink (INT4) | ~$0.59/hr | ~20-35 tok/s | ~$0.017 |

> 참고: MoE 모델(3.3B 활성)은 Dense 모델 대비 2-4배 빠른 토큰 생성으로 GPU 시간 대비 효율이 훨씬 높다.

---

## 10. RunPod 배포 가이드

### 10.1 handler.py 수정 예시

현재 `infra/runpod/handler.py`의 모델 설정을 변경:

```python
# 기존
MODEL_ID = "meta-llama/Meta-Llama-3-70B-Instruct"
QUANTIZATION = "awq"

# 변경 (Strategy A)
MODEL_ID = "developer-lunark/Qwen3-30B-Korean-Roleplay"
QUANTIZATION = ""  # BF16, 양자화 불필요

# 변경 (Strategy C)
MODEL_ID = "allura-org/Qwen2.5-72b-RP-Ink"
QUANTIZATION = "awq"  # INT4 AWQ 필수
```

### 10.2 SGLang 실행 옵션

```bash
# Qwen3-30B-Korean-Roleplay (MoE)
python -m sglang.launch_server \
  --model-path developer-lunark/Qwen3-30B-Korean-Roleplay \
  --port 30000 \
  --host 0.0.0.0 \
  --tp 1

# Qwen3-32B (Non-thinking 모드 권장)
python -m sglang.launch_server \
  --model-path Qwen/Qwen3-32B \
  --port 30000 \
  --host 0.0.0.0 \
  --tp 1 \
  --reasoning-parser qwen3

# Qwen2.5-72B RP Ink (INT4)
python -m sglang.launch_server \
  --model-path allura-org/Qwen2.5-72b-RP-Ink \
  --port 30000 \
  --host 0.0.0.0 \
  --tp 1 \
  --quantization awq
```

### 10.3 감정 태그 파싱 (Qwen3-30B-Korean-Roleplay 사용 시)

모델 출력에서 감정 태그를 파싱하여 Live2D에 전달하는 로직이 필요하다:

```python
def parse_emotion_tag(response: str) -> tuple[str, str]:
    """모델 응답에서 텍스트와 감정 태그를 분리."""
    if "|||emotion:" in response:
        text, emotion_part = response.rsplit("|||emotion:", 1)
        emotion = emotion_part.strip()
        return text.strip(), emotion
    return response, "neutral"
```

### 10.4 llm_models 테이블 등록

```sql
-- Qwen3-30B-Korean-Roleplay 등록
INSERT INTO llm_models (
    id, provider, model_id, display_name,
    input_cost_per_1m, output_cost_per_1m,
    max_context_length, tier, credit_per_1k_tokens,
    is_active, is_adult_only, metadata_
) VALUES (
    gen_random_uuid(), 'runpod',
    'developer-lunark/Qwen3-30B-Korean-Roleplay',
    '한국어 RP 전문 (Qwen3-30B)',
    0.10, 0.20,
    131072, 'economy', 2,
    true, false,
    '{"endpoint_id": "<RUNPOD_ENDPOINT_ID>", "emotion_tags": true}'::jsonb
);
```

---

## 11. 주요 동향 및 참고사항

### 11.1 시장 동향 (2026.02 기준)

| 동향 | 설명 |
|---|---|
| Qwen 생태계 지배 | Qwen2.5/3 기반 RP 파인튜닝이 오픈소스 RP 시장의 주류 |
| MoE 모델 부상 | Solar Open, K-EXAONE, Qwen3-30B-A3B 등 MoE 모델이 비용 효율성에서 우위 |
| 한국어 RP 파인튜닝 등장 | developer-lunark 시리즈로 한국어 + RP 동시 특화 모델 첫 등장 |
| Llama 4 한국어 미지원 | 공식 12개 언어에 한국어 없음 → 한국어 RP에 부적합 |
| EXAONE/Solar 라이선스 장벽 | 한국 국산 최고 모델들이 비상업용이거나 멀티 GPU 필요 |
| RP 벤치마크 표준화 시작 | FURINA-Bench가 최초의 체계적 RP 평가 벤치마크로 부상 |
| Qwen3.5 소형 모델 대기 | 72B/14B/7B 변형 출시 시 RP 파인튜닝 생태계 재편 예상 |

### 11.2 라이선스 요약

| 라이선스 | 상업 사용 | 해당 모델 |
|---|---|---|
| **Apache 2.0** | 자유 사용 | Qwen3 계열, Qwen2.5-32B RP Ink, EVA 계열, Qwen3-30B-Korean-RP |
| **Qwen License** | 조건부 (확인 필요) | Qwen2.5-72B 기반 모델 |
| **Llama 3.x Community** | MAU 7억 미만 가능 | Euryale, Sapphira, Joyous, Bllossom, CoSER |
| **EXAONE NC** | 불가 (비상업용) | EXAONE 3.5, EXAONE 4.0 |
| **Solar License** | 조건부 (검토 필요) | Solar Open 100B |
| **Gemma ToU** | 조건부 (제한 존재) | Gemma 3 계열 |

### 11.3 양자화 영향

| 정밀도 | 품질 영향 | 적합 모델 |
|---|---|---|
| BF16/FP16 | 없음 (원본 품질) | 32B 이하 모델 (A100 80GB에서) |
| INT8 | ~2-3% 저하 | 32B-72B 모델 |
| INT4 (AWQ/GPTQ) | ~5-10% 저하 | 70B+ 모델 (A100 80GB에서) |

> **원칙:** 가능하면 양자화 없이 BF16으로 배포. 72B+ 모델은 INT4가 불가피하므로, 양자화 없는 32B 모델 vs INT4 72B 모델 비교 검토 필요.

### 11.4 주의사항

1. **한국어 RP 학습 데이터 부족:** 영어 RP 데이터에 비해 한국어 RP 학습 데이터가 절대적으로 부족. developer-lunark 모델이 유일한 한국어 RP 전용 파인튜닝.
2. **MoE 모델의 KV 캐시:** MoE 모델은 활성 파라미터는 적지만 전체 파라미터를 메모리에 올려야 하므로, VRAM 사용량은 활성 파라미터보다 높음.
3. **SGLang RadixAttention:** 동일 페르소나의 시스템 프롬프트가 캐시되어 멀티턴 RP 대화에서 효율적. RP 챗봇에 매우 유리한 최적화.
4. **Qwen3.5 소형 모델 대기:** 현재 397B만 공개. 72B 출시 시 재평가 필요.

---

## 12. 출처

### 모델 HuggingFace 페이지

- [developer-lunark/Qwen3-30B-Korean-Roleplay](https://huggingface.co/developer-lunark/Qwen3-30B-Korean-Roleplay)
- [developer-lunark/kaidol-qwen3-14b-korean-rp](https://huggingface.co/developer-lunark/kaidol-qwen3-14b-korean-rp)
- [allura-org/Qwen2.5-72b-RP-Ink](https://huggingface.co/allura-org/Qwen2.5-72b-RP-Ink)
- [allura-org/Qwen2.5-32b-RP-Ink](https://huggingface.co/allura-org/Qwen2.5-32b-RP-Ink)
- [allura-org/Llama-3.3-70B-Joyous](https://huggingface.co/allura-org/Llama-3.3-70B-Joyous)
- [EVA-UNIT-01/EVA-Qwen2.5-72B](https://huggingface.co/EVA-UNIT-01/EVA-Qwen2.5-72B)
- [EVA-UNIT-01/EVA-Qwen2.5-32B-v0.2](https://huggingface.co/EVA-UNIT-01/EVA-Qwen2.5-32B-v0.2)
- [Qwen/Qwen3-32B](https://huggingface.co/Qwen/Qwen3-32B)
- [Qwen/Qwen3-30B-A3B](https://huggingface.co/Qwen/Qwen3-30B-A3B)
- [Qwen/Qwen3.5-397B-A17B](https://huggingface.co/Qwen/Qwen3.5-397B-A17B)
- [Sao10K/L3.3-70B-Euryale-v2.3](https://huggingface.co/Sao10K/L3.3-70B-Euryale-v2.3)
- [Neph0s/CoSER-Llama-3.1-70B](https://huggingface.co/Neph0s/CoSER-Llama-3.1-70B)
- [LGAI-EXAONE/EXAONE-4.0-32B](https://huggingface.co/LGAI-EXAONE/EXAONE-4.0-32B)
- [LGAI-EXAONE/EXAONE-3.5-32B-Instruct](https://huggingface.co/LGAI-EXAONE/EXAONE-3.5-32B-Instruct)
- [LGAI-EXAONE/K-EXAONE-236B-A23B](https://huggingface.co/LGAI-EXAONE/K-EXAONE-236B-A23B)
- [Bllossom/llama-3-Korean-Bllossom-70B](https://huggingface.co/Bllossom/llama-3-Korean-Bllossom-70B)
- [upstage/Solar-Open-100B](https://huggingface.co/upstage/Solar-Open-100B)

### 리더보드 및 벤치마크

- [Open Ko-LLM Leaderboard](https://huggingface.co/spaces/upstage/open-ko-llm-leaderboard)
- [OpenRouter Roleplay Rankings](https://openrouter.ai/rankings/roleplay)
- [FURINA-Bench (RP 평가 벤치마크)](https://openreview.net/forum?id=TjTuObGe27)

### 커뮤니티 및 가이드

- [Best Open Source LLM for Korean (SiliconFlow)](https://www.siliconflow.com/articles/en/best-open-source-llm-for-korean)
- [Best AI RP & LLMs for Roleplay 2026](https://nutstudio.imyfone.com/llm-tips/best-llm-for-roleplay/)
- [Best LLMs for RP 2026 (VisionVix)](https://visionvix.com/best-llm-for-rp/)
- [SillyTavern VRAM Guide 2026](https://redstapler.co/how-much-vram-do-you-actually-need-for-sillytavern-in-2026/)
- [Awesome Korean LLM (GitHub)](https://github.com/NomaDamas/awesome-korean-llm)
- [SGLang Supported Models](https://docs.sglang.ai/supported_models/generative_models.html)
- [RunPod SGLang Worker (GitHub)](https://github.com/runpod-workers/worker-sglang)
- [RunPod SGLang Performance Blog](https://www.runpod.io/blog/supercharge-llms-with-sglang)

### 뉴스 및 발표

- [Alibaba Launches Qwen 3.5 (Dataconomy, 2026.02.17)](https://dataconomy.com/2026/02/17/alibaba-launches-qwen-3-5-ai-model-claims-outperformance-of-us-rivals/)
- [LG K-EXAONE Breaks into Global Top 10 (Korea Herald)](https://www.koreaherald.com/article/10652980)
- [Upstage Solar Korean Fluency (Upstage Blog)](https://www.upstage.ai/blog/en/experience-stronger-korean-fluency-in-the-new-solar-llms)
- [Kakao Kanana-2 Open Source Release (Korea Times)](https://www.koreatimes.co.kr/business/tech-science/20260120/kakao-updates-kanana-2-releases-4-open-source-models)
