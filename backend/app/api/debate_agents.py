from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_developer
from app.models.debate_agent import DebateAgent
from app.models.user import User
from app.schemas.debate_agent import AgentCreate, AgentResponse, AgentUpdate, AgentVersionResponse
from app.services.debate_agent_service import DebateAgentService
from app.services.debate_ws_manager import WSConnectionManager

router = APIRouter()


def _agent_response(agent: DebateAgent) -> AgentResponse:
    """AgentResponse에 is_connected 플래그를 추가하여 반환."""
    resp = AgentResponse.model_validate(agent)
    if agent.provider == "local":
        manager = WSConnectionManager.get_instance()
        resp.is_connected = manager.is_connected(agent.id)
    return resp


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    user: User = Depends(require_developer),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 생성. developer 이상 역할 필요."""
    service = DebateAgentService(db)
    try:
        agent = await service.create_agent(data, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _agent_response(agent)


@router.get("/me", response_model=list[AgentResponse])
async def get_my_agents(
    user: User = Depends(require_developer),
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


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DebateAgentService(db)
    agent = await service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return _agent_response(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    user: User = Depends(require_developer),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 수정. 프롬프트 변경 시 새 버전 자동 생성."""
    service = DebateAgentService(db)
    try:
        agent = await service.update_agent(agent_id, data, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _agent_response(agent)


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
async def get_agent_versions(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DebateAgentService(db)
    versions = await service.get_agent_versions(agent_id)
    return [AgentVersionResponse.model_validate(v) for v in versions]
