# agent_service.py 모듈 명세

**파일 경로:** `backend/app/services/debate/agent_service.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

에이전트(AI 토론 참가자) 전체 생명주기를 관리한다. 생성·수정·삭제, ELO 및 전적 갱신, 랭킹/갤러리/H2H 조회, 버전 이력 관리를 담당한다. 같은 파일에 `DebateTemplateService`도 포함되어 있으며, 템플릿 기반 에이전트 생성 시 커스터마이징 검증과 프롬프트 조립을 맡는다.

---

## 주요 상수

| 상수 | 값 | 설명 |
|---|---|---|
| `_TIER_THRESHOLDS` | `[(2050,"Master"),(1900,"Diamond"),(1750,"Platinum"),(1600,"Gold"),(1450,"Silver"),(1300,"Bronze")]` | ELO → 티어 변환 기준 (내림차순) |
| `_INJECTION_PATTERNS` | 정규식 | free_text 입력의 프롬프트 인젝션 탐지 패턴 |

---

## 모듈 수준 함수

### `get_tier_from_elo(elo: int) -> str`
`_TIER_THRESHOLDS`를 순회해 ELO에 해당하는 티어 문자열 반환. 모든 임계값 미달 시 `"Iron"` 반환.

### `get_latest_version(db: AsyncSession, agent_id) -> DebateAgentVersion | None`
에이전트의 `version_number` 기준 최신 버전 조회. 클래스 외부(`engine.py`, `matching_service.py`)에서도 직접 사용하는 standalone 함수.

---

## DebateAgentService

생성자: `__init__(self, db: AsyncSession)`

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `create_agent` | `(data: AgentCreate, user: User) -> DebateAgent` | 에이전트 생성. 3경로: 템플릿 기반 / BYOK / 로컬. `DebateAgentVersion` v1 자동 생성 |
| `update_agent` | `(agent_id: str, data: AgentUpdate, user: User) -> DebateAgent` | 소유권 검사 후 수정. 프롬프트/커스터마이징 변경 시 새 버전 자동 생성. 이름 변경 쿨다운 적용 |
| `get_agent` | `(agent_id: str) -> DebateAgent \| None` | 단일 에이전트 조회 |
| `get_my_agents` | `(user: User) -> list[DebateAgent]` | 소유자 기준 목록 (created_at DESC) |
| `get_agent_versions` | `(agent_id: str) -> list[DebateAgentVersion]` | 버전 이력 (version_number DESC) |
| `get_latest_version` | `(agent_id: str) -> DebateAgentVersion \| None` | 최신 버전 조회 (standalone 함수 위임) |
| `get_ranking` | `(limit, offset, search, tier, season_id) -> tuple[list[dict], int]` | ELO 기준 글로벌 랭킹. `season_id` 있으면 `debate_agent_season_stats` 기준, 없으면 누적 ELO 기준 |
| `get_my_ranking` | `(user: User) -> list[dict]` | 내 에이전트 순위. 전체 한 번 조회 후 rank_map 계산으로 N+1 방지 |
| `delete_agent` | `(agent_id: str, user: User) -> None` | 소유자 확인 + 진행 중 매치 없을 때만 삭제. 버전 먼저 삭제 후 FK 안전 제거 |
| `update_elo` | `(agent_id, new_elo, result_type, version_id) -> dict \| None` | ELO·전적 갱신 + 승급전/강등전 트리거. `result_type`: `'win'`/`'loss'`/`'draw'`. 시리즈 생성 시 dict 반환, 없으면 None |
| `get_head_to_head` | `(agent_id: str, limit: int = 5) -> list[dict]` | 상대별 전적 집계. agent_a/b 양측 UNION ALL 후 opponent_id 기준 집계 |
| `get_gallery` | `(sort: str, skip: int, limit: int) -> tuple[list, int]` | `is_profile_public=True & is_active=True` 에이전트 공개 갤러리. sort: `elo`/`wins`/`recent` |
| `clone_agent` | `(source_id: str, user: User, name: str) -> DebateAgent` | `is_system_prompt_public=True` 에이전트 복제. BYOK 에이전트는 api_key 없이 직접 DB 삽입 |

### `update_elo` 호출 흐름

```
현재 에이전트 조회
→ elo_rating + wins/losses/draws 갱신 dict 구성
→ active_series_id 없으면 DebatePromotionService.check_and_trigger() 호출
  → 시리즈 미생성 + 강등 방향이면 tier_protection_count 감소
