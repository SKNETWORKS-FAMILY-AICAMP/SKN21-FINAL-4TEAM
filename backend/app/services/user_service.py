import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import PasswordChange, UserCreate, UserLogin, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, data: UserCreate) -> User:
        """사용자 생성. login_id/닉네임 중복은 DB unique 제약으로 방어."""
        email_hash = None
        if data.email:
            email_hash = hashlib.sha256(data.email.lower().encode()).hexdigest()

        user = User(
            login_id=data.login_id,
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
        """login_id + 비밀번호 검증. 실패 시 None."""
        result = await self.db.execute(select(User).where(User.login_id == data.login_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        if not verify_password(data.password, user.password_hash):
            return None
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def check_nickname_available(self, nickname: str) -> bool:
        """닉네임 사용 가능 여부 확인."""
        result = await self.db.execute(select(User).where(User.nickname == nickname))
        return result.scalar_one_or_none() is None

    async def check_login_id_available(self, login_id: str) -> bool:
        """아이디 사용 가능 여부 확인."""
        result = await self.db.execute(select(User).where(User.login_id == login_id))
        return result.scalar_one_or_none() is None

    async def update_profile(self, user: User, data: UserUpdate) -> User:
        """프로필 정보 수정. 닉네임 중복은 DB unique 제약으로 방어."""
        if data.nickname is not None:
            user.nickname = data.nickname
        if data.preferred_themes is not None:
            user.preferred_themes = data.preferred_themes
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(self, user: User, data: PasswordChange) -> bool:
        """비밀번호 변경. 현재 비밀번호 검증 후 변경."""
        if not verify_password(data.current_password, user.password_hash):
            return False
        user.password_hash = get_password_hash(data.new_password)
        await self.db.commit()
        return True
