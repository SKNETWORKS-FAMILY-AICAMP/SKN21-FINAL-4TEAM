"""WebSocket 연결 관리자 단위 테스트."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.debate_ws import WSTurnRequest, WSTurnResponse
from app.services.debate_ws_manager import WSConnectionManager


@pytest.fixture(autouse=True)
def reset_singleton():
    """각 테스트마다 싱글턴 인스턴스 초기화."""
    WSConnectionManager._instance = None
    yield
    WSConnectionManager._instance = None


def _make_mock_ws(connected: bool = True) -> MagicMock:
    """WebSocket mock 생성."""
    from starlette.websockets import WebSocketState

    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
    ws.send_json = AsyncMock()
    return ws


def _make_turn_request(match_id: uuid.UUID | None = None) -> WSTurnRequest:
    return WSTurnRequest(
        match_id=match_id or uuid.uuid4(),
        turn_number=1,
        speaker="agent_a",
        topic_title="Test Topic",
        topic_description=None,
        max_turns=6,
        turn_token_limit=500,
        my_previous_claims=[],
        opponent_previous_claims=[],
        time_limit_seconds=60,
    )


class TestWSConnectionManager:
    @pytest.mark.asyncio
    @patch("app.services.debate_ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_connect_registers_agent(self, mock_presence):
        """접속 시 _connections에 등록된다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)

        assert manager.is_connected(agent_id) is True
        mock_presence.assert_called_once_with(agent_id, True)

    @pytest.mark.asyncio
    @patch("app.services.debate_ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_disconnect_clears_agent(self, mock_presence):
        """해제 시 정리되고 Future가 취소된다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)
        assert manager.is_connected(agent_id) is True

        # pending future 생성
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        key = f"{uuid.uuid4()}:1:agent_a"
        # agent_id를 key에 포함시키기 위해 조작
        key_with_agent = f"{agent_id}:1:agent_a"
        manager._pending_turns[key_with_agent] = future

        await manager.disconnect(agent_id)

        assert manager.is_connected(agent_id) is False
        assert future.cancelled()
        assert key_with_agent not in manager._pending_turns

    @pytest.mark.asyncio
    @patch("app.services.debate_ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_request_turn_resolves_on_response(self, mock_presence):
        """턴 요청 후 응답 수신 시 Future가 resolve된다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        match_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)

        request = _make_turn_request(match_id)

        async def simulate_response():
            """응답을 짧은 지연 후 전송하여 Future resolve."""
            await asyncio.sleep(0.05)
            response_data = {
                "type": "turn_response",
                "match_id": str(match_id),
                "action": "argue",
                "claim": "Test claim",
                "evidence": None,
            }
            await manager.handle_message(agent_id, response_data)

        task = asyncio.create_task(simulate_response())
        result = await asyncio.wait_for(
            manager.request_turn(match_id, agent_id, request),
            timeout=2.0,
        )
        await task

        assert isinstance(result, WSTurnResponse)
        assert result.action == "argue"
        assert result.claim == "Test claim"

    @pytest.mark.asyncio
    @patch("app.services.debate_ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_request_turn_timeout(self, mock_presence):
        """타임아웃 시 TimeoutError가 발생한다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()
        ws = _make_mock_ws()

        await manager.connect(agent_id, ws)

        request = _make_turn_request()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                manager.request_turn(uuid.uuid4(), agent_id, request),
                timeout=0.1,
            )

    @pytest.mark.asyncio
    @patch("app.services.debate_ws_manager.WSConnectionManager._set_presence", new_callable=AsyncMock)
    async def test_handle_invalid_message(self, mock_presence):
        """잘못된 메시지는 에러 없이 무시된다."""
        manager = WSConnectionManager.get_instance()
        agent_id = uuid.uuid4()

        # 잘못된 type
        await manager.handle_message(agent_id, {"type": "unknown"})

        # turn_response이지만 필수 필드 누락
        await manager.handle_message(agent_id, {"type": "turn_response", "action": "argue"})

    @pytest.mark.asyncio
    async def test_is_connected_returns_false_for_unknown_agent(self):
        """등록되지 않은 에이전트는 False."""
        manager = WSConnectionManager.get_instance()
        assert manager.is_connected(uuid.uuid4()) is False

    @pytest.mark.asyncio
    async def test_request_turn_raises_on_disconnected(self):
        """미접속 에이전트에 턴 요청 시 ConnectionError."""
        manager = WSConnectionManager.get_instance()

        with pytest.raises(ConnectionError):
            await manager.request_turn(uuid.uuid4(), uuid.uuid4(), _make_turn_request())
