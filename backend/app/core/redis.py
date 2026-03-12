from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from app.core.config import settings

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

# pub/sub 전용 클라이언트 — subscribe 상태에서는 다른 명령 불가이므로 일반 클라이언트와 분리.
# ConnectionPool을 명시적으로 생성해 동시 SSE 연결 수를 max_connections으로 상한 제어.
_pubsub_pool = ConnectionPool.from_url(
    settings.redis_url,
    decode_responses=True,
    max_connections=200,
)
pubsub_client = Redis(connection_pool=_pubsub_pool)


async def get_redis() -> Redis:
    return redis_client
