from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.user import User
from app.schemas.debate_agent import (
    AgentTemplateAdminResponse,
    AgentTemplateCreate,
    AgentTemplateUpdate,
)
from app.schemas.debate_topic import TopicUpdate
from app.services.debate_match_service import DebateMatchService
from app.services.debate_template_service import DebateTemplateService
from app.services.debate_topic_service import DebateTopicService

router = APIRouter()


@router.get("/stats")
async def debate_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """토론 플랫폼 전체 통계."""
    agents_count = (await db.execute(select(func.count(DebateAgent.id)))).scalar() or 0
    topics_count = (await db.execute(select(func.count(DebateTopic.id)))).scalar() or 0
    matches_total = (await db.execute(select(func.count(DebateMatch.id)))).scalar() or 0
    matches_completed = (await db.execute(
        select(func.count(DebateMatch.id)).where(DebateMatch.status == "completed")
    )).scalar() or 0
    matches_in_progress = (await db.execute(
        select(func.count(DebateMatch.id)).where(DebateMatch.status == "in_progress")
    )).scalar() or 0

    return {
        "agents_count": agents_count,
        "topics_count": topics_count,
        "matches_total": matches_total,
        "matches_completed": matches_completed,
        "matches_in_progress": matches_in_progress,
    }


@router.patch("/topics/{topic_id}")
async def update_topic(
    topic_id: str,
    data: TopicUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """토픽 수정 (관리자)."""
    service = DebateTopicService(db)
    try:
        topic = await service.update_topic(topic_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "id": str(topic.id),
        "title": topic.title,
        "status": topic.status,
        "updated_at": topic.updated_at,
    }


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(
    topic_id: str,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """토픽 삭제 (superadmin 전용, 매치가 없는 경우만)."""
    service = DebateTopicService(db)
    try:
        await service.delete_topic(topic_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/matches")
async def list_all_matches(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 매치 목록 (관리자)."""
    service = DebateMatchService(db)
    items, total = await service.list_matches(status=status_filter, skip=skip, limit=limit)
    return {"items": items, "total": total}


# ---------------------------------------------------------------------------
# 템플릿 관리 엔드포인트
# ---------------------------------------------------------------------------

@router.get("/templates", response_model=list[AgentTemplateAdminResponse])
async def list_templates_admin(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 템플릿 목록 (비활성 포함, base_system_prompt 포함)."""
    service = DebateTemplateService(db)
    templates = await service.list_all_templates()
    return [AgentTemplateAdminResponse.model_validate(t) for t in templates]


@router.get("/templates/{template_id}", response_model=AgentTemplateAdminResponse)
async def get_template_admin(
    template_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """템플릿 상세 조회 (base_system_prompt 포함)."""
    service = DebateTemplateService(db)
    template = await service.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return AgentTemplateAdminResponse.model_validate(template)


@router.post(
    "/templates",
    response_model=AgentTemplateAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    data: AgentTemplateCreate,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """템플릿 생성 (superadmin 전용)."""
    service = DebateTemplateService(db)
    try:
        template = await service.create_template(data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return AgentTemplateAdminResponse.model_validate(template)


@router.patch("/templates/{template_id}", response_model=AgentTemplateAdminResponse)
async def update_template(
    template_id: str,
    data: AgentTemplateUpdate,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """템플릿 수정 (superadmin 전용)."""
    service = DebateTemplateService(db)
    try:
        template = await service.update_template(template_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AgentTemplateAdminResponse.model_validate(template)