→ UPDATE debate_agents
→ version_id 있으면 UPDATE debate_agent_versions 전적
→ 시리즈 생성 정보 dict 반환 (없으면 None)
```

---

## DebateTemplateService

생성자: `__init__(self, db: AsyncSession)`

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `list_active_templates` | `() -> list[DebateAgentTemplate]` | 활성 템플릿 목록 (sort_order ASC) |
| `list_all_templates` | `() -> list[DebateAgentTemplate]` | 전체 템플릿 (관리자용, 비활성 포함) |
| `get_template` | `(template_id: str \| UUID) -> DebateAgentTemplate \| None` | ID로 단일 조회 |
| `get_template_by_slug` | `(slug: str) -> DebateAgentTemplate \| None` | slug로 단일 조회 |
| `validate_customizations` | `(template, customizations, enable_free_text) -> dict` | 슬라이더 범위·셀렉트 옵션 검증, 누락 키는 기본값 보충, free_text 인젝션 패턴 스캔 |
| `assemble_prompt` | `(template, customizations: dict) -> str` | `{customization_block}` 치환으로 최종 시스템 프롬프트 생성 |
| `create_template` | `(data: AgentTemplateCreate) -> DebateAgentTemplate` | 템플릿 생성 (superadmin) |
| `update_template` | `(template_id, data: AgentTemplateUpdate) -> DebateAgentTemplate` | 템플릿 수정 (superadmin) |

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `app.core.encryption` | `encrypt_api_key` — BYOK API 키 Fernet 암호화 |
| `app.core.config` | `settings.agent_name_change_cooldown_days` |
| `app.models.debate_agent` | `DebateAgent`, `DebateAgentVersion`, `DebateAgentSeasonStats` |
| `app.models.debate_agent_template` | `DebateAgentTemplate` |
| `app.models.debate_match` | `DebateMatch` (삭제 전 진행 중 매치 확인용) |
| `app.models.user` | `User` |
| `app.schemas.debate_agent` | `AgentCreate`, `AgentUpdate`, `AgentTemplateCreate`, `AgentTemplateUpdate` |
| `app.services.debate.promotion_service` | `DebatePromotionService`, `TIER_ORDER` (지연 임포트) |

---

## 호출 흐름

```
API 라우터 (api/debate_agents.py)
  → DebateAgentService.create_agent()
      → DebateTemplateService.validate_customizations()
      → DebateTemplateService.assemble_prompt()
      → DebateAgent + DebateAgentVersion INSERT

매치 완료 후 (services/debate/engine.py)
  → DebateAgentService.update_elo()
      → DebatePromotionService.check_and_trigger()
          → create_promotion_series() 또는 create_demotion_series()

services/debate/matching_service.py
  → get_latest_version() (standalone) — 매치 생성 시 버전 스냅샷 연결
```

---

## 에러 처리

| 상황 | 예외 | 설명 |
|---|---|---|
| 에이전트 미존재 | `ValueError("Agent not found")` | HTTP 404로 변환 |
| 소유권 불일치 | `PermissionError("Permission denied")` | HTTP 403으로 변환 |
| 이름 변경 쿨다운 미경과 | `ValueError("이름은 N일에...")` | HTTP 400 |
| 진행 중 매치 있을 때 삭제 | `ValueError("진행 중인 매치가...")` | HTTP 400 |
| BYOK API 키 누락 | `ValueError("API key is required...")` | HTTP 400 |
| 시스템 프롬프트 누락 | `ValueError("System prompt is required...")` | HTTP 400 |
| 비공개 에이전트 클론 | `PermissionError("이 에이전트는 복제 불가능합니다")` | HTTP 403 |
| 커스터마이징 검증 실패 | `ValueError(구체적 메시지)` | HTTP 400 |

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
