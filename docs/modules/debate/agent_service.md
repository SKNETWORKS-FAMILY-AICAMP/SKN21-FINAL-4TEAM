# AgentService

> 에이전트(AI 토론 참가자)의 전체 생명주기와 공개 갤러리·랭킹·H2H 통계를 관리하는 서비스 계층

**파일 경로:** `backend/app/services/debate/agent_service.py`
**최종 수정일:** 2026-03-12

---

## 모듈 목적

이 파일에는 두 개의 서비스 클래스가 함께 존재한다.

- **`DebateAgentService`** — 에이전트 생성·수정·삭제, ELO 및 전적 갱신, 랭킹/갤러리/H2H 조회, 버전 이력 관리
- **`DebateTemplateService`** — 관리자 제공 에이전트 템플릿 CRUD, 커스터마이징 검증, 프롬프트 조립

두 클래스는 `DebateAgentService.create_agent()` 내부에서 협력하며, 템플릿 기반 에이전트 생성 흐름을 완성한다.

---

## 주요 상수

| 상수 | 타입 | 값 / 설명 |
|---|---|---|
| `_TIER_THRESHOLDS` | `list[tuple[int, str]]` | `[(2050,"Master"),(1900,"Diamond"),(1750,"Platinum"),(1600,"Gold"),(1450,"Silver"),(1300,"Bronze")]` — ELO → 티어 변환 기준, 내림차순 정렬 |
| `_INJECTION_PATTERNS` | `re.Pattern` | free_text 입력에서 프롬프트 인젝션 의심 패턴 탐지용 정규식 (IM_END, IGNORE ALL PREVIOUS INSTRUCTIONS 등) |

---

## 모듈 수준 함수

### `get_tier_from_elo(elo: int) -> str`

`_TIER_THRESHOLDS`를 순회해 ELO에 해당하는 티어 문자열을 반환한다. 모든 임계값에 미달하면 `"Iron"`을 반환한다. `DebateAgentService.update_elo()` 내부에서 티어 자동 계산에 사용된다.

### `get_latest_version(db: AsyncSession, agent_id) -> DebateAgentVersion | None`

에이전트의 `version_number` 기준 최신 버전을 조회한다. `DebateAgentService.get_latest_version()`이 이 함수를 위임 호출하며, 클래스 외부(`engine.py`, `matching_service.py`)에서도 직접 import해 사용하는 standalone 함수다.

---

## 클래스: DebateAgentService

### 생성자

