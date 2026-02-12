from sqlalchemy.ext.asyncio import AsyncSession


class PersonaLoader:
    """페르소나 데이터를 프롬프트 형식으로 변환."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def load(self, persona_id: str) -> dict:
        """페르소나 + 관련 로어북 + Live2D 매핑 로드."""
        raise NotImplementedError
