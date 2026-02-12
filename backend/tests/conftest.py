import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import create_access_token
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

# rsplit으로 마지막 /chatbot만 교체 (username의 chatbot은 유지)
_base, _dbname = settings.database_url.rsplit("/", 1)
TEST_DATABASE_URL = f"{_base}/chatbot_test"


def auth_header(user) -> dict:
    """테스트용 JWT Authorization 헤더 생성."""
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def db_session():
    # 각 테스트마다 새 엔진 생성 (이벤트 루프 충돌 방지)
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    """일반 사용자 fixture."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        nickname="testuser",
        password_hash=get_password_hash("testpass"),
        role="user",
        age_group="unverified",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession):
    """관리자 fixture."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    admin = User(
        id=uuid.uuid4(),
        nickname="testadmin",
        password_hash=get_password_hash("adminpass"),
        role="admin",
        age_group="adult_verified",
        adult_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest_asyncio.fixture
async def test_adult_user(db_session: AsyncSession):
    """성인인증 완료 사용자 fixture."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        nickname="adultuser",
        password_hash=get_password_hash("adultpass"),
        role="user",
        age_group="adult_verified",
        adult_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