```python
def __init__(self, db: AsyncSession)
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `db` | `AsyncSession` | SQLAlchemy 비동기 세션. FastAPI `Depends(get_db)`로 주입 |

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `create_agent` | `(data: AgentCreate, user: User) -> DebateAgent` | 에이전트 생성. 3경로(템플릿/BYOK/로컬) 분기 처리. `DebateAgentVersion` v1 자동 생성 |
| `update_agent` | `(agent_id: str, data: AgentUpdate, user: User) -> DebateAgent` | 에이전트 수정. 소유권 검사 후 필드 갱신. 프롬프트·커스터마이징 변경 시 새 버전 자동 생성. 이름 변경 쿨다운 적용 |
| `get_agent` | `(agent_id: str) -> DebateAgent \| None` | ID로 단일 에이전트 조회 |
| `get_my_agents` | `(user: User) -> list[DebateAgent]` | 소유자 기준 에이전트 목록 (created_at DESC) |
| `get_agent_versions` | `(agent_id: str) -> list[DebateAgentVersion]` | 버전 이력 목록 (version_number DESC) |
| `get_latest_version` | `(agent_id: str) -> DebateAgentVersion \| None` | 최신 버전 조회. 모듈 수준 `get_latest_version()` 함수로 위임 |
| `get_ranking` | `(limit: int, offset: int, search: str \| None, tier: str \| None, season_id: str \| None) -> tuple[list[dict], int]` | ELO 기준 글로벌 랭킹 페이지네이션 조회. `season_id` 지정 시 `debate_agent_season_stats` 기준, 미지정 시 누적 ELO 기준 |
| `get_my_ranking` | `(user: User) -> list[dict]` | 내 에이전트들의 전체 순위 반환. 전체 에이전트를 한 번 조회 후 rank_map으로 계산 (N+1 방지) |
| `delete_agent` | `(agent_id: str, user: User) -> None` | 에이전트 삭제. 소유권 확인 + 진행 중 매치 없을 때만 허용. 버전 먼저 삭제 후 FK 안전 제거 |
| `update_elo` | `(agent_id: str, new_elo: int, result_type: str, version_id: str \| None) -> dict \| None` | ELO·전적 갱신 + 승급전/강등전 시리즈 트리거. `result_type`: `'win'` / `'loss'` / `'draw'`. 시리즈 생성 시 시리즈 정보 dict 반환, 없으면 `None` |
| `get_head_to_head` | `(agent_id: str, limit: int = 5) -> list[dict]` | 상대별 전적 집계. agent_a·agent_b 양측 UNION ALL 후 opponent_id 기준 집계 |
| `get_gallery` | `(sort: str = "elo", skip: int = 0, limit: int = 20) -> tuple[list, int]` | `is_profile_public=True & is_active=True` 에이전트 공개 갤러리. `sort`: `"elo"` / `"wins"` / `"recent"` |
| `clone_agent` | `(source_id: str, user: User, name: str) -> DebateAgent` | `is_system_prompt_public=True` 에이전트 복제. BYOK 에이전트는 `api_key=None`으로 직접 DB 삽입, 나머지는 `create_agent()` 재사용 |

---

## 클래스: DebateTemplateService

### 생성자

```python
def __init__(self, db: AsyncSession)
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `db` | `AsyncSession` | SQLAlchemy 비동기 세션 |

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `list_active_templates` | `() -> list[DebateAgentTemplate]` | 활성 템플릿 목록 (sort_order ASC) |
| `list_all_templates` | `() -> list[DebateAgentTemplate]` | 전체 템플릿 (관리자용, 비활성 포함) |
| `get_template` | `(template_id: str \| uuid.UUID) -> DebateAgentTemplate \| None` | ID로 단일 템플릿 조회 |
| `get_template_by_slug` | `(slug: str) -> DebateAgentTemplate \| None` | slug로 단일 템플릿 조회 |
| `validate_customizations` | `(template: DebateAgentTemplate, customizations: dict \| None, enable_free_text: bool = False) -> dict` | 슬라이더 범위·셀렉트 옵션 검증, 누락 키 기본값 보충, free_text 인젝션 패턴 스캔 |
| `assemble_prompt` | `(template: DebateAgentTemplate, customizations: dict) -> str` | `{customization_block}` 자리표시자를 검증된 커스터마이징 텍스트로 치환해 최종 시스템 프롬프트 반환 |
| `create_template` | `(data: AgentTemplateCreate) -> DebateAgentTemplate` | 템플릿 생성 (superadmin 전용) |
| `update_template` | `(template_id: str \| uuid.UUID, data: AgentTemplateUpdate) -> DebateAgentTemplate` | 템플릿 수정 (superadmin 전용) |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `encrypt_api_key` | `app.core.encryption` | BYOK API 키 Fernet 암호화 |
| `settings` | `app.core.config` | `agent_name_change_cooldown_days` 설정값 읽기 (지연 임포트) |
| `DebateAgent` | `app.models.debate_agent` | 에이전트 ORM 모델 |
| `DebateAgentVersion` | `app.models.debate_agent` | 에이전트 버전 ORM 모델 |
| `DebateAgentSeasonStats` | `app.models.debate_agent` | 시즌별 ELO·전적 분리 집계 모델 |
| `DebateAgentTemplate` | `app.models.debate_agent_template` | 에이전트 템플릿 ORM 모델 |
| `DebateMatch` | `app.models.debate_match` | 진행 중 매치 확인용 (지연 임포트, `delete_agent`·`get_head_to_head`) |
| `User` | `app.models.user` | 사용자 ORM 모델 |
| `AgentCreate`, `AgentUpdate` | `app.schemas.debate_agent` | 에이전트 입력 스키마 |
| `AgentTemplateCreate`, `AgentTemplateUpdate` | `app.schemas.debate_agent` | 템플릿 입력 스키마 |
| `DebatePromotionService`, `TIER_ORDER` | `app.services.debate.promotion_service` | 승급전/강등전 트리거 (지연 임포트, `update_elo`) |

---

## 호출 흐름

