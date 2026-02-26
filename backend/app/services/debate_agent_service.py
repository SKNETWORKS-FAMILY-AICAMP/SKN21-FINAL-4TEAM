import logging
from datetime import UTC, datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_api_key
from app.models.debate_agent import DebateAgent
from app.models.debate_agent_version import DebateAgentVersion
from app.models.user import User
from app.schemas.debate_agent import AgentCreate, AgentUpdate
from app.services.debate_template_service import DebateTemplateService

logger = logging.getLogger(__name__)


def get_tier_from_elo(elo: int) -> str:
    """ELO 기반 티어 계산."""
    if elo >= 2050:
        return "Master"
    elif elo >= 1900:
        return "Diamond"
    elif elo >= 1750:
        return "Platinum"
    elif elo >= 1600:
        return "Gold"
    elif elo >= 1450:
        return "Silver"
    elif elo >= 1300:
        return "Bronze"
    else:
        return "Iron"


class DebateAgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_agent(self, data: AgentCreate, user: User) -> DebateAgent:
        """에이전트 생성 + 초기 버전 자동 생성.

        생성 경로:
        1. template_id 있음 → 템플릿 로드 → 커스터마이징 검증 → 프롬프트 조립
        2. template_id 없음 + non-local → BYOK (system_prompt + api_key 필수)
        3. template_id 없음 + local → 로컬 에이전트 (API 키 불필요)
        """
        is_local = data.provider == "local"
        template_service = DebateTemplateService(self.db)

        # API 키 처리
        encrypted_key = None
        if not is_local and data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)
        elif not is_local and data.template_id is None:
            # BYOK 경로: api_key 필수
            raise ValueError("API key is required for non-local providers")

        # 시스템 프롬프트 결정
        if data.template_id is not None:
            # 템플릿 기반 경로
            template = await template_service.get_template(data.template_id)
            if template is None:
                raise ValueError("Template not found")
            if not template.is_active:
                raise ValueError("Template is not active")

            validated = template_service.validate_customizations(
                template, data.customizations, data.enable_free_text
            )
            prompt = template_service.assemble_prompt(template, validated)
        elif is_local:
            # 로컬 에이전트 기본값
            template = None
            validated = None
            prompt = data.system_prompt or "(로컬 에이전트 — 프롬프트 로컬 관리)"
        else:
            # BYOK 경로
            if not data.system_prompt:
                raise ValueError("System prompt is required for API agents")
            template = None
            validated = None
            prompt = data.system_prompt

        agent = DebateAgent(
            owner_id=user.id,
            name=data.name,
            description=data.description,
            provider=data.provider,
            model_id=data.model_id,
            encrypted_api_key=encrypted_key,
            image_url=data.image_url,
            is_system_prompt_public=data.is_system_prompt_public,
            template_id=template.id if template else None,
            customizations=validated,
        )
        self.db.add(agent)
        await self.db.flush()

        version = DebateAgentVersion(
            agent_id=agent.id,
            version_number=1,
            version_tag=data.version_tag or "v1",
            system_prompt=prompt,
            parameters=data.parameters,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def update_agent(self, agent_id: str, data: AgentUpdate, user: User) -> DebateAgent:
        """에이전트 수정. 프롬프트/커스터마이징 변경 시 새 버전 자동 생성."""
        result = await self.db.execute(
            select(DebateAgent).where(DebateAgent.id == agent_id, DebateAgent.owner_id == user.id)
        )
        agent = result.scalar_one_or_none()
        if agent is None:
            raise ValueError("Agent not found or not owned by user")

        if data.name is not None and data.name != agent.name:
            # 이름 변경 7일 제한
            if agent.name_changed_at is not None:
                days_since = (datetime.now(UTC) - agent.name_changed_at).days
                if days_since < 7:
                    days_left = 7 - days_since
                    raise ValueError(f"이름은 7일에 한 번만 변경할 수 있습니다 ({days_left}일 후 변경 가능)")
            agent.name = data.name
            agent.name_changed_at = datetime.now(UTC)
        elif data.name is not None:
            agent.name = data.name
        if data.description is not None:
            agent.description = data.description
        if data.provider is not None:
            agent.provider = data.provider
        if data.model_id is not None:
            agent.model_id = data.model_id
        if data.api_key is not None and agent.provider != "local":
            agent.encrypted_api_key = encrypt_api_key(data.api_key)
        if data.image_url is not None:
            agent.image_url = data.image_url
        if data.is_system_prompt_public is not None:
            agent.is_system_prompt_public = data.is_system_prompt_public
        if data.is_profile_public is not None:
            agent.is_profile_public = data.is_profile_public

        # 새 버전 생성이 필요한지 판단
        new_prompt: str | None = None

        if data.customizations is not None and agent.template_id is not None:
            # 템플릿 커스터마이징 변경 → 프롬프트 재조립
            template_service = DebateTemplateService(self.db)
            template = await template_service.get_template(agent.template_id)
            if template is None:
                raise ValueError("Associated template not found")
            validated = template_service.validate_customizations(
                template, data.customizations, data.enable_free_text
            )
            new_prompt = template_service.assemble_prompt(template, validated)
            agent.customizations = validated
        elif data.system_prompt is not None:
            # 직접 프롬프트 수정 (BYOK/로컬)
            new_prompt = data.system_prompt

        if new_prompt is not None:
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
                system_prompt=new_prompt,
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

    async def get_ranking(
        self, limit: int = 50, offset: int = 0, search: str | None = None, tier: str | None = None
    ) -> list[dict]:
        """ELO 기준 글로벌 랭킹 조회. search: 에이전트명/소유자명, tier: 티어 필터."""
        query = (
            select(DebateAgent, User.nickname)
            .join(User, DebateAgent.owner_id == User.id)
            .where(DebateAgent.is_active == True)  # noqa: E712
        )

        if search:
            like = f"%{search}%"
            query = query.where(
                (DebateAgent.name.ilike(like)) | (User.nickname.ilike(like))
            )

        if tier:
            query = query.where(DebateAgent.tier == tier)

        query = query.order_by(DebateAgent.elo_rating.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
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
                "image_url": agent.image_url,
                "tier": agent.tier,
                "is_profile_public": agent.is_profile_public,
            }
            for agent, nickname in rows
        ]

    async def get_my_ranking(self, user: User) -> list[dict]:
        """내 에이전트들의 랭킹 순위 반환."""
        from sqlalchemy import func as sqlfunc
        # 전체 에이전트 중 내 에이전트들의 순위 계산
        # rank = 내 ELO보다 높은 에이전트 수 + 1
        result = await self.db.execute(
            select(DebateAgent).where(
                DebateAgent.owner_id == user.id,
                DebateAgent.is_active == True,  # noqa: E712
            ).order_by(DebateAgent.elo_rating.desc())
        )
        my_agents = list(result.scalars().all())

        rankings = []
        for agent in my_agents:
            count_result = await self.db.execute(
                select(sqlfunc.count(DebateAgent.id)).where(
                    DebateAgent.is_active == True,  # noqa: E712
                    DebateAgent.elo_rating > agent.elo_rating,
                )
            )
            rank = (count_result.scalar() or 0) + 1
            rankings.append({
                "id": str(agent.id),
                "name": agent.name,
                "elo_rating": agent.elo_rating,
                "tier": agent.tier,
                "image_url": agent.image_url,
                "rank": rank,
            })
        return rankings

    async def delete_agent(self, agent_id: str, user: User) -> None:
        """에이전트 삭제. 소유자만 삭제 가능. 진행 중인 매치가 있으면 삭제 불가."""
        from app.models.debate_match import DebateMatch

        agent = await self.db.get(DebateAgent, agent_id)
        if agent is None:
            raise ValueError("Agent not found")
        if agent.owner_id != user.id:
            raise PermissionError("Permission denied")

        # 진행 중인 매치 확인
        active_result = await self.db.execute(
            select(func.count(DebateMatch.id)).where(
                (DebateMatch.agent_a_id == agent_id) | (DebateMatch.agent_b_id == agent_id),
                DebateMatch.status == "in_progress",
            )
        )
        active_count = active_result.scalar() or 0
        if active_count > 0:
            raise ValueError("진행 중인 매치가 있어 삭제할 수 없습니다.")

        # 에이전트 버전 먼저 삭제 (FK 제약)
        await self.db.execute(
            sa_delete(DebateAgentVersion).where(DebateAgentVersion.agent_id == agent_id)
        )
        await self.db.delete(agent)
        await self.db.commit()

    async def update_elo(
        self, agent_id: str, new_elo: int, result_type: str, version_id: str | None = None
    ) -> None:
        """ELO 및 전적 갱신 + 티어 계산 및 강등 보호. result_type: 'win' | 'loss' | 'draw'."""
        # 현재 에이전트 상태 조회 (티어 보호 로직에 필요)
        result = await self.db.execute(select(DebateAgent).where(DebateAgent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None:
            return

        new_tier = get_tier_from_elo(new_elo)
        old_tier = agent.tier

        updates: dict = {"elo_rating": new_elo}

        if result_type == "win":
            updates["wins"] = DebateAgent.wins + 1
        elif result_type == "loss":
            updates["losses"] = DebateAgent.losses + 1
        else:
            updates["draws"] = DebateAgent.draws + 1

        # 티어 변경 로직
        tier_order = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"]
        old_idx = tier_order.index(old_tier) if old_tier in tier_order else 0
        new_idx = tier_order.index(new_tier) if new_tier in tier_order else 0

        if new_idx > old_idx:
            # 승급: 티어 갱신 + 보호 횟수 3 부여
            updates["tier"] = new_tier
            updates["tier_protection_count"] = 3
        elif new_idx < old_idx:
            # 강등 대상: 보호 있으면 유지, 없으면 강등
            if agent.tier_protection_count > 0:
                updates["tier_protection_count"] = DebateAgent.tier_protection_count - 1
                # 티어는 유지 (updates에 tier 없음)
            else:
                updates["tier"] = new_tier
        # else: 같은 티어면 아무 변경 없음

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
