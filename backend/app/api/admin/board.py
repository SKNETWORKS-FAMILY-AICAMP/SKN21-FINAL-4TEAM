from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.services.board_service import BoardService

router = APIRouter()


@router.get("/posts")
async def admin_get_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """전체 게시글 목록 (모더레이션)."""
    service = BoardService(db)
    return await service.admin_get_posts(skip=skip, limit=limit)


@router.put("/posts/{post_id}/hide")
async def admin_hide_post(
    post_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """게시글 숨김 처리."""
    service = BoardService(db)
    await service.admin_hide_post(post_id)
    return {"status": "hidden"}


@router.put("/comments/{comment_id}/hide")
async def admin_hide_comment(
    comment_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """댓글 숨김 처리."""
    service = BoardService(db)
    await service.admin_hide_comment(comment_id)
    return {"status": "hidden"}