### 에이전트 생성 흐름

```
API 라우터 (api/debate_agents.py)
  → DebateAgentService.create_agent(data, user)
      ├─ [template_id 있음] DebateTemplateService.get_template()
      │     → DebateTemplateService.validate_customizations()
      │     → DebateTemplateService.assemble_prompt()
      ├─ [local] 기본 프롬프트 사용
      └─ [BYOK] data.system_prompt 직접 사용
      → DebateAgent INSERT
      → DebateAgentVersion(v1) INSERT
```

### ELO 갱신 흐름

```
services/debate/engine.py (매치 완료 후)
  → DebateAgentService.update_elo(agent_id, new_elo, result_type, version_id)
      → DebateAgent 조회 (active_series_id 확인)
      → 전적 업데이트 dict 구성 (wins/losses/draws)
      ├─ [active_series_id 없음]
      │   → DebatePromotionService.check_and_trigger()
      │       → 시리즈 생성 또는 tier_protection_count 감소
      └─ [active_series_id 있음]
          → ELO만 업데이트 (티어 변경 없음)
      → UPDATE debate_agents
      → [version_id 있음] UPDATE debate_agent_versions 전적
      → 시리즈 생성 시 dict 반환, 없으면 None
```

### 랭킹 조회 분기

```
GET /api/agents/ranking?season_id={id}
  → DebateAgentService.get_ranking(season_id=id)
      ├─ [season_id 있음] debate_agent_season_stats JOIN debate_agents 기준 정렬
      └─ [season_id 없음] debate_agents.elo_rating 기준 정렬
```

### H2H 전적 집계 흐름

```
DebateAgentService.get_head_to_head(agent_id, limit)
  → stmt_as_a: agent_a_id = agent_id, opponent = agent_b_id 그룹 집계
  → stmt_as_b: agent_b_id = agent_id, opponent = agent_a_id 그룹 집계
  → UNION ALL → subquery → opponent_id 기준 재집계
  → 상대 에이전트 이름 배치 조회 (N+1 방지)
```

---

## 에러 처리

| 상황 | 예외 | HTTP 변환 |
|---|---|---|
| 에이전트 미존재 | `ValueError("Agent not found")` | 404 |
| 소유권 불일치 | `PermissionError("Permission denied")` | 403 |
| 이름 변경 쿨다운 미경과 | `ValueError("이름은 {N}일에 한 번만 변경할 수 있습니다 ({M}일 후 변경 가능)")` | 400 |
| 진행 중 매치 있을 때 삭제 | `ValueError("진행 중인 매치가 있어 삭제할 수 없습니다.")` | 400 |
| BYOK API 키 누락 | `ValueError("API key is required for non-local providers")` | 400 |
| 시스템 프롬프트 누락 (BYOK) | `ValueError("System prompt is required for API agents")` | 400 |
| 템플릿 미존재 | `ValueError("Template not found")` | 400 |
| 비활성 템플릿 사용 | `ValueError("Template is not active")` | 400 |
| 비공개 에이전트 클론 시도 | `PermissionError("이 에이전트는 복제 불가능합니다")` | 403 |
| 슬라이더 범위 초과 | `ValueError("슬라이더 '{key}' 값 {val}은 {min}~{max} 범위여야 합니다.")` | 400 |
| 허용되지 않은 셀렉트 옵션 | `ValueError("'{key}' 값 '{val}'은 허용된 옵션({list})이 아닙니다.")` | 400 |
| free_text 길이 초과 | `ValueError("추가 지시사항은 {max_len}자를 초과할 수 없습니다.")` | 400 |
| free_text 인젝션 패턴 탐지 | `ValueError("추가 지시사항에 허용되지 않는 패턴이 포함되어 있습니다.")` | 400 |

예외 → HTTP 상태코드 변환은 `api/debate_agents.py` 라우터가 담당한다 (`ValueError` → 400/404, `PermissionError` → 403).

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-12 | 나머지 문서의 형식 레퍼런스 템플릿 역할을 위해 전면 재작성. 모듈 수준 함수 섹션 추가, 에러 처리 표 상세화, 호출 흐름 4개 시나리오로 확장 |
| 2026-03-11 | `services/debate/` 하위로 이동, 실제 코드 기반으로 초기 재작성 |
