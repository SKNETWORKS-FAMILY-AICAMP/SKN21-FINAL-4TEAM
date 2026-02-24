"""대기방 큐 SSE 브로드캐스트.

채널: debate:queue:{topic_id}:{agent_id}
이벤트: matched, timeout, cancelled
matched / timeout / cancelled 수신 시 스트림 종료.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_TERMINAL_EVENTS = {"matched", "timeout", "cancelled"}


def _channel(topic_id: str, agent_id: str) -> str:
    return f"debate:queue:{topic_id}:{agent_id}"


async def _get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def publish_queue_event(topic_id: str, agent_id: str, event_type: str, data: dict) -> None:
    """큐 이벤트를 Redis 채널에 발행."""
    r = await _get_redis()
    try:
        payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False, default=str)
        await r.publish(_channel(topic_id, agent_id), payload)
    finally:
        await r.aclose()


async def subscribe_queue(topic_id: str, agent_id: str) -> AsyncGenerator[str, None]:
    """Redis pub/sub 구독. SSE 형식 문자열을 yield. 종료 이벤트 수신 시 스트림 종료."""
    r = await _get_redis()
    pubsub = r.pubsub()
    channel = _channel(topic_id, agent_id)
    await pubsub.subscribe(channel)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is not None and message["type"] == "message":
                data = message["data"]
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("event") in _TERMINAL_EVENTS:
                    break
            else:
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await r.aclose()
