"""Redis pub/sub을 통한 토론 이벤트 SSE 브로드캐스트."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


def _channel(match_id: str) -> str:
    return f"debate:match:{match_id}"


async def _get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def publish_event(match_id: str, event_type: str, data: dict) -> None:
    """토론 이벤트를 Redis 채널에 발행."""
    r = await _get_redis()
    try:
        payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False, default=str)
        await r.publish(_channel(match_id), payload)
    finally:
        await r.aclose()


async def subscribe(match_id: str) -> AsyncGenerator[str, None]:
    """Redis pub/sub 구독. SSE 형식 문자열을 yield."""
    r = await _get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel(match_id))

    # 관전자 수 추적 — 별도 연결로 INCR (pubsub 연결 공유 불가)
    r_viewers = None
    try:
        r_viewers = await _get_redis()
        await r_viewers.incr(f"debate:viewers:{match_id}")
        await r_viewers.expire(f"debate:viewers:{match_id}", 3600)
    except Exception:
        logger.warning("Failed to increment viewer count for match %s", match_id)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is not None and message["type"] == "message":
                data = message["data"]
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("event") in ("finished", "error"):
                    break
            else:
                # 하트비트 전송 (연결 유지)
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)
    finally:
        await pubsub.unsubscribe(_channel(match_id))
        await pubsub.aclose()
        await r.aclose()
        if r_viewers is not None:
            try:
                await r_viewers.decr(f"debate:viewers:{match_id}")
            except Exception:
                logger.warning("Failed to decrement viewer count for match %s", match_id)
            await r_viewers.aclose()
