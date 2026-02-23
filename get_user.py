import asyncio
from sqlalchemy import text
from app.core.database import async_session
async def main():
    async with async_session() as db:
        r = await db.execute(text(chr(34)*3SELECT nickname FROM users LIMIT 3{chr(34)*3}))
        for row in r.all():
            print(row)
asyncio.run(main())
