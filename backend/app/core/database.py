from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,  # 프로덕션에서 SQL 로그 비활성화 (성능)
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # 연결 유효성 사전 확인 (끊어진 커넥션 재연결)
    pool_recycle=1800,   # 30분마다 커넥션 재생성 (장기 연결 누수 방지)
    pool_timeout=5,      # 풀 고갈 시 5초 내 실패 반환 — 기본 30초 대기로 인한 행(hang) 방지
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
