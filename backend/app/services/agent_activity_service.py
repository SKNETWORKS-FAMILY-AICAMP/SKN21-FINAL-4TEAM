"""AI 에이전트 자동 활동 서비스.

페르소나가 게시판에서 자율적으로 댓글/게시글을 생성하는 핵심 로직.
소유자의 크레딧을 차감하고, 일일 한도를 관리한다.
"""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_activity_log import AgentActivityLog
from app.models.board_comment import BoardComment
from app.models.board_post import BoardPost
from app.models.llm_model import LLMModel
from app.models.persona import Persona
from app.models.persona_lounge_config import PersonaLoungeConfig
from app.models.user import User
from app.pipeline.pii import get_pii_detector
from app.prompt.compiler import PromptCompiler
from app.prompt.persona_loader import PersonaLoader
from app.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)

# 게시판 활동용 프롬프트 컨텍스트
BOARD_COMMENT_CONTEXT = (
    "You are participating in a community board as a character. "
    "Write a short, in-character comment responding to the post below. "
    "Stay in character and keep your response under 150 tokens. "
    "Write naturally in Korean."
)

BOARD_POST_CONTEXT = (
    "You are participating in a community board as a character. "
    "Write a short, casual post sharing your thoughts or daily life in character. "
    "Keep it under 200 tokens. Write naturally in Korean."
)


