from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class AdultVerifyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify(self, user: User, method: str) -> bool:
        """성인인증 처리. 성공 시 user.adult_verified_at 설정 + consent_logs 기록."""
        raise NotImplementedError

    async def check_status(self, user: User) -> bool:
        """성인인증 여부 확인."""
        return user.adult_verified_at is not None
