import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.models.user import User
from app.schemas.persona import PersonaCreate, PersonaUpdate


class PersonaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_personas(self, user: User, skip: int = 0, limit: int = 20) -> dict:
        """공개+승인+내 페르소나 목록. 연령등급 필터링 적용."""
        allowed_ratings = self._allowed_ratings(user)

        query = (
            select(Persona)
            .where(
                Persona.age_rating.in_(allowed_ratings),
                or_(
                    # 공개 + 승인된 페르소나
                    (Persona.visibility == "public") & (Persona.moderation_status == "approved"),
                    # 내가 만든 페르소나 (비공개 포함)
                    Persona.created_by == user.id,
                ),
            )
            .order_by(Persona.created_at.desc())
        )

        # 전체 카운트
        from sqlalchemy import func
        count_query = (
            select(func.count())
            .select_from(Persona)
            .where(
                Persona.age_rating.in_(allowed_ratings),
                or_(
                    (Persona.visibility == "public") & (Persona.moderation_status == "approved"),
                    Persona.created_by == user.id,
                ),
            )
        )
        total = (await self.db.execute(count_query)).scalar()

        result = await self.db.execute(query.offset(skip).limit(limit))
        items = result.scalars().all()
        return {"items": list(items), "total": total}

    async def get_persona(self, persona_id: uuid.UUID, user: User) -> Persona:
        """페르소나 상세 조회. 접근 권한 + 연령 게이트 확인."""
        persona = await self._get_or_404(persona_id)

        # 접근 권한: 공개+승인 또는 본인 소유
        if persona.created_by != user.id:
            if persona.visibility != "public" or persona.moderation_status != "approved":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

        # 연령 게이트
        self._check_age_gate(user, persona.age_rating)
        return persona

    async def create_persona(self, data: PersonaCreate, user: User) -> Persona:
        """페르소나 생성. 18+ 등급은 성인인증 필수."""
        if data.age_rating == "18+" and user.adult_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Adult verification required for 18+ content",
            )

        persona = Persona(
            created_by=user.id,
            type="user_created",
            persona_key=data.persona_key,
            version=data.version,
            display_name=data.display_name,
            system_prompt=data.system_prompt,
            style_rules=data.style_rules,
            safety_rules=data.safety_rules,
            review_template=data.review_template,
            catchphrases=data.catchphrases,
            live2d_model_id=data.live2d_model_id,
            background_image_url=data.background_image_url,
            age_rating=data.age_rating,
            visibility=data.visibility,
            moderation_status="pending",
            is_active=False,
        )
        self.db.add(persona)
        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    async def update_persona(self, persona_id: uuid.UUID, data: PersonaUpdate, user: User) -> Persona:
        """페르소나 수정 (소유자만)."""
        persona = await self._get_or_404(persona_id)
        self._check_ownership(persona, user)

        # 18+ 등급 변경 시 성인인증 확인
        if data.age_rating == "18+" and user.adult_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Adult verification required for 18+ content",
            )

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(persona, field, value)
        persona.updated_at = datetime.now(timezone.utc)

        # 내용 변경 시 모더레이션 재심 필요
        if persona.visibility == "public":
            persona.moderation_status = "pending"

        await self.db.commit()
        await self.db.refresh(persona)
        return persona

    async def delete_persona(self, persona_id: uuid.UUID, user: User) -> None:
        """페르소나 삭제 (소유자만)."""
        persona = await self._get_or_404(persona_id)
        self._check_ownership(persona, user)
        await self.db.delete(persona)
        await self.db.commit()

    # ── 헬퍼 ──

    async def _get_or_404(self, persona_id: uuid.UUID) -> Persona:
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
        return persona

    @staticmethod
    def _check_ownership(persona: Persona, user: User) -> None:
        if persona.created_by != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the owner")

    @staticmethod
    def _allowed_ratings(user: User) -> list[str]:
        """사용자 연령 인증 상태에 따라 허용되는 등급 목록."""
        if user.adult_verified_at is not None:
            return ["all", "15+", "18+"]
        return ["all", "15+"]

    @staticmethod
    def _check_age_gate(user: User, age_rating: str) -> None:
        if age_rating == "18+" and user.adult_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Adult verification required",
            )
