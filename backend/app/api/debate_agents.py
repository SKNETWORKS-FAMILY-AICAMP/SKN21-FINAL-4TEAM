from fastapi import APIRouter, Depends, HTTPException, Query, status
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


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse | AgentPublicResponse:
    """소유자는 customizations 포함 전체 응답, 비소유자는 공개 응답만 반환."""
    service = DebateAgentService(db)
    agent = await service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if agent.owner_id == user.id:
        return _agent_response(agent)
    return AgentPublicResponse.model_validate(agent)


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
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
