"""로컬 에이전트 WebSocket 연결 관리 (싱글턴)."""

import asyncio
import logging
from uuid import UUID

from starlette.websockets import WebSocket, WebSocketState

from app.schemas.debate_ws import WSMatchReady, WSTurnRequest, WSTurnResponse

logger = logging.getLogger(__name__)

_PRESENCE_PREFIX = "debate:agent:"
_PRESENCE_TTL = 60  # heartbeat 갱신 주기보다 충분히 길게
_PUBSUB_CHANNEL = "debate:agent:messages"


class WSConnectionManager:
    _instance: "WSConnectionManager | None" = None

    def __init__(self) -> None:
        self._connections: dict[UUID, WebSocket] = {}
        self._pending_turns: dict[str, asyncio.Future[WSTurnResponse]] = {}
        self._pubsub_task: asyncio.Task | None = None

    @classmethod
    def get_instance(cls) -> "WSConnectionManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def connect(self, agent_id: UUID, ws: WebSocket) -> None:
        """WebSocket 등록 + Redis 프레즈스 설정.

        기존 stale 연결이 남아 있으면 정리 후 새 연결을 등록한다.
        pending Future는 보존하여 새 연결에서 계속 처리할 수 있도록 한다.
        """
        existing_ws = self._connections.get(agent_id)
        if existing_ws is not None and existing_ws is not ws:
            # stale 연결 정리 — pending Future는 보존
            await self._cleanup_stale_connection(agent_id, existing_ws)

        self._connections[agent_id] = ws
        await self._set_presence(agent_id, True)
        logger.info("Local agent %s connected via WebSocket", agent_id)

    async def _cleanup_stale_connection(self, agent_id: UUID, stale_ws: WebSocket) -> None:
        """stale WebSocket 연결을 안전하게 닫는다. pending Future는 보존."""
        logger.info("Cleaning up stale connection for agent %s (reconnect)", agent_id)
        try:
            if stale_ws.client_state == WebSocketState.CONNECTED:
                await stale_ws.close(code=1012, reason="Replaced by new connection")
        except Exception:
            # stale 소켓은 이미 깨진 상태일 수 있음 — 무시
            logger.debug("Failed to close stale WebSocket for agent %s (expected)", agent_id)
        # _connections에서 제거하지 않음 — caller가 새 ws로 덮어씔
        # _pending_turns 보존 — 새 연결에서 계속 처리


    async def disconnect(self, agent_id: UUID) -> None:
        """연결 해제 + Redis 프레즌스 삭제 + 대기 중 Future 취소."""
        self._connections.pop(agent_id, None)
        await self._set_presence(agent_id, False)

        # 해당 에이전트와 관련된 모든 pending Future 취소
        to_cancel = [k for k in self._pending_turns if str(agent_id) in k]
        for key in to_cancel:
            future = self._pending_turns.pop(key, None)
            if future and not future.done():
                future.cancel()

        logger.info("Local agent %s disconnected", agent_id)

    def is_connected(self, agent_id: UUID) -> bool:
        ws = self._connections.get(agent_id)
        if ws is None:
            return False
        return ws.client_state == WebSocketState.CONNECTED

    async def request_turn(
        self, match_id: UUID, agent_id: UUID, request: WSTurnRequest
    ) -> WSTurnResponse:
        """턴 요청 전송 + Future 생성. caller가 wait_for로 타임아웃 처리.
        로컬 미연결이면 Redis pub/sub로 다른 인스턴스에 전달 시도.
        """
        key = f"{match_id}:{request.turn_number}:{request.speaker}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[WSTurnResponse] = loop.create_future()
        self._pending_turns[key] = future

        ws = self._connections.get(agent_id)
        if ws is not None:
            # 로컬 연결 — 직접 전송
            try:
                await ws.send_json(request.model_dump(mode="json"))
            except Exception:
                self._pending_turns.pop(key, None)
                raise
        else:
            # 로컬 미연결 — Redis 프레즌스 확인 후 pub/sub로 전달
            is_present = await self.check_presence(agent_id)
            if not is_present:
                self._pending_turns.pop(key, None)
                raise ConnectionError(f"Agent {agent_id} is not connected on any instance")
            await self._publish_to_agent(agent_id, request.model_dump(mode="json"))

        return await future

    async def handle_message(self, agent_id: UUID, data: dict) -> None:
        """수신 메시지 처리. turn_response일 때 해당 Future resolve."""
        msg_type = data.get("type")

        if msg_type == "turn_response":
            try:
                response = WSTurnResponse.model_validate(data)
            except Exception:
                logger.warning("Invalid turn_response from agent %s: %s", agent_id, data)
                return

            key = f"{response.match_id}:{data.get('turn_number', '')}:{data.get('speaker', '')}"
            # turn_number/speaker가 없으면 match_id 기반 부분 매칭
            future = self._pending_turns.pop(key, None)
            if future is None:
                # match_id 기반 첫 번째 매칭 Future 탐색
                for k in list(self._pending_turns):
                    if k.startswith(str(response.match_id)):
                        future = self._pending_turns.pop(k)
                        break

            if future and not future.done():
                future.set_result(response)
            else:
                logger.warning("No pending future for turn_response: match=%s", response.match_id)

        elif msg_type == "pong":
            # heartbeat 응답 — 프레즌스 갱신
            await self._set_presence(agent_id, True)

        else:
            logger.debug("Unknown message type from agent %s: %s", agent_id, msg_type)

    async def send_match_ready(self, agent_id: UUID, msg: WSMatchReady) -> None:
        ws = self._connections.get(agent_id)
        if ws is None:
            raise ConnectionError(f"Agent {agent_id} is not connected")
        await ws.send_json(msg.model_dump(mode="json"))

    async def send_error(self, agent_id: UUID, message: str, code: str | None = None) -> None:
        ws = self._connections.get(agent_id)
        if ws is None:
            return
        try:
            await ws.send_json({"type": "error", "message": message, "code": code})
        except Exception:
            pass

    async def send_ping(self, agent_id: UUID) -> None:
        ws = self._connections.get(agent_id)
        if ws is None:
            return
        try:
            await ws.send_json({"type": "ping"})
        except Exception:
            await self.disconnect(agent_id)

    async def _set_presence(self, agent_id: UUID, connected: bool) -> None:
        try:
            from app.core.redis import redis_client

            key = f"{_PRESENCE_PREFIX}{agent_id}:connected"
            if connected:
                await redis_client.setex(key, _PRESENCE_TTL, "1")
            else:
                await redis_client.delete(key)
        except Exception:
            logger.debug("Redis presence update failed for agent %s", agent_id)

    async def check_presence(self, agent_id: UUID) -> bool:
        """Redis 프레즌스로 접속 여부 확인 (메모리 + Redis 이중 체크)."""
        if self.is_connected(agent_id):
            return True
        try:
            from app.core.redis import redis_client

            key = f"{_PRESENCE_PREFIX}{agent_id}:connected"
            return await redis_client.exists(key) > 0
        except Exception:
            return False


    async def start_pubsub_listener(self) -> None:
        """Redis pub/sub 리스너 시작. 다른 인스턴스에서 온 메시지를 로컬 에이전트에 전달."""
        if self._pubsub_task is not None:
            return
        self._pubsub_task = asyncio.create_task(self._pubsub_loop())
        logger.info("Started Redis pub/sub listener for agent messages")

    async def stop_pubsub_listener(self) -> None:
        """Redis pub/sub 리스너 중지."""
        if self._pubsub_task is not None:
            self._pubsub_task.cancel()
            self._pubsub_task = None
            logger.info("Stopped Redis pub/sub listener")

    async def _pubsub_loop(self) -> None:
        """Redis pub/sub 수신 루프."""
        try:
            from app.core.redis import redis_client

            pubsub = redis_client.pubsub()
            await pubsub.subscribe(_PUBSUB_CHANNEL)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    import json
                    data = json.loads(message["data"])
                    target_agent_id = data.get("target_agent_id")
                    if target_agent_id:
                        from uuid import UUID
                        agent_uuid = UUID(target_agent_id)
                        ws = self._connections.get(agent_uuid)
                        if ws is not None:
                            payload = data.get("payload", {})
                            await ws.send_json(payload)
                except Exception as exc:
                    logger.debug("pub/sub message handling error: %s", exc)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("pub/sub listener error: %s", exc)

    async def _publish_to_agent(self, agent_id: UUID, payload: dict) -> None:
        """Redis pub/sub로 다른 인스턴스의 에이전트에 메시지 전달."""
        try:
            from app.core.redis import redis_client
            import json

            message = json.dumps({
                "target_agent_id": str(agent_id),
                "payload": payload,
            })
            await redis_client.publish(_PUBSUB_CHANNEL, message)
        except Exception:
            logger.debug("Failed to publish message to agent %s via Redis", agent_id)

    async def wait_for_connection(self, agent_id: UUID, timeout: float) -> bool:
        """에이전트 접속 대기. timeout 초 내에 접속하면 True."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if self.is_connected(agent_id):
                return True
            await asyncio.sleep(0.5)
        return self.is_connected(agent_id)
