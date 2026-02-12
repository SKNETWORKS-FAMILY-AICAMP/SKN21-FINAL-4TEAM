from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent_log import ConsentLog
from app.models.user import User


class AdultVerifyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify(self, user: User, method: str) -> bool:
        """성인인증 처리. 프로토타입에서는 항상 성공."""
        user.age_group = "adult_verified"
        user.adult_verified_at = datetime.now(timezone.utc)
        user.auth_method = method

        # 청소년보호법 시행령 기반 동의 이력 기록
        consent = ConsentLog(
            user_id=user.id,
            consent_type="adult_verify",
            status="granted",
            scope={"method": method},
        )
        self.db.add(consent)
        await self.db.commit()
        return True

    async def check_status(self, user: User) -> bool:
        """성인인증 여부 확인."""
        return user.adult_verified_at is not None
