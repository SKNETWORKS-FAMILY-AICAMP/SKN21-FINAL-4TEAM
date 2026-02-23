import os
import uuid
from datetime import datetime, timezone

# debate 라우트를 테스트에서 활성화하기 위해 app import 전에 환경변수 설정
os.environ.setdefault("DEBATE_ENABLED", "true")

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
async def test_superadmin(db_session: AsyncSession):
    """슈퍼관리자 fixture."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    superadmin = User(
        id=uuid.uuid4(),
        nickname="testsuperadmin",
        password_hash=get_password_hash("superpass"),
        role="superadmin",
        age_group="adult_verified",
        adult_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(superadmin)
    await db_session.commit()
    await db_session.refresh(superadmin)
    return superadmin


@pytest_asyncio.fixture
async def test_developer(db_session: AsyncSession):
    """개발자 역할 fixture."""
    from app.core.auth import get_password_hash
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        nickname="testdev",
        password_hash=get_password_hash("devpass"),
        role="developer",
        age_group="unverified",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_debate_agent(db_session: AsyncSession, test_developer):
    """토론 에이전트 fixture."""
    from app.core.encryption import encrypt_api_key
    from app.models.debate_agent import DebateAgent
    from app.models.debate_agent_version import DebateAgentVersion

    agent = DebateAgent(
        id=uuid.uuid4(),
        owner_id=test_developer.id,
        name="Test Agent",
        provider="openai",
        model_id="gpt-4o",
        encrypted_api_key=encrypt_api_key("sk-test-key"),
    )
    db_session.add(agent)
    await db_session.flush()

    version = DebateAgentVersion(
        agent_id=agent.id,
        version_number=1,
        version_tag="v1",
        system_prompt="You are a test debate agent.",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_local_debate_agent(db_session: AsyncSession, test_developer):
    """로컬 에이전트 fixture (provider=local, API 키 없음)."""
    from app.models.debate_agent import DebateAgent
    from app.models.debate_agent_version import DebateAgentVersion

    agent = DebateAgent(
        id=uuid.uuid4(),
        owner_id=test_developer.id,
        name="Local Test Agent",
        provider="local",
        model_id="custom",
        encrypted_api_key=None,
    )
    db_session.add(agent)
    await db_session.flush()

    version = DebateAgentVersion(
        agent_id=agent.id,
        version_number=1,
        version_tag="v1",
        system_prompt="You are a local test debate agent.",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest_asyncio.fixture
async def test_debate_topic(db_session: AsyncSession, test_admin):
    """토론 주제 fixture."""
    from app.models.debate_topic import DebateTopic

    topic = DebateTopic(
        id=uuid.uuid4(),
        title="AI와 교육의 미래",
        description="AI가 교육을 개선할 수 있는가?",
        mode="debate",
        status="open",
        max_turns=6,
        turn_token_limit=500,
        created_by=test_admin.id,
    )
    db_session.add(topic)
    await db_session.commit()
    await db_session.refresh(topic)
    return topic


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
