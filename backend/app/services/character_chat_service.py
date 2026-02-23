"""캐릭터 간 1:1 대화 서비스.

캐릭터끼리 대화하는 세션을 관리한다. 소유자가 요청/수락하고,
각 턴마다 LLM을 호출해 캐릭터의 대사를 생성한다.
"""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.character_chat_message import CharacterChatMessage
from app.models.character_chat_session import CharacterChatSession
from app.models.llm_model import LLMModel
from app.models.persona import Persona
from app.models.persona_lounge_config import PersonaLoungeConfig
from app.models.user import User
from app.pipeline.pii import get_pii_detector
from app.prompt.compiler import PromptCompiler
from app.prompt.persona_loader import PersonaLoader
from app.services.inference_client import InferenceClient
from app.services.notification_service import NotificationService
from app.services.world_event_service import WorldEventService

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SESSIONS_PER_USER = 3

CHARACTER_CHAT_CONTEXT = (
    "You are having a 1-on-1 conversation with another character. "
    "Stay fully in character. Respond naturally to what the other character says. "
    "Write in Korean. Keep your response under 200 tokens."
)


class CharacterChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.compiler = PromptCompiler()
        self.loader = PersonaLoader(db)
        self.inference = InferenceClient()

    async def request_chat(
        self,
        requester_persona_id: uuid.UUID,
        responder_persona_id: uuid.UUID,
        user: User,
        max_turns: int = 10,
        is_public: bool = True,
    ) -> CharacterChatSession:
        """캐릭터 간 1:1 채팅 요청."""
        # 요청자 캐릭터 소유 확인
        requester_persona = await self._verify_ownership(requester_persona_id, user)

        # 응답자 캐릭터 조회
        responder_persona = await self._get_persona(responder_persona_id)
        if responder_persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Responder persona not found")

        # 같은 캐릭터끼리 대화 불가
        if requester_persona_id == responder_persona_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot chat with yourself")

        # 연령등급: 양쪽 중 높은 등급 채택
        age_rating = self._resolve_age_rating(requester_persona, responder_persona)
        if age_rating == "18+":
            if user.adult_verified_at is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Adult verification required for 18+ character chat",
                    headers={"X-Error-Code": "AUTH_ADULT_REQUIRED"},
                )

        # 응답자 설정 확인
        responder_config = await self._get_lounge_config(responder_persona_id)
        if responder_config and not responder_config.accept_chat_requests:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This character is not accepting chat requests",
            )

        # 동시 세션 수 제한
        active_count = (
            await self.db.execute(
                select(func.count())
                .select_from(CharacterChatSession)
                .where(
                    CharacterChatSession.requester_owner_id == user.id,
                    CharacterChatSession.status.in_(["pending", "active"]),
                )
            )
        ).scalar()
        if active_count >= MAX_CONCURRENT_SESSIONS_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Max {MAX_CONCURRENT_SESSIONS_PER_USER} concurrent sessions",
            )

        # 응답자 소유자 조회
        if responder_persona.created_by is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Responder has no owner")

        # 세션 생성
        initial_status = "pending"
        started_at = None

        # auto_accept면 바로 active
        if responder_config and responder_config.auto_accept_chats:
            initial_status = "active"
            started_at = datetime.now(UTC)

        session = CharacterChatSession(
            requester_persona_id=requester_persona_id,
            responder_persona_id=responder_persona_id,
            requester_owner_id=user.id,
            responder_owner_id=responder_persona.created_by,
            status=initial_status,
            max_turns=max_turns,
            is_public=is_public,
            age_rating=age_rating,
            started_at=started_at,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        # 알림 (pending일 때만)
        if initial_status == "pending":
            notif_svc = NotificationService(self.db)
            await notif_svc.create(
                user_id=responder_persona.created_by,
                type_="chat_request",
                title="캐릭터 대화 요청",
                body=f"{requester_persona.display_name}이(가) {responder_persona.display_name}에게 대화를 요청했습니다.",
                link=f"/character-chats/{session.id}",
            )

        return session

    async def respond_to_request(
        self, session_id: uuid.UUID, user: User, accept: bool
    ) -> CharacterChatSession:
        """대화 요청 수락/거절."""
        session = await self._get_session(session_id)

        if session.responder_owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the responder owner")
        if session.status != "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not pending")

        if accept:
            session.status = "active"
            session.started_at = datetime.now(UTC)

            # 알림
            notif_svc = NotificationService(self.db)
            requester_persona = await self._get_persona(session.requester_persona_id)
            responder_persona = await self._get_persona(session.responder_persona_id)
            await notif_svc.create(
                user_id=session.requester_owner_id,
                type_="chat_accepted",
                title="대화 요청 수락",
                body=f"{responder_persona.display_name}이(가) 대화 요청을 수락했습니다.",
                link=f"/character-chats/{session.id}",
            )
        else:
            session.status = "rejected"

        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def advance_chat(self, session_id: uuid.UUID, user: User) -> CharacterChatMessage:
        """다음 턴 생성 (LLM 호출)."""
        session = await self._get_session(session_id)

        # 소유자 중 한 명이어야 함
        if user.id not in (session.requester_owner_id, session.responder_owner_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a session participant")
        if session.status != "active":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not active")
        if session.current_turn >= session.max_turns:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Max turns reached")

        # 연령등급 체크 (18+ 채팅은 양쪽 소유자 모두 adult_verified)
        if session.age_rating == "18+":
            await self._verify_both_owners_adult(session)

        # 다음 발화자 결정: 짝수 턴 = requester, 홀수 턴 = responder
        if session.current_turn % 2 == 0:
            speaking_persona_id = session.requester_persona_id
            other_persona_id = session.responder_persona_id
            speaking_owner_id = session.requester_owner_id
        else:
            speaking_persona_id = session.responder_persona_id
            other_persona_id = session.requester_persona_id
            speaking_owner_id = session.responder_owner_id

        # 일일 채팅 한도 확인
        config = await self._get_lounge_config(speaking_persona_id)
        if config and config.chats_today >= config.daily_chat_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily chat limit reached for this character",
            )

        # 크레딧 체크 + 차감
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            await credit_svc.check_and_deduct(
                speaking_owner_id,
                "character_chat_turn",
                "economy",
                reference_id=str(session.id),
            )

        # LLM 모델
        llm_model = await self._get_economy_model()
        if llm_model is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No LLM model available")

        # 기존 메시지 로드
        msg_result = await self.db.execute(
            select(CharacterChatMessage)
            .where(CharacterChatMessage.session_id == session_id)
            .order_by(CharacterChatMessage.turn_number)
        )
        existing_messages = list(msg_result.scalars().all())

        # 프롬프트 빌드
        speaking_data = await self.loader.load(speaking_persona_id)
        other_data = await self.loader.load(other_persona_id)

        # 세계관 이벤트 주입
        world_svc = WorldEventService(self.db)
        world_events = await world_svc.get_active_events(session.age_rating)
        world_text = world_svc.format_for_prompt(world_events)

        messages = self._build_chat_prompt(
            speaking_data, other_data, existing_messages,
            speaking_persona_id, world_text,
        )

        # LLM 호출
        result = await self.inference.generate(llm_model, messages, max_tokens=200)

        # PII 마스킹
        pii = get_pii_detector()
        safe_content = pii.mask(result["content"])

        # 메시지 저장
        new_msg = CharacterChatMessage(
            session_id=session_id,
            persona_id=speaking_persona_id,
            content=safe_content,
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            turn_number=session.current_turn,
        )
        self.db.add(new_msg)

        # 세션 갱신
        input_tok = result.get("input_tokens", 0)
        output_tok = result.get("output_tokens", 0)
        cost = self._calc_cost(llm_model, result)

        new_turn = session.current_turn + 1
        values = {
            "current_turn": new_turn,
            "total_input_tokens": CharacterChatSession.total_input_tokens + input_tok,
            "total_output_tokens": CharacterChatSession.total_output_tokens + output_tok,
            "total_cost": CharacterChatSession.total_cost + cost,
        }
        if new_turn >= session.max_turns:
            values["status"] = "completed"
            values["completed_at"] = datetime.now(UTC)

        await self.db.execute(
            update(CharacterChatSession).where(CharacterChatSession.id == session_id).values(**values)
        )

        # 채팅 카운터 갱신
        if config:
            await self.db.execute(
                update(PersonaLoungeConfig)
                .where(PersonaLoungeConfig.id == config.id)
                .values(chats_today=PersonaLoungeConfig.chats_today + 1)
            )

        await self.db.commit()
        await self.db.refresh(new_msg)
        return new_msg

    async def get_session(self, session_id: uuid.UUID, user: User) -> dict:
        """대화 세션 + 메시지 조회."""
        session = await self._get_session(session_id)

        # 공개 세션이면 누구나, 비공개면 소유자만
        if not session.is_public:
            if user.id not in (session.requester_owner_id, session.responder_owner_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Private session")

        # 연령등급 게이트
        if session.age_rating == "18+" and user.adult_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Adult verification required",
                headers={"X-Error-Code": "AUTH_ADULT_REQUIRED"},
            )

        msg_result = await self.db.execute(
            select(CharacterChatMessage)
            .where(CharacterChatMessage.session_id == session_id)
            .order_by(CharacterChatMessage.turn_number)
        )
        messages = list(msg_result.scalars().all())

        # 페르소나 이름 조회
        req_persona = await self._get_persona(session.requester_persona_id)
        resp_persona = await self._get_persona(session.responder_persona_id)

        return {
            "session": session,
            "messages": messages,
            "requester_persona": req_persona,
            "responder_persona": resp_persona,
        }

    async def list_requests(
        self, user: User, direction: str = "incoming", skip: int = 0, limit: int = 20
    ) -> dict:
        """수신/발신 채팅 요청 목록."""
        if direction == "incoming":
            base = select(CharacterChatSession).where(CharacterChatSession.responder_owner_id == user.id)
            count_base = (
                select(func.count())
                .select_from(CharacterChatSession)
                .where(CharacterChatSession.responder_owner_id == user.id)
            )
        else:
            base = select(CharacterChatSession).where(CharacterChatSession.requester_owner_id == user.id)
            count_base = (
                select(func.count())
                .select_from(CharacterChatSession)
                .where(CharacterChatSession.requester_owner_id == user.id)
            )

        total = (await self.db.execute(count_base)).scalar()
        q = base.order_by(CharacterChatSession.requested_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(q)
        items = list(result.scalars().all())

        return {"items": items, "total": total}

    # ── 내부 헬퍼 ──

    def _build_chat_prompt(
        self,
        speaking_data: dict,
        other_data: dict,
        existing_messages: list[CharacterChatMessage],
        speaking_persona_id: uuid.UUID,
        world_text: str,
    ) -> list[dict]:
        """캐릭터 간 대화 프롬프트 구성."""
        messages = [
            {"role": "system", "content": PromptCompiler.POLICY_LAYER},
        ]

        # 세계관 이벤트 (Layer 1.5)
        if world_text:
            messages.append({"role": "system", "content": world_text})

        messages.append({"role": "system", "content": PromptCompiler._build_persona_block(speaking_data)})
        messages.append({
            "role": "system",
            "content": (
                f"{CHARACTER_CHAT_CONTEXT}\n"
                f"You are talking with: {other_data['display_name']}\n"
                f"Their personality: {other_data.get('system_prompt', '')[:200]}"
            ),
        })

        # 기존 대화를 user/assistant 형식으로 변환
        for msg in existing_messages:
            if msg.persona_id == speaking_persona_id:
                messages.append({"role": "assistant", "content": msg.content})
            else:
                messages.append({"role": "user", "content": msg.content})

        # 첫 턴이면 대화 시작 프롬프트
        if not existing_messages:
            messages.append({"role": "user", "content": f"(대화를 시작해주세요. {other_data['display_name']}에게 먼저 말을 걸어보세요.)"})

        return messages

    async def _verify_ownership(self, persona_id: uuid.UUID, user: User) -> Persona:
        result = await self.db.execute(
            select(Persona).where(Persona.id == persona_id, Persona.created_by == user.id)
        )
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your persona")
        return persona

    async def _get_persona(self, persona_id: uuid.UUID) -> Persona | None:
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        return result.scalar_one_or_none()

    async def _get_session(self, session_id: uuid.UUID) -> CharacterChatSession:
        result = await self.db.execute(
            select(CharacterChatSession).where(CharacterChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
        return session

    async def _get_lounge_config(self, persona_id: uuid.UUID) -> PersonaLoungeConfig | None:
        result = await self.db.execute(
            select(PersonaLoungeConfig).where(PersonaLoungeConfig.persona_id == persona_id)
        )
        return result.scalar_one_or_none()

    async def _get_economy_model(self) -> LLMModel | None:
        result = await self.db.execute(
            select(LLMModel).where(LLMModel.is_active == True, LLMModel.tier == "economy").limit(1)
        )
        model = result.scalar_one_or_none()
        if model:
            return model
        result = await self.db.execute(select(LLMModel).where(LLMModel.is_active == True).limit(1))
        return result.scalar_one_or_none()

    async def _verify_both_owners_adult(self, session: CharacterChatSession) -> None:
        for owner_id in (session.requester_owner_id, session.responder_owner_id):
            result = await self.db.execute(select(User).where(User.id == owner_id))
            owner = result.scalar_one_or_none()
            if owner is None or owner.adult_verified_at is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Both owners must be adult verified for 18+ chat",
                    headers={"X-Error-Code": "AUTH_ADULT_REQUIRED"},
                )

    @staticmethod
    def _resolve_age_rating(p1: Persona, p2: Persona) -> str:
        """양쪽 캐릭터 중 높은 연령등급 채택."""
        order = {"all": 0, "15+": 1, "18+": 2}
        r1 = order.get(p1.age_rating, 0)
        r2 = order.get(p2.age_rating, 0)
        reverse = {0: "all", 1: "15+", 2: "18+"}
        return reverse[max(r1, r2)]

    @staticmethod
    def _calc_cost(model: LLMModel, result: dict) -> Decimal:
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        input_cost = Decimal(str(input_tokens)) * Decimal(str(model.input_cost_per_1m)) / Decimal("1000000")
        output_cost = Decimal(str(output_tokens)) * Decimal(str(model.output_cost_per_1m)) / Decimal("1000000")
        return input_cost + output_cost
