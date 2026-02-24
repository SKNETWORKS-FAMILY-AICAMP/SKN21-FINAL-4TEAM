"""큐 브로드캐스트 단위 테스트."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPublishQueueEvent:
    @pytest.mark.asyncio
    async def test_publish_serializes_payload(self):
        """이벤트를 JSON으로 직렬화해 Redis에 발행한다."""
        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.services.debate_queue_broadcast._get_redis", return_value=mock_redis
        ):
            from app.services.debate_queue_broadcast import publish_queue_event

            await publish_queue_event(
                "topic-1", "agent-1", "matched", {"match_id": "m1", "auto_matched": False}
            )

        mock_redis.publish.assert_called_once()
        channel, payload = mock_redis.publish.call_args[0]
        assert channel == "debate:queue:topic-1:agent-1"
        parsed = json.loads(payload)
        assert parsed["event"] == "matched"
        assert parsed["data"]["match_id"] == "m1"

    @pytest.mark.asyncio
    async def test_publish_uses_correct_channel(self):
        """채널명이 debate:queue:{topic_id}:{agent_id} 형식이다."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.services.debate_queue_broadcast._get_redis", return_value=mock_redis
        ):
            from app.services.debate_queue_broadcast import publish_queue_event

            await publish_queue_event("topic-abc", "agent-xyz", "cancelled", {})

        channel = mock_redis.publish.call_args[0][0]
        assert channel == "debate:queue:topic-abc:agent-xyz"

    @pytest.mark.asyncio
    async def test_redis_closed_after_publish(self):
        """발행 후 Redis 연결을 닫는다."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.services.debate_queue_broadcast._get_redis", return_value=mock_redis
        ):
            from app.services.debate_queue_broadcast import publish_queue_event

            await publish_queue_event("t1", "a1", "timeout", {"reason": "no_platform_agents"})

        mock_redis.aclose.assert_called_once()


class TestSubscribeQueue:
    @pytest.mark.asyncio
    async def test_stream_terminates_on_matched(self):
        """matched 이벤트 수신 시 스트림이 종료된다."""
        matched_payload = json.dumps({"event": "matched", "data": {"match_id": "m1"}})

        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        call_count = 0

        async def fake_get_message(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"type": "message", "data": matched_payload}
            return None

        mock_pubsub.get_message = fake_get_message

        mock_redis = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.services.debate_queue_broadcast._get_redis", return_value=mock_redis
        ):
            from app.services.debate_queue_broadcast import subscribe_queue

            events = []
            async for chunk in subscribe_queue("t1", "a1"):
                events.append(chunk)

        # matched SSE 청크 하나 후 종료
        assert len(events) == 1
        assert "matched" in events[0]

    @pytest.mark.asyncio
    async def test_stream_terminates_on_cancelled(self):
        """cancelled 이벤트 수신 시 스트림이 종료된다."""
        cancelled_payload = json.dumps({"event": "cancelled", "data": {}})

        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.aclose = AsyncMock()

        call_count = 0

        async def fake_get_message(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"type": "message", "data": cancelled_payload}
            return None

        mock_pubsub.get_message = fake_get_message

        mock_redis = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.aclose = AsyncMock()

        with patch(
            "app.services.debate_queue_broadcast._get_redis", return_value=mock_redis
        ):
            from app.services.debate_queue_broadcast import subscribe_queue

            events = []
            async for chunk in subscribe_queue("t1", "a1"):
                events.append(chunk)

        assert len(events) == 1
        assert "cancelled" in events[0]
