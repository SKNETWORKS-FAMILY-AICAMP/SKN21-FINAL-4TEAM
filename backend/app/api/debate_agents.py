import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.debate_agent import DebateAgent
from app.models.user import User
from app.schemas.debate_agent import (
    AgentCreate,
    AgentPublicResponse,
    AgentResponse,
    AgentTemplateResponse,
    AgentUpdate,
    AgentVersionResponse,
)
from app.services.debate_agent_service import DebateAgentService
from app.services.debate_template_service import DebateTemplateService
from app.services.debate_ws_manager import WSConnectionManager

router = APIRouter()


def _classify_provider_error(exc: httpx.HTTPStatusError) -> tuple[str, str]:
    """프로바이더 HTTP 에러를 (error_type, user_message)로 변환.

    각 프로바이더 에러 포맷:
      OpenAI    → body["error"]["code"]:   "invalid_api_key" | "model_not_found"
      Anthropic → body["error"]["type"]:   "authentication_error" | "not_found_error"
      Google    → body["error"]["status"]: "UNAUTHENTICATED" | "NOT_FOUND"
    """
    code = exc.response.status_code
    try:
        body = exc.response.json()
    except Exception:
        body = {}

    err = body.get("error", {})
    err_code = str(err.get("code", ""))        # OpenAI: "invalid_api_key" / "model_not_found"
    err_type = err.get("type", "")             # Anthropic: "authentication_error" / "not_found_error"
    err_status = err.get("status", "")         # Google: "UNAUTHENTICATED" / "NOT_FOUND"
    err_msg = err.get("message", "")

    # ── API 키 문제 ────────────────────────────────────────────────────────
    api_key_signals = (
        code == 401
        or err_code == "invalid_api_key"
        or err_type == "authentication_error"
        or err_status == "UNAUTHENTICATED"
    )
    if api_key_signals:
        return "api_key", "API 키가 올바르지 않습니다."

    # ── 모델 문제 ──────────────────────────────────────────────────────────
    model_signals = (
        code == 404
        or err_code == "model_not_found"
        or err_type == "not_found_error"
        or err_status == "NOT_FOUND"
    )
    if model_signals:
        return "model", "모델을 찾을 수 없습니다. 모델 ID를 확인해주세요."

    # ── 권한 거부 (403) — 키는 유효하나 모델 접근 권한 없음 ───────────────
    if code == 403:
        return "api_key", "접근이 거부되었습니다. API 키 권한을 확인해주세요."

    # ── 400 Bad Request — 메시지로 세부 판별 ──────────────────────────────
    if code == 400:
        lower_msg = err_msg.lower()
        if "model" in lower_msg or "not found" in lower_msg:
            return "model", f"모델 오류: {err_msg[:150]}" if err_msg else "모델 ID를 확인해주세요."
        return "api_key", f"잘못된 요청: {err_msg[:150]}" if err_msg else f"API 오류 ({code})"

    return "other", f"API 오류 ({code})" + (f": {err_msg[:120]}" if err_msg else "")


def _agent_response(agent: DebateAgent) -> AgentResponse:
    """AgentResponse에 is_connected 플래그를 추가하여 반환."""
    resp = AgentResponse.model_validate(agent)
    if agent.provider == "local":
        manager = WSConnectionManager.get_instance()
        resp.is_connected = manager.is_connected(agent.id)
    return resp


@router.get("/templates", response_model=list[AgentTemplateResponse])
async def list_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """활성 에이전트 템플릿 목록 조회. base_system_prompt는 미노출."""
    service = DebateTemplateService(db)
    templates = await service.list_active_templates()
    return [AgentTemplateResponse.model_validate(t) for t in templates]


class AgentTestRequest(BaseModel):
    provider: str
    model_id: str
    api_key: str = ""


@router.post("/test")
async def test_agent_connection(
    data: AgentTestRequest,
    user: User = Depends(get_current_user),
):
    """API 키·모델 ID 유효성 사전 테스트. DB 저장 없음."""
    # local/runpod은 플랫폼 키 사용 — 사용자 측 테스트 불필요
    if data.provider in ("local", "runpod"):
        return {"ok": True}

    if not data.api_key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="API 키를 입력해주세요.")

    from app.services.inference_client import InferenceClient

    client = InferenceClient()
    messages = [{"role": "user", "content": "Say ok"}]

    try:
        result = await asyncio.wait_for(
            client.generate_byok(data.provider, data.model_id, data.api_key, messages, max_tokens=10),
            timeout=15.0,
        )
        return {"ok": True, "model_response": result["content"]}
    except asyncio.TimeoutError:
        return {"ok": False, "error_type": "other", "error": "응답 시간이 초과되었습니다 (15초)"}
    except httpx.HTTPStatusError as exc:
        error_type, error_msg = _classify_provider_error(exc)
        return {"ok": False, "error_type": error_type, "error": error_msg}
    except ValueError as exc:
        return {"ok": False, "error_type": "other", "error": str(exc)[:200]}
    except Exception as exc:
        return {"ok": False, "error_type": "other", "error": f"테스트 중 오류: {str(exc)[:200]}"}


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 생성. 로그인한 사용자 누구나 가능."""
    service = DebateAgentService(db)
    try:
        agent = await service.create_agent(data, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _agent_response(agent)


@router.get("/me", response_model=list[AgentResponse])
async def get_my_agents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 에이전트 목록 조회."""
    service = DebateAgentService(db)
    agents = await service.get_my_agents(user)
    return [_agent_response(a) for a in agents]


@router.get("/ranking")
async def get_ranking(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ELO 글로벌 랭킹 조회."""
    service = DebateAgentService(db)
    return await service.get_ranking(limit=limit, offset=offset)


@router.get("/ranking/my")
async def get_my_ranking(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 에이전트들의 글로벌 랭킹 순위 조회."""
    service = DebateAgentService(db)
    return await service.get_my_ranking(user)


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse | AgentPublicResponse:
    """소유자는 전체 응답, 비소유자는 공개 응답만 반환.
    is_system_prompt_public=True이면 비소유자에게도 최신 버전의 system_prompt 포함.
    """
    service = DebateAgentService(db)
    agent = await service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if agent.owner_id == user.id:
        return _agent_response(agent)

    resp = AgentPublicResponse.model_validate(agent)
    if agent.is_system_prompt_public:
        latest_version = await service.get_latest_version(agent_id)
        if latest_version:
            resp.system_prompt = latest_version.system_prompt
    return resp


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 수정. 프롬프트/커스터마이징 변경 시 새 버전 자동 생성."""
    service = DebateAgentService(db)
    try:
        agent = await service.update_agent(agent_id, data, user)
    except ValueError as exc:
        detail = str(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail) from exc
    return _agent_response(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 삭제. 소유자만 가능(403). 미존재 시 404. 진행 중 매치 있으면 400."""
    service = DebateAgentService(db)
    try:
        await service.delete_agent(agent_id, user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail) from exc


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
async def get_agent_versions(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """버전 히스토리(system_prompt 포함)는 소유자만 조회 가능."""
    service = DebateAgentService(db)
    agent = await service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if agent.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    versions = await service.get_agent_versions(agent_id)
    return [AgentVersionResponse.model_validate(v) for v in versions]
