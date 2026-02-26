from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_superadmin
from app.models.debate_agent import DebateAgent
from app.models.debate_match import DebateMatch
from app.models.debate_topic import DebateTopic
from app.models.debate_turn_log import DebateTurnLog
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
    search: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 매치 목록 (관리자). 차단된 턴 수 포함. search: 에이전트명, date_from/date_to: 날짜 범위."""
    service = DebateMatchService(db)
    items, total = await service.list_matches(
        status=status_filter, skip=skip, limit=limit,
        search=search, date_from=date_from, date_to=date_to,
    )

    # 매치별 차단된 턴 수 집계 (단일 쿼리)
    if items:
        match_ids = [item["id"] for item in items]
        blocked_result = await db.execute(
            select(DebateTurnLog.match_id, func.count(DebateTurnLog.id).label("cnt"))
            .where(
                DebateTurnLog.match_id.in_(match_ids),
                DebateTurnLog.is_blocked == True,  # noqa: E712
            )
            .group_by(DebateTurnLog.match_id)
        )
        blocked_map: dict = {str(row.match_id): row.cnt for row in blocked_result}
        for item in items:
            item["blocked_turns_count"] = blocked_map.get(item["id"], 0)

    return {"items": items, "total": total}


@router.get("/matches/{match_id}/debug")
async def get_match_debug(
    match_id: str,
    admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """매치 전체 디버그 로그.

    raw_response, review_result, penalties 등 내부 데이터를 모두 포함.
    차단된 발언의 원문도 포함되므로 슈퍼관리자 전용.
    """
    row = (
        await db.execute(
            select(DebateMatch, DebateTopic.title)
            .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
            .where(DebateMatch.id == match_id)
        )
    ).one_or_none()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    match, topic_title = row
    agent_a = await db.get(DebateAgent, match.agent_a_id)
    agent_b = await db.get(DebateAgent, match.agent_b_id)

    turns_result = await db.execute(
        select(DebateTurnLog)
        .where(DebateTurnLog.match_id == match.id)
        .order_by(DebateTurnLog.turn_number)
    )
    turns = turns_result.scalars().all()

    return {
        "match": {
            "id": str(match.id),
            "topic_title": topic_title,
            "agent_a": {
                "id": str(agent_a.id) if agent_a else str(match.agent_a_id),
                "name": agent_a.name if agent_a else "[삭제됨]",
                "provider": agent_a.provider if agent_a else "",
                "model_id": agent_a.model_id if agent_a else "",
            },
            "agent_b": {
                "id": str(agent_b.id) if agent_b else str(match.agent_b_id),
                "name": agent_b.name if agent_b else "[삭제됨]",
                "provider": agent_b.provider if agent_b else "",
                "model_id": agent_b.model_id if agent_b else "",
            },
            "status": match.status,
            "winner_id": str(match.winner_id) if match.winner_id else None,
            "score_a": match.score_a,
            "score_b": match.score_b,
            "penalty_a": match.penalty_a,
            "penalty_b": match.penalty_b,
            "scorecard": match.scorecard,
            "started_at": match.started_at,
            "finished_at": match.finished_at,
        },
        "turns": [
            {
                "id": str(t.id),
                "turn_number": t.turn_number,
                "speaker": t.speaker,
                "action": t.action,
                "claim": t.claim,
                "evidence": t.evidence,
                "raw_response": t.raw_response,
                "review_result": t.review_result,
                "penalties": t.penalties,
                "penalty_total": t.penalty_total,
                "is_blocked": t.is_blocked,
                "human_suspicion_score": t.human_suspicion_score,
                "response_time_ms": t.response_time_ms,
                "input_tokens": t.input_tokens,
                "output_tokens": t.output_tokens,
                "tool_used": t.tool_used,
                "tool_result": t.tool_result,
                "created_at": t.created_at,
            }
            for t in turns
        ],
    }


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


# ---------------------------------------------------------------------------
# 에이전트 관리 엔드포인트
# ---------------------------------------------------------------------------

@router.get("/agents")
async def list_all_debate_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    provider: str | None = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 토론 에이전트 목록 (관리자). search: 에이전트명/소유자명, provider: 제공자 필터."""
    # count with filters
    count_query = select(func.count(DebateAgent.id)).join(User, DebateAgent.owner_id == User.id)
    main_query = (
        select(DebateAgent, User.nickname)
        .join(User, DebateAgent.owner_id == User.id)
        .order_by(DebateAgent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if search:
        like = f"%{search}%"
        count_query = count_query.where((DebateAgent.name.ilike(like)) | (User.nickname.ilike(like)))
        main_query = main_query.where((DebateAgent.name.ilike(like)) | (User.nickname.ilike(like)))
    if provider:
        count_query = count_query.where(DebateAgent.provider == provider)
        main_query = main_query.where(DebateAgent.provider == provider)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    result = await db.execute(main_query)
    rows = result.all()

    items = [
        {
            "id": str(agent.id),
            "name": agent.name,
            "provider": agent.provider,
            "model_id": agent.model_id,
            "elo_rating": agent.elo_rating,
            "image_url": agent.image_url,
            "owner_id": str(agent.owner_id),
            "owner_nickname": nickname,
            "wins": agent.wins,
            "losses": agent.losses,
            "draws": agent.draws,
            "is_active": agent.is_active,
            "tier": agent.tier,
            "is_profile_public": agent.is_profile_public,
            "created_at": agent.created_at,
        }
        for agent, nickname in rows
    ]
    return {"items": items, "total": total}


@router.get("/agents/{agent_id}")
async def get_debate_agent_detail(
    agent_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 상세 조회 (관리자). 소유자 정보 + 시스템 프롬프트 + 버전 히스토리 + 최근 매치 5건."""
    from app.models.debate_agent_version import DebateAgentVersion
    from app.models.debate_match import DebateMatch
    from app.models.debate_topic import DebateTopic

    agent = await db.get(DebateAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    owner = await db.get(User, agent.owner_id)

    # 소유자 에이전트 수
    owner_agent_count = (await db.execute(
        select(func.count(DebateAgent.id)).where(DebateAgent.owner_id == agent.owner_id)
    )).scalar() or 0

    # 버전 히스토리
    versions_result = await db.execute(
        select(DebateAgentVersion)
        .where(DebateAgentVersion.agent_id == agent.id)
        .order_by(DebateAgentVersion.version_number.desc())
    )
    versions = versions_result.scalars().all()

    # 최근 매치 5건
    matches_result = await db.execute(
        select(DebateMatch, DebateTopic.title)
        .join(DebateTopic, DebateMatch.topic_id == DebateTopic.id)
        .where(
            (DebateMatch.agent_a_id == agent.id) | (DebateMatch.agent_b_id == agent.id)
        )
        .order_by(DebateMatch.created_at.desc())
        .limit(5)
    )
    recent_matches = [
        {
            "id": str(m.id),
            "topic_title": title,
            "status": m.status,
            "winner_id": str(m.winner_id) if m.winner_id else None,
            "score_a": m.score_a,
            "score_b": m.score_b,
            "created_at": m.created_at,
        }
        for m, title in matches_result.all()
    ]

    return {
        "id": str(agent.id),
        "name": agent.name,
        "description": agent.description,
        "provider": agent.provider,
        "model_id": agent.model_id,
        "image_url": agent.image_url,
        "elo_rating": agent.elo_rating,
        "tier": agent.tier,
        "wins": agent.wins,
        "losses": agent.losses,
        "draws": agent.draws,
        "is_active": agent.is_active,
        "is_platform": agent.is_platform,
        "is_profile_public": agent.is_profile_public,
        "is_system_prompt_public": agent.is_system_prompt_public,
        "created_at": agent.created_at,
        "owner": {
            "id": str(owner.id) if owner else None,
            "nickname": owner.nickname if owner else "[삭제됨]",
            "created_at": owner.created_at if owner else None,
            "agent_count": owner_agent_count,
        },
        "versions": [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "version_tag": v.version_tag,
                "system_prompt": v.system_prompt,
                "parameters": v.parameters,
                "wins": v.wins,
                "losses": v.losses,
                "draws": v.draws,
                "created_at": v.created_at,
            }
            for v in versions
        ],
        "recent_matches": recent_matches,
    }


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_debate_agent(
    agent_id: str,
    superadmin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """토론 에이전트 강제 삭제 (superadmin 전용, 소유자 무관).

    진행 중인 매치가 있으면 삭제 불가.
    """
    agent = await db.get(DebateAgent, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # 진행 중인 매치 확인
    active_count = (
        await db.execute(
            select(func.count(DebateMatch.id)).where(
                ((DebateMatch.agent_a_id == agent.id) | (DebateMatch.agent_b_id == agent.id))
                & DebateMatch.status.in_(["pending", "in_progress", "waiting_agent"])
            )
        )
    ).scalar() or 0

    if active_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="진행 중인 매치가 있어 삭제할 수 없습니다.",
        )

    await db.delete(agent)
    await db.commit()


# ---------------------------------------------------------------------------
# 테스트용 강제 매치 생성
# ---------------------------------------------------------------------------

class ForceMatchRequest(BaseModel):
    agent_a_id: UUID
    agent_b_id: UUID


async def _run_debate_safe(match_id: str) -> None:
    """토론 엔진 실행 래퍼 (관리자 강제 매치용)."""
    import logging as _logging

    from app.services.debate_engine import run_debate
    _logger = _logging.getLogger(__name__)
    try:
        await run_debate(match_id)
    except Exception:
        _logger.exception("토론 엔진 오류 (force-match, match_id=%s)", match_id)


@router.post("/topics/{topic_id}/force-match", status_code=status.HTTP_201_CREATED)
async def force_match(
    topic_id: str,
    data: ForceMatchRequest,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """관리자 테스트용 강제 매치 생성. 큐 없이 두 에이전트를 즉시 매칭하고 토론을 시작."""
    from app.models.debate_agent_version import DebateAgentVersion
    from sqlalchemy import select as sa_select

    # 토픽 존재 확인
    topic = await db.get(DebateTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    # 에이전트 검증
    if str(data.agent_a_id) == str(data.agent_b_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="두 에이전트가 같을 수 없습니다")

    agent_a = await db.get(DebateAgent, str(data.agent_a_id))
    agent_b = await db.get(DebateAgent, str(data.agent_b_id))
    if agent_a is None or agent_b is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # 각 에이전트의 최신 버전 조회
    ver_a = (
        await db.execute(
            sa_select(DebateAgentVersion)
            .where(DebateAgentVersion.agent_id == agent_a.id)
            .order_by(DebateAgentVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    ver_b = (
        await db.execute(
            sa_select(DebateAgentVersion)
            .where(DebateAgentVersion.agent_id == agent_b.id)
            .order_by(DebateAgentVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    match = DebateMatch(
        topic_id=topic_id,
        agent_a_id=agent_a.id,
        agent_b_id=agent_b.id,
        agent_a_version_id=ver_a.id if ver_a else None,
        agent_b_version_id=ver_b.id if ver_b else None,
        status="pending",
        is_test=True,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)

    background_tasks.add_task(_run_debate_safe, str(match.id))

    return {"match_id": str(match.id), "topic_id": topic_id}
