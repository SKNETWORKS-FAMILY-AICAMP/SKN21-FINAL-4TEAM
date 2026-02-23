"""수동 모드 승인 큐 서비스.

publishing_mode='manual'인 캐릭터의 AI 생성 콘텐츠를 pending 큐에 저장하고,
소유자가 승인/거절할 수 있게 한다. 크레딧은 생성 시점에 차감 (LLM 호출 이미 발생).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_comment import BoardComment
from app.models.board_post import BoardPost
from app.models.pending_post import PendingPost
from app.models.persona import Persona
from app.models.user import User


MAX_PENDING_PER_PERSONA = 20


class PendingPostService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pending(
        self,
        persona_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        content_type: str,
        content: str,
        title: str | None = None,
        target_post_id: uuid.UUID | None = None,
        target_comment_id: uuid.UUID | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: Decimal = Decimal("0"),
    ) -> PendingPost:
        """AI 생성 콘텐츠를 pending 큐에 저장."""
        # pending 상한 체크
        count = (
            await self.db.execute(
                select(func.count())
                .select_from(PendingPost)
                .where(
                    PendingPost.persona_id == persona_id,
                    PendingPost.status == "pending",
                )
            )
        ).scalar()
        if count >= MAX_PENDING_PER_PERSONA:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Pending queue full (max {MAX_PENDING_PER_PERSONA})",
            )

        pending = PendingPost(
            persona_id=persona_id,
            owner_user_id=owner_user_id,
            content_type=content_type,
            title=title,
            content=content,
            target_post_id=target_post_id,
            target_comment_id=target_comment_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )
        self.db.add(pending)
        await self.db.commit()
        await self.db.refresh(pending)
        return pending

    async def list_by_owner(
        self,
        owner_user_id: uuid.UUID,
        status_filter: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """소유자의 pending 목록 조회."""
        base = select(PendingPost).where(PendingPost.owner_user_id == owner_user_id)
        count_base = select(func.count()).select_from(PendingPost).where(PendingPost.owner_user_id == owner_user_id)

        if status_filter:
            base = base.where(PendingPost.status == status_filter)
            count_base = count_base.where(PendingPost.status == status_filter)

        total = (await self.db.execute(count_base)).scalar()
        q = base.order_by(PendingPost.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(q)
        items = list(result.scalars().all())

        return {"items": items, "total": total}

    async def approve(self, pending_id: uuid.UUID, user: User) -> BoardPost | BoardComment:
        """승인: pending → board_posts 또는 board_comments로 이동."""
        pending = await self._get_owned_pending(pending_id, user)

        if pending.status != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already reviewed")

        pending.status = "approved"
        pending.reviewed_at = datetime.now(UTC)

        if pending.content_type == "post":
            # 게시판 선택: 페르소나의 lounge config에서 가져오기
            from app.models.persona_lounge_config import PersonaLoungeConfig

            config_result = await self.db.execute(
                select(PersonaLoungeConfig).where(PersonaLoungeConfig.persona_id == pending.persona_id)
            )
            config = config_result.scalar_one_or_none()
            board_id = config.allowed_boards[0] if config and config.allowed_boards else None
            if board_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No board configured for this persona",
                )

            post = BoardPost(
                board_id=board_id,
                author_persona_id=pending.persona_id,
                title=pending.title,
                content=pending.content,
                is_ai_generated=True,
            )
            self.db.add(post)

            # post_count 갱신
            await self.db.execute(
                update(Persona).where(Persona.id == pending.persona_id).values(post_count=Persona.post_count + 1)
            )

            await self.db.commit()
            await self.db.refresh(post)
            return post
        else:
            # 댓글 승인: 대상 게시물 존재 확인
            if pending.target_post_id:
                target_exists = (
                    await self.db.execute(
                        select(func.count())
                        .select_from(BoardPost)
                        .where(BoardPost.id == pending.target_post_id, BoardPost.is_hidden == False)
                    )
                ).scalar()
                if not target_exists:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Target post no longer exists or is hidden",
                    )

            comment = BoardComment(
                post_id=pending.target_post_id,
                parent_id=pending.target_comment_id,
                author_persona_id=pending.persona_id,
                content=pending.content,
                is_ai_generated=True,
            )
            self.db.add(comment)

            # 게시글 댓글 카운터 갱신
            if pending.target_post_id:
                await self.db.execute(
                    update(BoardPost)
                    .where(BoardPost.id == pending.target_post_id)
                    .values(comment_count=BoardPost.comment_count + 1)
                )

            await self.db.commit()
            await self.db.refresh(comment)
            return comment

    async def reject(self, pending_id: uuid.UUID, user: User) -> PendingPost:
        """거절: 상태만 변경 (환불 없음 — LLM 호출 비용 이미 발생)."""
        pending = await self._get_owned_pending(pending_id, user)

        if pending.status != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already reviewed")

        pending.status = "rejected"
        pending.reviewed_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(pending)
        return pending

    async def _get_owned_pending(self, pending_id: uuid.UUID, user: User) -> PendingPost:
        result = await self.db.execute(
            select(PendingPost).where(PendingPost.id == pending_id)
        )
        pending = result.scalar_one_or_none()
        if pending is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending post not found")
        if pending.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your pending post")
        return pending
