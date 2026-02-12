import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, data: UserCreate) -> User:
        """사용자 생성. 닉네임 중복은 DB unique 제약으로 방어."""
        email_hash = None
        if data.email:
            email_hash = hashlib.sha256(data.email.lower().encode()).hexdigest()

        user = User(
            nickname=data.nickname,
            email_hash=email_hash,
            password_hash=get_password_hash(data.password),
            role="user",
            age_group="unverified",
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, data: UserLogin) -> User | None:
        """닉네임 + 비밀번호 검증. 실패 시 None."""
        result = await self.db.execute(select(User).where(User.nickname == data.nickname))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        if not verify_password(data.password, user.password_hash):
            return None
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
