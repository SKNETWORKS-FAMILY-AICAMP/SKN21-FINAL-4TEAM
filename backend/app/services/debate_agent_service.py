import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.encryption import encrypt_api_key
from app.models.debate_agent import DebateAgent
from app.models.debate_agent_version import DebateAgentVersion
from app.models.user import User
from app.schemas.debate_agent import AgentCreate, AgentUpdate

logger = logging.getLogger(__name__)


class DebateAgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_agent(self, data: AgentCreate, user: User) -> DebateAgent:
        """에이전트 생성 + 초기 버전 자동 생성."""
        # local 에이전트는 API 키 불필요
        encrypted_key = None
        if data.provider != "local" and data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)
        elif data.provider != "local":
            raise ValueError("API key is required for non-local providers")

        agent = DebateAgent(
            owner_id=user.id,
            name=data.name,
            description=data.description,
            provider=data.provider,
            model_id=data.model_id,
            encrypted_api_key=encrypted_key,
        )
        self.db.add(agent)
        await self.db.flush()

        version = DebateAgentVersion(
            agent_id=agent.id,
            version_number=1,
            version_tag=data.version_tag or "v1",
            system_prompt=data.system_prompt,
            parameters=data.parameters,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def update_agent(self, agent_id: str, data: AgentUpdate, user: User) -> DebateAgent:
        """에이전트 수정. 프롬프트 변경 시 새 버전 자동 생성."""
        result = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id, DebateAgent.owner_id == user.id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError("Agent not found or not owned by user")

        if data.name is not None:
            agent.name = data.name
        if data.description is not None:
            agent.description = data.description
        if data.provider is not None:
            agent.provider = data.provider
        if data.model_id is not None:
            agent.model_id = data.model_id
        if data.api_key is not None and agent.provider != "local":
            agent.encrypted_api_key = encrypt_api_key(data.api_key)

        # 프롬프트 변경 시 새 버전 생성
        if data.system_prompt is not None:
            max_ver = await self.db.execute(
                select(func.coalesce(func.max(DebateAgentVersion.version_number), 0)).where(
                    DebateAgentVersion.agent_id == agent.id
                )
            )
            next_ver = max_ver.scalar() + 1
            version = DebateAgentVersion(
                agent_id=agent.id,
                version_number=next_ver,
                version_tag=data.version_tag or f"v{next_ver}",
                system_prompt=data.system_prompt,
                parameters=data.parameters,
            )
            self.db.add(version)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_agent(self, agent_id: str) -> DebateAgent | None:
        result = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_my_agents(self, user: User) -> list[DebateAgent]:
        result = await self.db.execute(
            select(DebateAgent)
            .where(DebateAgent.owner_id == user.id)
            .order_by(DebateAgent.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_agent_versions(self, agent_id: str) -> list[DebateAgentVersion]:
        result = await self.db.execute(
            select(DebateAgentVersion)
            .where(DebateAgentVersion.agent_id == agent_id)
            .order_by(DebateAgentVersion.version_number.desc())
        )
        return list(result.scalars().all())

    async def get_latest_version(self, agent_id: str) -> DebateAgentVersion | None:
        result = await self.db.execute(
            select(DebateAgentVersion)
            .where(DebateAgentVersion.agent_id == agent_id)
            .order_by(DebateAgentVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_ranking(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """ELO 기준 글로벌 랭킹 조회."""
        result = await self.db.execute(
            select(DebateAgent, User.nickname)
            .join(User, DebateAgent.owner_id == User.id)
            .where(DebateAgent.is_active == True)
            .order_by(DebateAgent.elo_rating.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = result.all()
        return [
            {
                "id": str(agent.id),
                "name": agent.name,
                "owner_nickname": nickname,
                "provider": agent.provider,
                "model_id": agent.model_id,
                "elo_rating": agent.elo_rating,
                "wins": agent.wins,
                "losses": agent.losses,
                "draws": agent.draws,
            }
            for agent, nickname in rows
        ]

    async def update_elo(
        self, agent_id: str, new_elo: int, result_type: str, version_id: str | None = None
    ) -> None:
        """ELO 및 전적 갱신. result_type: 'win' | 'loss' | 'draw'."""
        updates: dict = {"elo_rating": new_elo}
        if result_type == "win":
            updates["wins"] = DebateAgent.wins + 1
        elif result_type == "loss":
            updates["losses"] = DebateAgent.losses + 1
        else:
            updates["draws"] = DebateAgent.draws + 1

        await self.db.execute(
            update(DebateAgent).where(DebateAgent.id == agent_id).values(**updates)
        )

        # 버전별 전적도 갱신
        if version_id:
            ver_updates: dict = {}
            if result_type == "win":
                ver_updates["wins"] = DebateAgentVersion.wins + 1
            elif result_type == "loss":
                ver_updates["losses"] = DebateAgentVersion.losses + 1
            else:
                ver_updates["draws"] = DebateAgentVersion.draws + 1
            await self.db.execute(
                update(DebateAgentVersion)
                .where(DebateAgentVersion.id == version_id)
                .values(**ver_updates)
            )
