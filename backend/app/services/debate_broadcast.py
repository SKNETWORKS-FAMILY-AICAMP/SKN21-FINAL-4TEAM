"""Redis pub/sub 기반 SSE 브로드캐스트 — 매치 관전 + 매칭 큐 이벤트 통합 모듈."""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

from app.core.redis import pubsub_client, redis_client  # 공유 연결 풀

logger = logging.getLogger(__name__)


# ── SSE 이벤트 브로드캐스트 (매치 관전자용) ────────────────────────────────────


def _channel(match_id: str) -> str:
    return f"debate:match:{match_id}"


async def publish_event(match_id: str, event_type: str, data: dict) -> None:
    """토론 이벤트를 Redis 채널에 발행. 공유 클라이언트 사용 — 청크 단위 호출 시 연결 생성 오버헤드 제거."""
    payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False, default=str)
    await redis_client.publish(_channel(match_id), payload)


async def subscribe(match_id: str, user_id: str, max_wait_seconds: int = 600) -> AsyncGenerator[str, None]:
    """Redis pub/sub 구독. SSE 형식 문자열을 yield.

    max_wait_seconds 내에 finished/error 이벤트가 오지 않으면 timeout 에러를 발행하고 종료.
    엔진 크래시/서버 재시작으로 이벤트가 누락된 경우 클라이언트가 fetchMatch를 호출해 상태를 갱신하도록 유도.
    """
    pubsub = pubsub_client.pubsub()
    await pubsub.subscribe(_channel(match_id))

    # 관전자 수 추적 — user_id를 Set 멤버로 사용해 새로고침 시 중복 카운트 방지
    viewers_key = f"debate:viewers:{match_id}"
    try:
        await redis_client.sadd(viewers_key, user_id)
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
        try:
            await redis_client.srem(viewers_key, user_id)
        except Exception:
            logger.warning("Failed to remove viewer for match %s", match_id)


# ── 매칭 큐 상태 브로드캐스트 (Redis Pub/Sub) ────────────────────────────────────
# 채널: debate:queue:{topic_id}:{agent_id}
# 이벤트: matched, timeout, cancelled, opponent_joined, countdown_started
# matched / timeout / cancelled 수신 시 스트림 종료.

_TERMINAL_EVENTS = {"matched", "timeout", "cancelled"}


def _queue_channel(topic_id: str, agent_id: str) -> str:
    return f"debate:queue:{topic_id}:{agent_id}"


async def publish_queue_event(topic_id: str, agent_id: str, event_type: str, data: dict) -> None:
    """큐 이벤트를 Redis 채널에 발행. publish_event와 동일하게 공유 redis_client 사용 — 매 호출마다 연결 생성 방지."""
    payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False, default=str)
    await redis_client.publish(_queue_channel(topic_id, agent_id), payload)


async def subscribe_queue(
    topic_id: str,
    agent_id: str,
    max_wait_seconds: int = 120,
) -> AsyncGenerator[str, None]:
    """Redis pub/sub 구독. SSE 형식 문자열을 yield. 종료 이벤트 수신 또는 타임아웃 시 스트림 종료.

    max_wait_seconds: 큐 대기 최대 시간 (기본 120초). 초과 시 timeout 이벤트를 발행하고 종료.
    """
    pubsub = pubsub_client.pubsub()
    channel = _queue_channel(topic_id, agent_id)
    await pubsub.subscribe(channel)

    deadline = time.monotonic() + max_wait_seconds

    try:
        while True:
            if time.monotonic() >= deadline:
                timeout_payload = json.dumps(
                    {"event": "timeout", "data": {"reason": "queue_timeout"}},
                    default=str,
                )
                yield f"data: {timeout_payload}\n\n"
                logger.warning(
                    "Queue subscribe timeout for topic=%s agent=%s after %ds",
                    topic_id, agent_id, max_wait_seconds,
                )
                break

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