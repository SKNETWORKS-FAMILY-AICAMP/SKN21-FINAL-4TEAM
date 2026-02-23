from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.board import (
    BoardResponse,
    CommentCreate,
    PostCreate,
    ReactionRequest,
    ReactionResponse,
)
from app.services.board_service import BoardService

router = APIRouter()


@router.get("/boards", response_model=list[BoardResponse])
async def get_boards(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """활성 게시판 목록 (연령등급 필터링)."""
    service = BoardService(db)
    return await service.get_boards(user)


@router.get("/{board_id}/posts")
async def get_feed(
    board_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("latest", pattern="^(latest|trending|persona)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """게시판 피드."""
    service = BoardService(db)
    return await service.get_feed(board_id, user, skip=skip, limit=limit, sort=sort)


@router.post("/{board_id}/posts", status_code=201)
async def create_post(
    board_id: str,
    data: PostCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """게시글 작성."""
    service = BoardService(db)
    post = await service.create_post(
        user=user,
        board_id=board_id,
        title=data.title,
        content=data.content,
        persona_id=data.persona_id,
        age_rating=data.age_rating,
    )
    return {"id": post.id, "created_at": post.created_at}


@router.get("/posts/{post_id}")
async def get_post_detail(
    post_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """게시글 상세 + 댓글 트리."""
    service = BoardService(db)
    return await service.get_post_detail(post_id, user)


@router.post("/posts/{post_id}/comments", status_code=201)
async def create_comment(
    post_id: str,
    data: CommentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """댓글/답글 작성."""
    service = BoardService(db)
    comment = await service.create_comment(
        user=user,
        post_id=post_id,
        content=data.content,
        parent_id=data.parent_id,
        persona_id=data.persona_id,
    )
    return {"id": comment.id, "created_at": comment.created_at}


@router.post("/posts/{post_id}/reactions", response_model=ReactionResponse)
async def toggle_post_reaction(
    post_id: str,
    data: ReactionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """게시글 좋아요 토글."""
    service = BoardService(db)
    return await service.toggle_reaction(user, post_id=post_id, reaction_type=data.reaction_type)


@router.post("/comments/{comment_id}/reactions", response_model=ReactionResponse)
async def toggle_comment_reaction(
    comment_id: str,
    data: ReactionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """댓글 좋아요 토글."""
    service = BoardService(db)
    return await service.toggle_reaction(user, comment_id=comment_id, reaction_type=data.reaction_type)


@router.get("/personas/{persona_id}/activity")
async def get_persona_activity(
    persona_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 캐릭터 활동 피드."""
    service = BoardService(db)
    return await service.get_persona_activity(persona_id, skip=skip, limit=limit)
