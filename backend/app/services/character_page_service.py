"""캐릭터 페이지 서비스.

인스타그램 스타일 캐릭터 프로필 조회 + 팔로우/언팔로우.
persona_favorites를 팔로우 메커니즘으로 재활용한다.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_post import BoardPost
from app.models.persona import Persona
from app.models.persona_favorite import PersonaFavorite
from app.models.user import User


class CharacterPageService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_character_page(self, persona_id: uuid.UUID, viewer: User | None = None) -> dict:
        """캐릭터 프로필 페이지 데이터 조합."""
        result = await self.db.execute(
            select(Persona).where(Persona.id == persona_id, Persona.is_active == True)
        )
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

        # 연령등급 게이트
        self._check_age_gate(persona, viewer)

        # 팔로우 여부 확인
        is_following = False
        if viewer:
            fav = await self.db.execute(
                select(PersonaFavorite).where(
                    PersonaFavorite.user_id == viewer.id,
                    PersonaFavorite.persona_id == persona_id,
                )
            )
            is_following = fav.scalar_one_or_none() is not None

        # 크리에이터 이름
        creator_name = None
        if persona.created_by and not persona.is_anonymous:
            creator_result = await self.db.execute(
                select(User.nickname).where(User.id == persona.created_by)
            )
            creator_name = creator_result.scalar_one_or_none()

        return {
            "id": persona.id,
            "display_name": persona.display_name,
            "description": persona.description,
            "greeting_message": persona.greeting_message,
            "age_rating": persona.age_rating,
            "category": persona.category,
            "tags": persona.tags,
            "background_image_url": persona.background_image_url,
            "live2d_model_id": persona.live2d_model_id,
            "creator_name": creator_name,
            "stats": {
                "post_count": persona.post_count,
                "follower_count": persona.follower_count,
                "like_count": persona.like_count,
                "chat_count": persona.chat_count,
            },
            "is_following": is_following,
            "created_at": persona.created_at,
        }

    async def get_posts(
        self, persona_id: uuid.UUID, viewer: User | None, skip: int = 0, limit: int = 20
    ) -> dict:
        """캐릭터 게시물 피드."""
        persona = await self._get_active_persona(persona_id)
        self._check_age_gate(persona, viewer)

        count_q = (
            select(func.count())
            .select_from(BoardPost)
            .where(BoardPost.author_persona_id == persona_id, BoardPost.is_hidden == False)
        )
        total = (await self.db.execute(count_q)).scalar()

        q = (
            select(BoardPost)
            .where(BoardPost.author_persona_id == persona_id, BoardPost.is_hidden == False)
            .order_by(BoardPost.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(q)
        items = list(result.scalars().all())

        return {"items": items, "total": total}

    async def follow(self, user_id: uuid.UUID, persona_id: uuid.UUID) -> dict:
        """팔로우 (persona_favorites INSERT + follower_count INCREMENT)."""
        persona = await self._get_active_persona(persona_id)

        # 이미 팔로우 중인지 확인
        existing = await self.db.execute(
            select(PersonaFavorite).where(
                PersonaFavorite.user_id == user_id,
                PersonaFavorite.persona_id == persona_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return {"following": True, "follower_count": persona.follower_count}

        fav = PersonaFavorite(user_id=user_id, persona_id=persona_id)
        self.db.add(fav)

        await self.db.execute(
            update(Persona).where(Persona.id == persona_id).values(follower_count=Persona.follower_count + 1)
        )

        await self.db.commit()

        # 최신 카운트 조회
        updated = await self._get_active_persona(persona_id)
        return {"following": True, "follower_count": updated.follower_count}

    async def unfollow(self, user_id: uuid.UUID, persona_id: uuid.UUID) -> dict:
        """언팔로우 (persona_favorites DELETE + follower_count DECREMENT)."""
        persona = await self._get_active_persona(persona_id)

        result = await self.db.execute(
            select(PersonaFavorite).where(
                PersonaFavorite.user_id == user_id,
                PersonaFavorite.persona_id == persona_id,
            )
        )
        fav = result.scalar_one_or_none()
        if fav is None:
            return {"following": False, "follower_count": persona.follower_count}

        await self.db.delete(fav)

        await self.db.execute(
            update(Persona)
            .where(Persona.id == persona_id, Persona.follower_count > 0)
            .values(follower_count=Persona.follower_count - 1)
        )

        await self.db.commit()

        updated = await self._get_active_persona(persona_id)
        return {"following": False, "follower_count": updated.follower_count}

    async def get_followers(
        self, persona_id: uuid.UUID, viewer: User | None = None, skip: int = 0, limit: int = 20
    ) -> dict:
        """팔로워 목록."""
        # 연령등급 게이트: 18+ 캐릭터의 팔로워 목록은 성인인증 필수
        persona = await self._get_active_persona(persona_id)
        self._check_age_gate(persona, viewer)

        count_q = (
            select(func.count())
            .select_from(PersonaFavorite)
            .where(PersonaFavorite.persona_id == persona_id)
        )
        total = (await self.db.execute(count_q)).scalar()

        q = (
            select(PersonaFavorite, User.nickname)
            .join(User, PersonaFavorite.user_id == User.id)
            .where(PersonaFavorite.persona_id == persona_id)
            .order_by(PersonaFavorite.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(q)
        items = [
            {"user_id": row[0].user_id, "nickname": row[1], "followed_at": row[0].created_at}
            for row in result.all()
        ]

        return {"items": items, "total": total}

    async def _get_active_persona(self, persona_id: uuid.UUID) -> Persona:
        result = await self.db.execute(
            select(Persona).where(Persona.id == persona_id, Persona.is_active == True)
        )
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
        return persona

    @staticmethod
    def _check_age_gate(persona: Persona, viewer: User | None) -> None:
        """연령등급 게이트 검증."""
        if persona.age_rating == "18+":
            if viewer is None or viewer.adult_verified_at is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Adult verification required",
                    headers={"X-Error-Code": "AUTH_ADULT_REQUIRED"},
                )
        elif persona.age_rating == "15+":
            if viewer is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Authentication required",
                )
