"""Redis pub/sub을 통한 토론 이벤트 SSE 브로드캐스트."""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.redis import redis_client  # 공유 연결 풀 (viewer 추적용)

logger = logging.getLogger(__name__)


def _channel(match_id: str) -> str:
    return f"debate:match:{match_id}"


async def _get_redis():
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def publish_event(match_id: str, event_type: str, data: dict) -> None:
    """토론 이벤트를 Redis 채널에 발행. 공유 클라이언트 사용 — 청크 단위 호출 시 연결 생성 오버헤드 제거."""
    payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False, default=str)
    await redis_client.publish(_channel(match_id), payload)


async def subscribe(match_id: str, max_wait_seconds: int = 600) -> AsyncGenerator[str, None]:
    """Redis pub/sub 구독. SSE 형식 문자열을 yield.

    max_wait_seconds 내에 finished/error 이벤트가 오지 않으면 timeout 에러를 발행하고 종료.
    엔진 크래시/서버 재시작으로 이벤트가 누락된 경우 클라이언트가 fetchMatch를 호출해 상태를 갱신하도록 유도.
    """
    r = await _get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel(match_id))

    # 관전자 수 추적 — 공유 redis_client + Set 기반 (연결마다 새 Redis 클라이언트 생성 방지)
    conn_id = str(uuid.uuid4())
    viewers_key = f"debate:viewers:{match_id}"
    try:
        await redis_client.sadd(viewers_key, conn_id)
        await redis_client.expire(viewers_key, 3600)
    except Exception:
        logger.warning("Failed to add viewer for match %s", match_id)

    deadline = time.monotonic() + max_wait_seconds

    try:
        while True:
            if time.monotonic() >= deadline:
                # 최대 대기 시간 초과 — 엔진 크래시 또는 비정상 종료로 이벤트 미수신
                timeout_payload = json.dumps(
                    {"event": "error", "data": {"message": "Stream timeout: match may have failed"}},
                    ensure_ascii=False,
                )
                yield f"data: {timeout_payload}\n\n"
                logger.warning("SSE subscribe timeout for match %s after %ds", match_id, max_wait_seconds)
                break

            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is not None and message["type"] == "message":
                data = message["data"]
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("event") in ("finished", "error", "forfeit"):
                    break
            else:
                # 하트비트 전송 (연결 유지)
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)
    finally:
        await pubsub.unsubscribe(_channel(match_id))
        await pubsub.aclose()
        await r.aclose()
        try:
            await redis_client.srem(viewers_key, conn_id)
        except Exception:
            logger.warning("Failed to remove viewer for match %s", match_id)
