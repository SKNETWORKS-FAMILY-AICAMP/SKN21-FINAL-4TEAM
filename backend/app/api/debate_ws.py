"""로컬 에이전트 WebSocket 엔드포인트."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import decode_access_token
from app.core.config import settings
from app.core.database import async_session
from app.models.debate_agent import DebateAgent
from app.models.user import User
from app.services.debate_ws_manager import WSConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authenticate_ws(token: str, db: AsyncSession) -> tuple[User, None] | tuple[None, str]:
    """JWT 토큰으로 WebSocket 사용자 인증."""
    payload = decode_access_token(token)
    if payload is None:
        return None, "Invalid or expired token"

    user_id = payload.get("sub")
    if not user_id:
        return None, "Invalid token payload"

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None, "User not found"

    return user, None


@router.websocket("/ws/agent/{agent_id}")
async def agent_websocket(
    websocket: WebSocket,
    agent_id: UUID,
    token: str = Query(...),
) -> None:
    """로컬 에이전트 WebSocket 엔드포인트."""
    # 인증/권한 검증은 accept 전에 수행하고, 실패 시 accept 후 close
    async with async_session() as db:
        # 1. JWT 검증
        user, error = await _authenticate_ws(token, db)
        if user is None:
            await websocket.accept()
            await websocket.close(code=4001, reason=error)
            return

        # 2. 에이전트 소유권 + provider 검증
        result = await db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id)
        )
        agent = result.scalar_one_or_none()

        if agent is None:
            await websocket.accept()
            await websocket.close(code=4004, reason="Agent not found")
            return
        if agent.owner_id != user.id:
            await websocket.accept()
            await websocket.close(code=4003, reason="Not owner of this agent")
            return
        if agent.provider != "local":
            await websocket.accept()
            await websocket.close(code=4003, reason="Agent is not a local provider")
            return

    # 3. WebSocket 수락 + 연결 등록
    await websocket.accept()
    manager = WSConnectionManager.get_instance()
    await manager.connect(agent_id, websocket)

    # 4. heartbeat 태스크
    async def heartbeat_loop() -> None:
        while True:
            await asyncio.sleep(settings.debate_ws_heartbeat_interval)
            try:
                await manager.send_ping(agent_id)
            except Exception:
                break

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        # 5. 메시지 수신 루프
        while True:
            data = await websocket.receive_json()
            await manager.handle_message(agent_id, data)
    except WebSocketDisconnect:
        logger.info("Agent %s WebSocket disconnected normally", agent_id)
    except Exception as exc:
        logger.warning("Agent %s WebSocket error: %s", agent_id, exc)
    finally:
        heartbeat_task.cancel()
        await manager.disconnect(agent_id)
