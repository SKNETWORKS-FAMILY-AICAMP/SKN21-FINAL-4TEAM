import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import httpx

BASE = "http://localhost:8000"

# 1. 로그인 시도
r = httpx.post(f"{BASE}/api/auth/login", json={"nickname": "tester", "password": "Test1234"})
print(f"Login status: {r.status_code}")
print(f"Response: {r.text[:500]}")

if r.status_code != 200:
    # DB에서 유저 확인
    import asyncio
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.models.user import User

    async def check():
        engine = create_async_engine(settings.database_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            result = await db.execute(select(User).where(User.nickname == "tester"))
            user = result.scalar_one_or_none()
            if user:
                print(f"\nDB user found: {user.nickname}, id={user.id}")
                print(f"  role={user.role}, age_group={user.age_group}")
                print(f"  password_hash exists: {bool(user.password_hash)}")
                print(f"  hash prefix: {user.password_hash[:20] if user.password_hash else 'NONE'}")

                # 비밀번호 직접 검증
                from app.core.auth import verify_password
                ok = verify_password("Test1234", user.password_hash)
                print(f"  password verify: {ok}")
            else:
                print("\nDB user NOT found!")

            # 전체 유저 수
            from sqlalchemy import func
            count = (await db.execute(select(func.count()).select_from(User))).scalar()
            print(f"  Total users in DB: {count}")

        await engine.dispose()

    asyncio.run(check())
