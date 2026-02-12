from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.persona import PersonaCreate, PersonaUpdate


class PersonaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_persona(self, data: PersonaCreate, user: User):
        """페르소나 생성. 18+ 등급은 성인인증 필수."""
        raise NotImplementedError

    async def update_persona(self, persona_id: str, data: PersonaUpdate, user: User):
        raise NotImplementedError

    async def delete_persona(self, persona_id: str, user: User):
        raise NotImplementedError

    async def list_personas(self, user: User):
        """공개 + 내 페르소나 목록. 연령등급 필터링 적용."""
        raise NotImplementedError

    async def get_persona(self, persona_id: str, user: User):
        raise NotImplementedError
