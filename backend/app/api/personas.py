import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.chat_session import ChatSession
from app.models.persona import Persona
from app.models.persona_favorite import PersonaFavorite
from app.models.user import User
from app.schemas.persona import (
    PersonaCreate,
    PersonaListResponse,
    PersonaResponse,
    PersonaStatsResponse,
    PersonaUpdate,
)
from app.schemas.report import ReportCreate
from app.services.persona_service import PersonaService
from app.services.report_service import ReportService

router = APIRouter()


@router.get("/tags")
async def list_tags(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용 중인 태그 목록 (인기순)."""
    result = await db.execute(
        select(
            func.unnest(Persona.tags).label("tag"),
            func.count().label("count"),
        )
        .where(Persona.tags.isnot(None))
        .group_by("tag")
        .order_by(func.count().desc())
        .limit(50)
    )
    return [{"tag": row.tag, "count": row.count} for row in result.all()]


@router.get("/my/stats", response_model=PersonaStatsResponse)
async def my_persona_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 페르소나 통계 (크리에이터 대시보드)."""
    # Single query with LEFT JOINs to avoid N+1
    stmt = (
        select(
            Persona,
            func.count(func.distinct(ChatSession.id)).label("chat_count"),
            func.count(func.distinct(PersonaFavorite.id)).label("like_count"),
        )
        .outerjoin(ChatSession, ChatSession.persona_id == Persona.id)
        .outerjoin(PersonaFavorite, PersonaFavorite.persona_id == Persona.id)
        .where(Persona.created_by == user.id)
        .group_by(Persona.id)
        .order_by(Persona.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    stats = []
    for p, chat_count, like_count in rows:
        stats.append(
            {
                "persona_id": str(p.id),
                "display_name": p.display_name,
                "chat_count": chat_count,
                "like_count": like_count,
                "age_rating": p.age_rating,
                "visibility": p.visibility,
                "moderation_status": p.moderation_status,
                "created_at": p.created_at.isoformat(),
            }
        )
    return {"personas": stats, "total": len(stats)}


@router.get("", response_model=PersonaListResponse)
async def list_personas(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    tags: str | None = Query(None, max_length=200),
    category: str | None = Query(None, max_length=30),
    rating: str | None = Query(None, pattern="^(all_age|15\\+|18\\+)$"),
    sort: str = Query("recent", pattern="^(recent|popular|name)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 목록 조회 (검색, 태그/카테고리 필터, 정렬 지원)."""
    service = PersonaService(db)
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    return await service.list_personas(
        user,
        skip=skip,
        limit=limit,
        search=search,
        tags=tag_list,
        category=category,
        rating=rating,
        sort=sort,
    )


@router.post("", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def create_persona(
    data: PersonaCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 생성."""
    service = PersonaService(db)
    try:
        return await service.create_persona(data, user)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Persona key + version already exists",
        ) from None


@router.get("/creator/{creator_id}")
async def get_creator_personas(
    creator_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 유저가 만든 공개 페르소나 목록 + 닉네임."""
    from sqlalchemy import or_

    from app.services.persona_service import PersonaService

    # 제작자 닉네임 조회
    creator = await db.execute(select(User).where(User.id == creator_id))
    creator_user = creator.scalar_one_or_none()
    if creator_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    allowed_ratings = PersonaService._allowed_ratings(user)

    query = (
        select(Persona)
        .where(
            Persona.created_by == creator_id,
            Persona.age_rating.in_(allowed_ratings),
            or_(
                Persona.created_by == user.id,
                (Persona.visibility == "public")
                & (Persona.moderation_status == "approved")
                & (Persona.is_anonymous == False),
            ),
        )
        .order_by(Persona.chat_count.desc())
        .limit(20)
    )
    result = await db.execute(query)
    personas = result.scalars().all()

    return {
        "creator_nickname": creator_user.nickname,
        "creator_id": str(creator_id),
        "personas": [
            {
                "id": str(p.id),
                "display_name": p.display_name,
                "description": p.description,
                "category": p.category,
                "age_rating": p.age_rating,
                "chat_count": p.chat_count,
                "like_count": p.like_count,
                "background_image_url": p.background_image_url,
            }
            for p in personas
        ],
        "total": len(personas),
    }


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 상세 조회."""
    service = PersonaService(db)
    return await service.get_persona(persona_id, user)


@router.put("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: uuid.UUID,
    data: PersonaUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 수정 (소유자만)."""
    service = PersonaService(db)
    return await service.update_persona(persona_id, data, user)


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    persona_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 삭제 (소유자만)."""
    service = PersonaService(db)
    await service.delete_persona(persona_id, user)


@router.post("/{persona_id}/report", status_code=status.HTTP_201_CREATED)
async def report_persona(
    persona_id: uuid.UUID,
    data: ReportCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """페르소나 신고. 자기 페르소나 신고 불가, 중복 신고 불가."""
    service = ReportService(db)
    report = await service.create_report(persona_id, user.id, data)
    return {"id": report.id, "status": report.status}