class AgentActivityService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.compiler = PromptCompiler()
        self.loader = PersonaLoader(db)
        self.inference = InferenceClient()

    async def process_new_post(self, post: BoardPost) -> list[BoardComment]:
        """새 게시글에 반응할 페르소나를 선택하고 댓글을 생성한다."""
        # 활성 라운지 페르소나 조회
        configs = await self._get_eligible_configs(post.board_id)
        if not configs:
            return []

        # 관심도 기반 필터링 (최대 3개 선택)
        selected = self._select_responders(configs, post, max_count=3)
        comments = []

        for config in selected:
            try:
                comment = await self._generate_comment(config, post)
                if comment:
                    comments.append(comment)
            except Exception:
                logger.warning("Agent comment failed for persona %s", config.persona_id, exc_info=True)

        return comments

    async def generate_persona_post(self, config: PersonaLoungeConfig) -> BoardPost | None:
        """페르소나가 자발적으로 게시글을 작성한다 (스케줄러에서 호출)."""
        if not config.is_active or config.activity_level != "active":
            return None

        if config.actions_today >= config.daily_action_limit:
            return None

        # 세분화 한도 체크
        if config.posts_today >= config.daily_post_limit:
            return None

        # 소유자 확인 + 크레딧 체크
        persona = await self._get_persona(config.persona_id)
        if persona is None or persona.created_by is None:
            return None

        owner_id = persona.created_by

        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            sufficient = await credit_svc.check_balance_sufficient(owner_id, "agent_action", "economy")
            if not sufficient:
                logger.info("Insufficient credits for persona %s owner %s", config.persona_id, owner_id)
                return None

        # LLM 모델 선택 (경제형 기본)
        llm_model = await self._get_economy_model()
        if llm_model is None:
            return None

        # 세계관 이벤트 로드
        from app.services.world_event_service import WorldEventService

        world_svc = WorldEventService(self.db)
        world_events = await world_svc.get_active_events(persona.age_rating if persona else "all")
        world_text = world_svc.format_for_prompt(world_events)

        # 페르소나 데이터 로드 + 프롬프트 빌드
        persona_data = await self.loader.load(config.persona_id)
        messages = self._build_post_prompt(persona_data, world_text=world_text)

        # LLM 호출
        result = await self.inference.generate(llm_model, messages, max_tokens=200)

        # PII 마스킹
        pii = get_pii_detector()
        safe_content = pii.mask(result["content"])

        # 게시판 선택 (allowed_boards 중 첫 번째, 없으면 스킵)
        board_id = None
        if config.allowed_boards:
            board_id = config.allowed_boards[0]
        else:
            return None

        # 크레딧 차감 (생성 시점에 — LLM 호출 이미 발생)
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            await credit_svc.check_and_deduct(
                owner_id,
                "agent_action",
                "economy",
                reference_id=str(config.persona_id),
            )

        cost = self._calc_cost(llm_model, result)

        # publishing_mode에 따라 직접 게시 또는 pending 큐로
        if config.publishing_mode == "manual":
            from app.services.pending_post_service import PendingPostService

            pending_svc = PendingPostService(self.db)
            pending = await pending_svc.create_pending(
                persona_id=config.persona_id,
                owner_user_id=owner_id,
                content_type="post",
                content=safe_content,
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
                cost=cost,
            )

            # 소유자에게 알림
            from app.services.notification_service import NotificationService

            notif_svc = NotificationService(self.db)
            await notif_svc.create(
                user_id=owner_id,
                type_="pending_post",
                title="게시물 승인 대기",
                body=f"{persona.display_name}이(가) 새 게시물을 작성했습니다. 승인을 기다리고 있습니다.",
                link="/pending-posts",
            )

            # 활동 로그 기록
            log = AgentActivityLog(
                persona_id=config.persona_id,
                owner_user_id=owner_id,
                action_type="post_pending",
                llm_model_id=llm_model.id,
                input_tokens=result.get("input_tokens"),
                output_tokens=result.get("output_tokens"),
                cost=cost,
            )
            self.db.add(log)

            await self._increment_actions(config, action_type="post")
            await self.db.commit()
            logger.info("Agent post pending: persona=%s pending=%s", config.persona_id, pending.id)
            return None

        # auto 모드: 직접 게시
        post = BoardPost(
            board_id=board_id,
            author_persona_id=config.persona_id,
            content=safe_content,
            is_ai_generated=True,
        )
        self.db.add(post)

        # post_count 갱신
        await self.db.execute(
            update(Persona).where(Persona.id == config.persona_id).values(post_count=Persona.post_count + 1)
        )

        # 활동 로그 기록
        log = AgentActivityLog(
            persona_id=config.persona_id,
            owner_user_id=owner_id,
            action_type="post",
            result_post_id=post.id,
            llm_model_id=llm_model.id,
            input_tokens=result.get("input_tokens"),
            output_tokens=result.get("output_tokens"),
            cost=cost,
        )
        self.db.add(log)

        # 일일 카운터 갱신
        await self._increment_actions(config, action_type="post")
        await self.db.commit()
        await self.db.refresh(post)

        logger.info("Agent post created: persona=%s post=%s", config.persona_id, post.id)
        return post

    # ── 라운지 설정 CRUD ──

    async def get_config(self, persona_id: uuid.UUID, user: User) -> PersonaLoungeConfig:
        """라운지 설정 조회. 없으면 기본 생성."""
        await self._verify_persona_ownership(persona_id, user)

        result = await self.db.execute(select(PersonaLoungeConfig).where(PersonaLoungeConfig.persona_id == persona_id))
        config = result.scalar_one_or_none()

        if config is None:
            config = PersonaLoungeConfig(persona_id=persona_id)
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)

        return config

    async def update_config(
        self,
        persona_id: uuid.UUID,
        user: User,
        activity_level: str | None = None,
        interest_tags: list[str] | None = None,
        allowed_boards: list[uuid.UUID] | None = None,
        publishing_mode: str | None = None,
        daily_post_limit: int | None = None,
        daily_comment_limit: int | None = None,
        daily_chat_limit: int | None = None,
        auto_comment_reply: bool | None = None,
        accept_chat_requests: bool | None = None,
        auto_accept_chats: bool | None = None,
    ) -> PersonaLoungeConfig:
        """라운지 설정 변경."""
        config = await self.get_config(persona_id, user)

        if activity_level is not None:
            config.activity_level = activity_level
        if interest_tags is not None:
            config.interest_tags = interest_tags
        if allowed_boards is not None:
            config.allowed_boards = allowed_boards
        if publishing_mode is not None:
            config.publishing_mode = publishing_mode
        if daily_post_limit is not None:
            config.daily_post_limit = daily_post_limit
        if daily_comment_limit is not None:
            config.daily_comment_limit = daily_comment_limit
        if daily_chat_limit is not None:
            config.daily_chat_limit = daily_chat_limit
        if auto_comment_reply is not None:
            config.auto_comment_reply = auto_comment_reply
        if accept_chat_requests is not None:
            config.accept_chat_requests = accept_chat_requests
        if auto_accept_chats is not None:
            config.auto_accept_chats = auto_accept_chats

        config.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def activate(self, persona_id: uuid.UUID, user: User) -> PersonaLoungeConfig:
        """라운지 참여 시작."""
        config = await self.get_config(persona_id, user)
        config.is_active = True
        config.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def deactivate(self, persona_id: uuid.UUID, user: User) -> PersonaLoungeConfig:
        """라운지 참여 중단."""
        config = await self.get_config(persona_id, user)
        config.is_active = False
        config.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(config)
        return config

    async def get_activity_log(
        self, persona_id: uuid.UUID, user: User, skip: int = 0, limit: int = 20
    ) -> dict[str, Any]:
        """페르소나 활동 로그 조회."""
        await self._verify_persona_ownership(persona_id, user)

        count_q = select(func.count()).select_from(AgentActivityLog).where(AgentActivityLog.persona_id == persona_id)
        total = (await self.db.execute(count_q)).scalar()

        q = (
            select(AgentActivityLog)
            .where(AgentActivityLog.persona_id == persona_id)
            .order_by(AgentActivityLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(q)
        items = list(result.scalars().all())

        return {"items": items, "total": total}

    # ── 관리자 ──

    async def get_admin_summary(self) -> dict[str, Any]:
        """전체 에이전트 활동 통계."""
        now = datetime.now(UTC)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_today = (
            await self.db.execute(
                select(func.count()).select_from(AgentActivityLog).where(AgentActivityLog.created_at >= today)
            )
        ).scalar()

        total_all = (await self.db.execute(select(func.count()).select_from(AgentActivityLog))).scalar()

        active_personas = (
            await self.db.execute(
                select(func.count()).select_from(PersonaLoungeConfig).where(PersonaLoungeConfig.is_active == True)
            )
        ).scalar()

        tokens_today = (
            await self.db.execute(
                select(
                    func.coalesce(func.sum(AgentActivityLog.input_tokens), 0),
                    func.coalesce(func.sum(AgentActivityLog.output_tokens), 0),
                ).where(AgentActivityLog.created_at >= today)
            )
        ).one()

        cost_today = (
            await self.db.execute(
                select(func.coalesce(func.sum(AgentActivityLog.cost), 0)).where(AgentActivityLog.created_at >= today)
            )
        ).scalar()

        return {
            "total_actions_today": int(total_today),
            "total_actions_all": int(total_all),
            "active_personas": int(active_personas),
            "total_tokens_today": int(tokens_today[0]) + int(tokens_today[1]),
            "total_cost_today": float(cost_today),
        }

    async def get_admin_cost_stats(self) -> list[dict]:
        """에이전트 LLM 비용 통계 (페르소나별)."""
        q = (
            select(
                AgentActivityLog.persona_id,
                func.count(AgentActivityLog.id).label("action_count"),
                func.coalesce(func.sum(AgentActivityLog.input_tokens), 0).label("total_input"),
                func.coalesce(func.sum(AgentActivityLog.output_tokens), 0).label("total_output"),
                func.coalesce(func.sum(AgentActivityLog.cost), 0).label("total_cost"),
            )
            .group_by(AgentActivityLog.persona_id)
            .order_by(func.sum(AgentActivityLog.cost).desc())
            .limit(50)
        )
        result = await self.db.execute(q)
        return [
            {
                "persona_id": row.persona_id,
                "action_count": row.action_count,
                "total_input_tokens": int(row.total_input),
                "total_output_tokens": int(row.total_output),
                "total_cost": float(row.total_cost),
            }
            for row in result.all()
        ]

    # ── 내부 헬퍼 ──

    async def _get_eligible_configs(self, board_id: uuid.UUID) -> list[PersonaLoungeConfig]:
        """활성이고 일일 한도 미달인 라운지 설정 조회."""
        q = select(PersonaLoungeConfig).where(
            PersonaLoungeConfig.is_active == True,
            PersonaLoungeConfig.actions_today < PersonaLoungeConfig.daily_action_limit,
        )
        result = await self.db.execute(q)
        configs = list(result.scalars().all())

        # board_id 필터: allowed_boards가 비어있거나 해당 board_id 포함
        return [c for c in configs if not c.allowed_boards or board_id in (c.allowed_boards or [])]

    def _select_responders(
        self,
        configs: list[PersonaLoungeConfig],
        post: BoardPost,
        max_count: int = 3,
    ) -> list[PersonaLoungeConfig]:
        """관심도 + activity_level 기반으로 반응 페르소나 선택."""
        import random

        # activity_level별 반응 확률 가중치
        weight_map = {"quiet": 0.2, "normal": 0.5, "active": 0.8}

        candidates = []
        for config in configs:
            # 자기 글에는 반응하지 않음
            if post.author_persona_id == config.persona_id:
                continue

            weight = weight_map.get(config.activity_level, 0.5)

            # interest_tags가 있으면 태그 매칭으로 가중치 조절
            if config.interest_tags and post.content:
                matched = sum(1 for tag in config.interest_tags if tag.lower() in post.content.lower())
                if matched > 0:
                    weight = min(weight + 0.3, 1.0)

            if random.random() < weight:
                candidates.append(config)

        random.shuffle(candidates)
        return candidates[:max_count]

    async def _generate_comment(self, config: PersonaLoungeConfig, post: BoardPost) -> BoardComment | None:
        """단일 페르소나의 댓글 생성."""
        # 세분화 한도 체크
        if config.comments_today >= config.daily_comment_limit:
            return None

        persona = await self._get_persona(config.persona_id)
        if persona is None or persona.created_by is None:
            return None

        owner_id = persona.created_by

        # 크레딧 체크 + 차감
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            sufficient = await credit_svc.check_balance_sufficient(owner_id, "agent_action", "economy")
            if not sufficient:
                return None
            await credit_svc.check_and_deduct(
                owner_id,
                "agent_action",
                "economy",
                reference_id=str(post.id),
            )

        # LLM 모델
        llm_model = await self._get_economy_model()
        if llm_model is None:
            return None

        # 세계관 이벤트 로드
        from app.services.world_event_service import WorldEventService

        world_svc = WorldEventService(self.db)
        world_events = await world_svc.get_active_events(persona.age_rating if persona else "all")
        world_text = world_svc.format_for_prompt(world_events)

        # 프롬프트 빌드
        persona_data = await self.loader.load(config.persona_id)
        messages = self._build_comment_prompt(persona_data, post, world_text=world_text)

        # LLM 호출
        result = await self.inference.generate(llm_model, messages, max_tokens=150)

        # PII 마스킹
        pii = get_pii_detector()
        safe_content = pii.mask(result["content"])

        cost = self._calc_cost(llm_model, result)

        # publishing_mode에 따라 분기
        if config.publishing_mode == "manual":
            from app.services.pending_post_service import PendingPostService

            pending_svc = PendingPostService(self.db)
            await pending_svc.create_pending(
                persona_id=config.persona_id,
                owner_user_id=owner_id,
                content_type="comment",
                content=safe_content,
                target_post_id=post.id,
                input_tokens=result.get("input_tokens", 0),
                output_tokens=result.get("output_tokens", 0),
                cost=cost,
            )

            log = AgentActivityLog(
                persona_id=config.persona_id,
                owner_user_id=owner_id,
                action_type="comment_pending",
                target_post_id=post.id,
                llm_model_id=llm_model.id,
                input_tokens=result.get("input_tokens"),
                output_tokens=result.get("output_tokens"),
                cost=cost,
            )
            self.db.add(log)
            await self._increment_actions(config, action_type="comment")
            await self.db.flush()
            logger.info("Agent comment pending: persona=%s post=%s", config.persona_id, post.id)
            return None

        # auto 모드: 직접 댓글
        comment = BoardComment(
            post_id=post.id,
            author_persona_id=config.persona_id,
            content=safe_content,
            is_ai_generated=True,
        )
        self.db.add(comment)

        # 게시글 댓글 카운터 갱신
        await self.db.execute(
            update(BoardPost).where(BoardPost.id == post.id).values(comment_count=BoardPost.comment_count + 1)
        )

        # 활동 로그
        log = AgentActivityLog(
            persona_id=config.persona_id,
            owner_user_id=owner_id,
            action_type="comment",
            target_post_id=post.id,
            result_comment_id=comment.id,
            llm_model_id=llm_model.id,
            input_tokens=result.get("input_tokens"),
            output_tokens=result.get("output_tokens"),
            cost=cost,
        )
        self.db.add(log)

        # 일일 카운터 갱신
        await self._increment_actions(config, action_type="comment")
        await self.db.flush()

        logger.info("Agent comment: persona=%s post=%s", config.persona_id, post.id)
        return comment

    def _build_comment_prompt(self, persona_data: dict, post: BoardPost, world_text: str = "") -> list[dict]:
        """댓글 생성용 프롬프트."""
        messages = [
            {"role": "system", "content": PromptCompiler.POLICY_LAYER},
        ]
        if world_text:
            messages.append({"role": "system", "content": world_text})
        messages.append({"role": "system", "content": PromptCompiler._build_persona_block(persona_data)})
        messages.append({"role": "system", "content": BOARD_COMMENT_CONTEXT})

        # 원글 내용
        post_text = f"[게시글]\n{post.title or ''}\n{post.content}"
        messages.append({"role": "user", "content": post_text})

        return messages

    def _build_post_prompt(self, persona_data: dict, world_text: str = "") -> list[dict]:
        """자발적 게시글 생성용 프롬프트."""
        messages = [
            {"role": "system", "content": PromptCompiler.POLICY_LAYER},
        ]
        if world_text:
            messages.append({"role": "system", "content": world_text})
        messages.append({"role": "system", "content": PromptCompiler._build_persona_block(persona_data)})
        messages.append({"role": "system", "content": BOARD_POST_CONTEXT})
        messages.append({"role": "user", "content": "오늘의 이야기를 자유롭게 작성해줘."})
        return messages

    async def _get_persona(self, persona_id: uuid.UUID) -> Persona | None:
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        return result.scalar_one_or_none()

    async def _get_economy_model(self) -> LLMModel | None:
        """경제형 활성 모델 조회. 없으면 아무 활성 모델."""
        result = await self.db.execute(
            select(LLMModel).where(LLMModel.is_active == True, LLMModel.tier == "economy").limit(1)
        )
        model = result.scalar_one_or_none()
        if model:
            return model

        result = await self.db.execute(select(LLMModel).where(LLMModel.is_active == True).limit(1))
        return result.scalar_one_or_none()

    async def _verify_persona_ownership(self, persona_id: uuid.UUID, user: User) -> Persona:
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id, Persona.created_by == user.id))
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your persona")
        return persona

    async def _increment_actions(self, config: PersonaLoungeConfig, action_type: str = "post") -> None:
        values: dict = {
            "actions_today": PersonaLoungeConfig.actions_today + 1,
            "last_action_at": datetime.now(UTC),
        }
        if action_type == "post":
            values["posts_today"] = PersonaLoungeConfig.posts_today + 1
        elif action_type == "comment":
            values["comments_today"] = PersonaLoungeConfig.comments_today + 1

        await self.db.execute(
            update(PersonaLoungeConfig)
            .where(PersonaLoungeConfig.id == config.id)
            .values(**values)
        )

    @staticmethod
    def _calc_cost(model: LLMModel, result: dict) -> Decimal:
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        input_cost = Decimal(str(input_tokens)) * Decimal(str(model.input_cost_per_1m)) / Decimal("1000000")
        output_cost = Decimal(str(output_tokens)) * Decimal(str(model.output_cost_per_1m)) / Decimal("1000000")
        return input_cost + output_cost
