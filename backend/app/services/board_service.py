"""게시판(캐릭터 라운지) 서비스.

게시글/댓글 CRUD, 피드, 리액션, 연령등급 필터링, 크레딧 차감을 담당한다.
"""

import logging
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.board import Board
from app.models.board_comment import BoardComment
from app.models.board_post import BoardPost
from app.models.board_reaction import BoardReaction
from app.models.persona import Persona
from app.models.user import User
from app.pipeline.pii import PIIDetector, get_pii_detector

logger = logging.getLogger(__name__)


class BoardService:
    def __init__(self, db: AsyncSession, pii_detector: PIIDetector | None = None):
        self.db = db
        self._pii = pii_detector

    @property
    def pii(self) -> PIIDetector:
        if self._pii is None:
            self._pii = get_pii_detector()
        return self._pii

    # ── 게시판 목록 ──

    async def get_boards(self, user: User) -> list[Board]:
        """연령등급 필터링된 활성 게시판 목록."""
        q = select(Board).where(Board.is_active == True).order_by(Board.sort_order)
        if user.adult_verified_at is None:
            q = q.where(Board.age_rating == "all")
        result = await self.db.execute(q)
        return list(result.scalars().all())

    # ── 게시글 ──

    async def create_post(
        self,
        user: User,
        board_id: uuid.UUID,
        title: str | None,
        content: str,
        persona_id: uuid.UUID | None = None,
        age_rating: str = "all",
    ) -> BoardPost:
        """게시글 작성. 유저 직접 or 유저의 페르소나로 작성."""
        board = await self._get_board_or_404(board_id)
        self._check_age_gate(user, board.age_rating)

        # 연령등급 상향 검증
        if age_rating in ("15+", "18+"):
            self._check_age_gate(user, age_rating)

        author_persona_id = None
        if persona_id:
            persona = await self._verify_persona_ownership(user, persona_id)
            author_persona_id = persona.id

        safe_content = self.pii.mask(content)
        safe_title = self.pii.mask(title) if title else title

        # 크레딧 차감
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            await credit_svc.check_and_deduct(user.id, "lounge_post", "standard")

        post = BoardPost(
            board_id=board_id,
            author_user_id=user.id if not author_persona_id else None,
            author_persona_id=author_persona_id,
            title=safe_title,
            content=safe_content,
            age_rating=age_rating,
            is_ai_generated=False,
        )
        self.db.add(post)
        await self.db.commit()
        await self.db.refresh(post)
        return post

    async def get_feed(
        self,
        board_id: uuid.UUID,
        user: User,
        skip: int = 0,
        limit: int = 20,
        sort: str = "latest",
    ) -> dict[str, Any]:
        """게시판 피드. 연령등급 필터링 + 정렬."""
        board = await self._get_board_or_404(board_id)
        self._check_age_gate(user, board.age_rating)

        base = select(BoardPost).where(BoardPost.board_id == board_id, BoardPost.is_hidden == False)

        # 연령등급 필터
        if user.adult_verified_at is None:
            base = base.where(BoardPost.age_rating == "all")

        count_q = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_q)).scalar()

        if sort == "trending":
            q = base.order_by(BoardPost.reaction_count.desc(), BoardPost.created_at.desc())
        elif sort == "persona":
            q = base.where(BoardPost.author_persona_id.isnot(None)).order_by(BoardPost.created_at.desc())
        else:
            q = base.order_by(BoardPost.is_pinned.desc(), BoardPost.created_at.desc())

        q = q.offset(skip).limit(limit)
        result = await self.db.execute(q)
        posts = result.scalars().all()

        items = []
        for post in posts:
            items.append(await self._to_post_response(post, user))

        return {"items": items, "total": total}

    async def get_post_detail(self, post_id: uuid.UUID, user: User) -> dict[str, Any]:
        """게시글 상세 + 댓글 트리."""
        post = await self._get_post_or_404(post_id)
        self._check_age_gate(user, post.age_rating)

        post_resp = await self._to_post_response(post, user)

        # 댓글 조회 (is_hidden 제외)
        comment_q = (
            select(BoardComment)
            .where(BoardComment.post_id == post_id, BoardComment.is_hidden == False)
            .order_by(BoardComment.created_at.asc())
        )
        comment_result = await self.db.execute(comment_q)
        all_comments = list(comment_result.scalars().all())

        comments = await self._build_comment_tree(all_comments, user)

        return {"post": post_resp, "comments": comments}

    async def get_persona_activity(self, persona_id: uuid.UUID, skip: int = 0, limit: int = 20) -> dict[str, Any]:
        """특정 페르소나의 게시판 활동 피드."""
        # 게시글
        post_q = (
            select(BoardPost)
            .where(BoardPost.author_persona_id == persona_id, BoardPost.is_hidden == False)
            .order_by(BoardPost.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(post_q)
        posts = list(result.scalars().all())

        count_q = (
            select(func.count())
            .select_from(BoardPost)
            .where(BoardPost.author_persona_id == persona_id, BoardPost.is_hidden == False)
        )
        total = (await self.db.execute(count_q)).scalar()

        return {"items": posts, "total": total}

    # ── 댓글 ──

    async def create_comment(
        self,
        user: User,
        post_id: uuid.UUID,
        content: str,
        parent_id: uuid.UUID | None = None,
        persona_id: uuid.UUID | None = None,
    ) -> BoardComment:
        """댓글/답글 작성."""
        post = await self._get_post_or_404(post_id)
        self._check_age_gate(user, post.age_rating)

        if parent_id:
            parent_result = await self.db.execute(
                select(BoardComment).where(BoardComment.id == parent_id, BoardComment.post_id == post_id)
            )
            if parent_result.scalar_one_or_none() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found")

        author_persona_id = None
        if persona_id:
            persona = await self._verify_persona_ownership(user, persona_id)
            author_persona_id = persona.id

        safe_content = self.pii.mask(content)

        # 크레딧 차감
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            await credit_svc.check_and_deduct(user.id, "lounge_comment", "standard")

        comment = BoardComment(
            post_id=post_id,
            parent_id=parent_id,
            author_user_id=user.id if not author_persona_id else None,
            author_persona_id=author_persona_id,
            content=safe_content,
            is_ai_generated=False,
        )
        self.db.add(comment)

        # 비정규화 카운터 갱신
        await self.db.execute(
            update(BoardPost).where(BoardPost.id == post_id).values(comment_count=BoardPost.comment_count + 1)
        )

        await self.db.commit()
        await self.db.refresh(comment)
        return comment

    # ── 리액션 ──

    async def toggle_reaction(
        self,
        user: User,
        post_id: uuid.UUID | None = None,
        comment_id: uuid.UUID | None = None,
        reaction_type: str = "like",
    ) -> dict[str, Any]:
        """좋아요 토글. 이미 있으면 삭제, 없으면 추가."""
        if post_id:
            existing_q = select(BoardReaction).where(BoardReaction.user_id == user.id, BoardReaction.post_id == post_id)
        elif comment_id:
            existing_q = select(BoardReaction).where(
                BoardReaction.user_id == user.id, BoardReaction.comment_id == comment_id
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="post_id or comment_id required")

        existing_result = await self.db.execute(existing_q)
        existing = existing_result.scalar_one_or_none()

        if existing:
            # 삭제
            await self.db.delete(existing)
            delta = -1
            toggled = False
        else:
            # 추가
            reaction = BoardReaction(
                user_id=user.id,
                post_id=post_id,
                comment_id=comment_id,
                reaction_type=reaction_type,
            )
            self.db.add(reaction)
            delta = 1
            toggled = True

        # 비정규화 카운터 갱신
        if post_id:
            await self.db.execute(
                update(BoardPost).where(BoardPost.id == post_id).values(reaction_count=BoardPost.reaction_count + delta)
            )
            await self.db.commit()
            count_result = await self.db.execute(select(BoardPost.reaction_count).where(BoardPost.id == post_id))
        else:
            await self.db.execute(
                update(BoardComment)
                .where(BoardComment.id == comment_id)
                .values(reaction_count=BoardComment.reaction_count + delta)
            )
            await self.db.commit()
            count_result = await self.db.execute(
                select(BoardComment.reaction_count).where(BoardComment.id == comment_id)
            )

        new_count = count_result.scalar() or 0
        return {"toggled": toggled, "new_count": new_count}

    # ── 관리자 ──

    async def admin_get_posts(self, skip: int = 0, limit: int = 50) -> dict[str, Any]:
        """전체 게시글 (모더레이션용)."""
        count_q = select(func.count()).select_from(BoardPost)
        total = (await self.db.execute(count_q)).scalar()

        q = select(BoardPost).order_by(BoardPost.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(q)
        return {"items": list(result.scalars().all()), "total": total}

    async def admin_hide_post(self, post_id: uuid.UUID) -> None:
        await self.db.execute(update(BoardPost).where(BoardPost.id == post_id).values(is_hidden=True))
        await self.db.commit()

    async def admin_hide_comment(self, comment_id: uuid.UUID) -> None:
        await self.db.execute(update(BoardComment).where(BoardComment.id == comment_id).values(is_hidden=True))
        await self.db.commit()

    # ── 내부 헬퍼 ──

    async def _get_board_or_404(self, board_id: uuid.UUID) -> Board:
        result = await self.db.execute(select(Board).where(Board.id == board_id))
        board = result.scalar_one_or_none()
        if board is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        return board

    async def _get_post_or_404(self, post_id: uuid.UUID) -> BoardPost:
        result = await self.db.execute(select(BoardPost).where(BoardPost.id == post_id, BoardPost.is_hidden == False))
        post = result.scalar_one_or_none()
        if post is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        return post

    def _check_age_gate(self, user: User, age_rating: str) -> None:
        """연령등급 게이트. 미달 시 403."""
        if age_rating == "18+" and user.adult_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Adult verification required",
                headers={"X-Error-Code": "AUTH_ADULT_REQUIRED"},
            )
        if age_rating == "15+" and user.age_group not in ("minor_safe", "adult_verified"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Age verification required for 15+ content",
            )

    async def _verify_persona_ownership(self, user: User, persona_id: uuid.UUID) -> Persona:
        """유저가 해당 페르소나의 소유자인지 검증."""
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id, Persona.created_by == user.id))
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your persona")
        return persona

    async def _to_post_response(self, post: BoardPost, user: User) -> dict[str, Any]:
        """BoardPost → 응답 딕셔너리 변환 (author + my_reaction 포함)."""
        author = await self._resolve_author(post.author_user_id, post.author_persona_id)

        # 내 리액션 확인
        my_reaction = None
        reaction_result = await self.db.execute(
            select(BoardReaction.reaction_type).where(
                BoardReaction.user_id == user.id, BoardReaction.post_id == post.id
            )
        )
        r = reaction_result.scalar_one_or_none()
        if r:
            my_reaction = r

        return {
            "id": post.id,
            "board_id": post.board_id,
            "title": post.title,
            "content": post.content,
            "author": author,
            "age_rating": post.age_rating,
            "is_ai_generated": post.is_ai_generated,
            "reaction_count": post.reaction_count,
            "comment_count": post.comment_count,
            "is_pinned": post.is_pinned,
            "created_at": post.created_at,
            "updated_at": post.updated_at,
            "my_reaction": my_reaction,
        }

    async def _resolve_author(self, user_id: uuid.UUID | None, persona_id: uuid.UUID | None) -> dict:
        if persona_id:
            result = await self.db.execute(select(Persona.id, Persona.display_name).where(Persona.id == persona_id))
            row = result.one_or_none()
            if row:
                return {"type": "persona", "id": row.id, "display_name": row.display_name or "캐릭터"}
        if user_id:
            result = await self.db.execute(select(User.id, User.nickname).where(User.id == user_id))
            row = result.one_or_none()
            if row:
                return {"type": "user", "id": row.id, "display_name": row.nickname}
        return {"type": "unknown", "id": None, "display_name": "알 수 없음"}

    async def _build_comment_tree(self, comments: list[BoardComment], user: User) -> list[dict]:
        """플랫 댓글 → 트리 구조 변환."""
        comment_map: dict[uuid.UUID, dict] = {}
        roots: list[dict] = []

        for c in comments:
            author = await self._resolve_author(c.author_user_id, c.author_persona_id)

            # 내 리액션 확인
            my_reaction = None
            r_result = await self.db.execute(
                select(BoardReaction.reaction_type).where(
                    BoardReaction.user_id == user.id, BoardReaction.comment_id == c.id
                )
            )
            r = r_result.scalar_one_or_none()
            if r:
                my_reaction = r

            node = {
                "id": c.id,
                "post_id": c.post_id,
                "parent_id": c.parent_id,
                "author": author,
                "content": c.content,
                "is_ai_generated": c.is_ai_generated,
                "reaction_count": c.reaction_count,
                "created_at": c.created_at,
                "my_reaction": my_reaction,
                "children": [],
            }
            comment_map[c.id] = node

        for c in comments:
            node = comment_map[c.id]
            if c.parent_id and c.parent_id in comment_map:
                comment_map[c.parent_id]["children"].append(node)
            else:
                roots.append(node)

        return roots
