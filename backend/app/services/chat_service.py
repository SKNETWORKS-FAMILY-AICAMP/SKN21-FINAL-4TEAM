import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.observability import create_trace, set_sentry_user
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from app.models.user import User
from app.pipeline.emotion import EmotionAnalyzer, get_emotion_analyzer
from app.pipeline.pii import PIIDetector, get_pii_detector
from app.prompt.compiler import PromptCompiler
from app.prompt.persona_loader import PersonaLoader
from app.services.inference_client import InferenceClient

logger = logging.getLogger(__name__)

# 최근 대화 히스토리 최대 메시지 수
MAX_HISTORY_MESSAGES = 20

# 자동 메모리 추출 간격 (N번째 메시지마다)
MEMORY_EXTRACTION_INTERVAL = 5


class ChatService:
    def __init__(
        self,
        db: AsyncSession,
        pii_detector: PIIDetector | None = None,
        emotion_analyzer: EmotionAnalyzer | None = None,
    ):
        self.db = db
        self.compiler = PromptCompiler()
        self.persona_loader = PersonaLoader(db)
        self.inference = InferenceClient()
        self._pii = pii_detector
        self._emotion = emotion_analyzer

    @property
    def pii(self) -> PIIDetector:
        if self._pii is None:
            self._pii = get_pii_detector()
        return self._pii

    @property
    def emotion(self) -> EmotionAnalyzer:
        if self._emotion is None:
            self._emotion = get_emotion_analyzer()
        return self._emotion

    async def create_session(
        self,
        user: User,
        persona_id: uuid.UUID,
        webtoon_id: uuid.UUID | None = None,
        llm_model_id: uuid.UUID | None = None,
        user_persona_id: uuid.UUID | None = None,
    ) -> ChatSession:
        """새 채팅 세션 생성. greeting_message가 있으면 첫 assistant 메시지로 삽입."""
        # 페르소나 존재 확인
        from app.models.persona import Persona

        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

        # 연령 게이트
        if persona.age_rating == "18+" and user.adult_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Adult verification required",
            )

        # 사용자 선호 모델 폴백
        if llm_model_id is None and user.preferred_llm_model_id:
            llm_model_id = user.preferred_llm_model_id

        # LLM 모델 확인 (지정하지 않으면 기본 모델)
        if llm_model_id:
            model_result = await self.db.execute(
                select(LLMModel).where(LLMModel.id == llm_model_id, LLMModel.is_active == True)
            )
            llm_model = model_result.scalar_one_or_none()
            if llm_model is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM model not found")
            # 성인전용 모델은 성인인증 사용자만 사용 가능
            if llm_model.is_adult_only and user.adult_verified_at is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Adult verification required for this model",
                )

        session = ChatSession(
            user_id=user.id,
            persona_id=persona_id,
            webtoon_id=webtoon_id,
            llm_model_id=llm_model_id,
            user_persona_id=user_persona_id,
            title=persona.display_name or persona.persona_key,
            status="active",
        )
        self.db.add(session)
        await self.db.flush()

        # 인사말(greeting) 삽입
        if persona.greeting_message:
            greeting = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=persona.greeting_message,
            )
            self.db.add(greeting)

        # chat_count 증가
        persona.chat_count = persona.chat_count + 1

        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_user_sessions(self, user: User, skip: int = 0, limit: int = 20) -> dict:
        """사용자의 채팅 세션 목록 (페르소나 정보 포함)."""
        from app.models.persona import Persona

        count_query = (
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.user_id == user.id, ChatSession.status != "deleted")
        )
        total = (await self.db.execute(count_query)).scalar()

        query = (
            select(
                ChatSession,
                Persona.display_name.label("persona_display_name"),
                Persona.background_image_url.label("persona_background_image_url"),
                Persona.age_rating.label("persona_age_rating"),
                Persona.category.label("persona_category"),
            )
            .outerjoin(Persona, ChatSession.persona_id == Persona.id)
            .where(ChatSession.user_id == user.id, ChatSession.status != "deleted")
            .order_by(ChatSession.last_active_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        rows = result.all()

        items = []
        for session, p_name, p_bg, p_rating, p_category in rows:
            session.persona_display_name = p_name
            session.persona_background_image_url = p_bg
            session.persona_age_rating = p_rating
            session.persona_category = p_category
            items.append(session)

        return {"items": items, "total": total}

    async def get_session_messages(self, session_id: uuid.UUID, user: User, skip: int = 0, limit: int = 50) -> dict:
        """세션 메시지 히스토리 조회."""
        session = await self._get_session_or_404(session_id, user)

        count_query = select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session.id)
        total = (await self.db.execute(count_query)).scalar()

        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        items = result.scalars().all()
        return {"items": list(items), "total": total}

    async def send_message(self, session_id: uuid.UUID, user: User, content: str) -> ChatMessage:
        """메시지 처리 → PII 마스킹 → LLM 호출 → 감정 분석 → 응답 저장 (비스트리밍)."""
        # Langfuse 트레이스 시작
        create_trace(
            name="chat_message",
            user_id=str(user.id),
            session_id=str(session_id),
            metadata={"content_length": len(content)},
        )
        set_sentry_user(str(user.id), user.role)

        session = await self._get_session_or_404(session_id, user)
        llm_model = await self._resolve_llm_model(session)

        # 0. PII 마스킹 (사용자 입력에서 개인정보 제거)
        safe_content = self.pii.mask(content)

        # 0.5. 크레딧 사전 확인 (실제 차감은 LLM 응답 후 토큰 기반)
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            await credit_svc.grant_daily_credits(user.id)
            if not await credit_svc.check_has_credits(user.id):
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="대화석이 부족합니다",
                    headers={"X-Error-Code": "CREDITS_INSUFFICIENT"},
                )
        elif settings.quota_enabled:
            from app.services.quota_service import QuotaService

            quota_svc = QuotaService(self.db)
            quota_status = await quota_svc.check_quota(user.id)
            if not quota_status["allowed"]:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Usage quota exceeded",
                    headers={"X-Error-Code": "USAGE_QUOTA_EXCEEDED"},
                )

        # 1. 사용자 메시지 저장 (마스킹된 텍스트)
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=safe_content,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 2. 프롬프트 빌드
        prompt_messages = await self._build_prompt(session, safe_content)

        # 3. LLM 호출
        result = await self.inference.generate(llm_model, prompt_messages)

        # 4. 응답 감정 분석
        emotion_signal = None
        try:
            emotion_signal = self.emotion.get_dominant_emotion(result["content"])
        except Exception:
            logger.warning("Emotion analysis failed, skipping", exc_info=True)

        # 5. 어시스턴트 메시지 저장
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=result["content"],
            token_count=output_tokens,
            emotion_signal=emotion_signal,
        )
        self.db.add(assistant_msg)

        # 5-1. 토큰 사용량 로깅
        await self._log_usage(
            user=user,
            session=session,
            llm_model=llm_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # 5-2. 토큰 기반 크레딧 차감 (LLM 응답 후)
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            await credit_svc.deduct_by_tokens(
                user_id=user.id,
                total_tokens=input_tokens + output_tokens,
                credit_per_1k_tokens=llm_model.credit_per_1k_tokens,
                reference_id=str(session.id),
            )

        # 6. 호감도 갱신
        await self._update_relationship(user, session.persona_id, emotion_signal)

        # 7. 자동 메모리 추출
        await self._maybe_extract_memories(session, user)

        # 8. 세션 활성 시간 갱신
        session.last_active_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(assistant_msg)
        return assistant_msg

    async def send_message_stream(self, session_id: uuid.UUID, user: User, content: str) -> AsyncGenerator[str, None]:
        """메시지 처리 → PII 마스킹 → LLM SSE 스트리밍 → 감정 분석 → 응답 저장."""
        session = await self._get_session_or_404(session_id, user)
        llm_model = await self._resolve_llm_model(session)

        # 0. PII 마스킹
        safe_content = self.pii.mask(content)

        # 0.5. 크레딧 사전 확인 (실제 차감은 스트리밍 완료 후 토큰 기반)
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            logger.info("[stream] granting daily credits for user %s", user.id)
            await credit_svc.grant_daily_credits(user.id)
            logger.info("[stream] checking credits for user %s", user.id)
            has_credits = await credit_svc.check_has_credits(user.id)
            logger.info("[stream] has_credits=%s for user %s", has_credits, user.id)
            if not has_credits:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="대화석이 부족합니다",
                    headers={"X-Error-Code": "CREDITS_INSUFFICIENT"},
                )
        elif settings.quota_enabled:
            from app.services.quota_service import QuotaService

            quota_svc = QuotaService(self.db)
            quota_status = await quota_svc.check_quota(user.id)
            if not quota_status["allowed"]:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Usage quota exceeded",
                    headers={"X-Error-Code": "USAGE_QUOTA_EXCEEDED"},
                )

        # 1. 사용자 메시지 저장 (마스킹된 텍스트)
        logger.info("[stream] saving user message for session %s", session_id)
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=safe_content,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 2. 프롬프트 빌드
        logger.info("[stream] building prompt for session %s", session_id)
        prompt_messages = await self._build_prompt(session, safe_content)

        # 3. SSE 스트리밍 (usage_out으로 토큰 수 캡처)
        logger.info("[stream] starting LLM stream for session %s, model=%s", session_id, llm_model.model_id)
        full_response = []
        usage_out: dict = {}
        async for chunk in self.inference.generate_stream(llm_model, prompt_messages, usage_out=usage_out):
            full_response.append(chunk)
            yield chunk

        # 4. 응답 감정 분석
        response_text = "".join(full_response)
        emotion_signal = None
        try:
            emotion_signal = self.emotion.get_dominant_emotion(response_text)
        except Exception:
            logger.warning("Emotion analysis failed, skipping", exc_info=True)

        # 5. 어시스턴트 메시지 저장
        input_tokens = usage_out.get("input_tokens", 0)
        output_tokens = usage_out.get("output_tokens", 0)

        # API에서 토큰 수를 제공하지 않은 경우 텍스트 길이로 추정
        if output_tokens == 0 and response_text:
            output_tokens = max(len(response_text) // 3, 1)

        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=response_text,
            token_count=output_tokens,
            emotion_signal=emotion_signal,
        )
        self.db.add(assistant_msg)

        # 6. 토큰 사용량 로깅
        await self._log_usage(
            user=user,
            session=session,
            llm_model=llm_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # 6-1. 토큰 기반 크레딧 차감 (스트리밍 완료 후)
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            await credit_svc.deduct_by_tokens(
                user_id=user.id,
                total_tokens=input_tokens + output_tokens,
                credit_per_1k_tokens=llm_model.credit_per_1k_tokens,
                reference_id=str(session.id),
            )

        # 7. 호감도 갱신
        await self._update_relationship(user, session.persona_id, emotion_signal)

        # 8. 자동 메모리 추출
        await self._maybe_extract_memories(session, user)

        # 9. 세션 활성 시간 갱신
        session.last_active_at = datetime.now(UTC)
        await self.db.commit()

    async def regenerate_message(self, session_id: uuid.UUID, message_id: int, user: User) -> AsyncGenerator[str, None]:
        """기존 assistant 메시지를 비활성화하고 새로 생성 (SSE 스트리밍)."""
        session = await self._get_session_or_404(session_id, user)
        llm_model = await self._resolve_llm_model(session)

        # 대상 메시지 조회
        msg_result = await self.db.execute(
            select(ChatMessage).where(
                ChatMessage.id == message_id,
                ChatMessage.session_id == session.id,
                ChatMessage.role == "assistant",
            )
        )
        target_msg = msg_result.scalar_one_or_none()
        if target_msg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

        # 이전 user 메시지 찾기 (parent_id 기반 또는 시간순)
        user_msg_result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session.id,
                ChatMessage.role == "user",
                ChatMessage.is_active == True,
                ChatMessage.created_at < target_msg.created_at,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        user_msg = user_msg_result.scalar_one_or_none()
        if user_msg is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user message found to regenerate from",
            )

        # 기존 메시지 비활성화
        target_msg.is_active = False

        # 프롬프트 빌드 (이전 user 메시지 content 재사용)
        prompt_messages = await self._build_prompt(session, user_msg.content)

        # SSE 스트리밍 (usage_out으로 토큰 수 캡처)
        full_response = []
        usage_out: dict = {}
        try:
            async for chunk in self.inference.generate_stream(llm_model, prompt_messages, usage_out=usage_out):
                full_response.append(chunk)
                yield chunk
        except Exception as e:
            logger.error("Message regeneration failed: %s", e)
            yield f"\n\n[오류] 메시지 재생성에 실패했습니다: {str(e)}"
            return

        # 감정 분석
        response_text = "".join(full_response)
        emotion_signal = None
        try:
            emotion_signal = self.emotion.get_dominant_emotion(response_text)
        except Exception:
            logger.warning("Emotion analysis failed, skipping", exc_info=True)

        # 토큰 수 추출
        input_tokens = usage_out.get("input_tokens", 0)
        output_tokens = usage_out.get("output_tokens", 0)
        if output_tokens == 0 and response_text:
            output_tokens = max(len(response_text) // 3, 1)

        # 새 assistant 메시지 저장 (같은 parent_id)
        new_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=response_text,
            parent_id=target_msg.parent_id,
            token_count=output_tokens,
            emotion_signal=emotion_signal,
            is_active=True,
        )
        self.db.add(new_msg)

        # 토큰 사용량 로깅
        await self._log_usage(
            user=user,
            session=session,
            llm_model=llm_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # 토큰 기반 크레딧 차감
        if settings.credit_system_enabled:
            from app.services.credit_service import CreditService

            credit_svc = CreditService(self.db)
            await credit_svc.deduct_by_tokens(
                user_id=user.id,
                total_tokens=input_tokens + output_tokens,
                credit_per_1k_tokens=llm_model.credit_per_1k_tokens,
                reference_id=str(session.id),
            )

        # 호감도 갱신
        await self._update_relationship(user, session.persona_id, emotion_signal)

        session.last_active_at = datetime.now(UTC)
        await self.db.commit()

    async def edit_message(self, session_id: uuid.UUID, message_id: int, user: User, new_content: str) -> ChatMessage:
        """사용자 메시지 수정. 이후 assistant 응답 비활성화."""
        session = await self._get_session_or_404(session_id, user)

        msg_result = await self.db.execute(
            select(ChatMessage).where(
                ChatMessage.id == message_id,
                ChatMessage.session_id == session.id,
                ChatMessage.role == "user",
            )
        )
        msg = msg_result.scalar_one_or_none()
        if msg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

        # PII 마스킹
        safe_content = self.pii.mask(new_content)
        msg.content = safe_content
        msg.is_edited = True
        msg.edited_at = datetime.now(UTC)

        # 이후 assistant 응답 비활성화
        subsequent = await self.db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == session.id,
                ChatMessage.role == "assistant",
                ChatMessage.is_active == True,
                ChatMessage.created_at > msg.created_at,
            )
        )
        for m in subsequent.scalars().all():
            m.is_active = False

        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def get_siblings(self, session_id: uuid.UUID, message_id: int, user: User) -> dict:
        """같은 parent_id를 가진 형제 메시지 목록 반환."""
        session = await self._get_session_or_404(session_id, user)

        msg_result = await self.db.execute(
            select(ChatMessage).where(
                ChatMessage.id == message_id,
                ChatMessage.session_id == session.id,
            )
        )
        msg = msg_result.scalar_one_or_none()
        if msg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

        siblings_result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session.id,
                ChatMessage.parent_id == msg.parent_id,
                ChatMessage.role == msg.role,
            )
            .order_by(ChatMessage.created_at.asc())
        )
        siblings = list(siblings_result.scalars().all())

        current_index = 0
        for i, s in enumerate(siblings):
            if s.id == message_id:
                current_index = i
                break

        return {
            "messages": siblings,
            "current_index": current_index,
            "total": len(siblings),
        }

    async def switch_sibling(self, session_id: uuid.UUID, message_id: int, user: User) -> ChatMessage:
        """특정 형제 메시지를 활성화하고 기존 활성 형제를 비활성화."""
        session = await self._get_session_or_404(session_id, user)

        msg_result = await self.db.execute(
            select(ChatMessage).where(
                ChatMessage.id == message_id,
                ChatMessage.session_id == session.id,
            )
        )
        msg = msg_result.scalar_one_or_none()
        if msg is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

        # 같은 부모의 다른 형제 비활성화
        siblings_result = await self.db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == session.id,
                ChatMessage.parent_id == msg.parent_id,
                ChatMessage.role == msg.role,
                ChatMessage.is_active == True,
            )
        )
        for s in siblings_result.scalars().all():
            s.is_active = False

        msg.is_active = True
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def update_session(
        self,
        session_id: uuid.UUID,
        user: User,
        title: str | None = None,
        is_pinned: bool | None = None,
        llm_model_id: uuid.UUID | None = None,
    ) -> ChatSession:
        """세션 제목/핀/모델 수정."""
        session = await self._get_session_or_404(session_id, user)
        if title is not None:
            session.title = title
        if is_pinned is not None:
            session.is_pinned = is_pinned
        if llm_model_id is not None:
            model_result = await self.db.execute(
                select(LLMModel).where(LLMModel.id == llm_model_id, LLMModel.is_active == True)
            )
            llm_model = model_result.scalar_one_or_none()
            if llm_model is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM model not found or inactive")
            if llm_model.is_adult_only and user.adult_verified_at is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Adult verification required for this model",
                )
            session.llm_model_id = llm_model_id
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete_session(self, session_id: uuid.UUID, user: User) -> None:
        """세션 소프트 삭제."""
        session = await self._get_session_or_404(session_id, user)
        session.status = "deleted"
        await self.db.commit()

    async def archive_session(self, session_id: uuid.UUID, user: User) -> ChatSession:
        """세션 아카이브."""
        session = await self._get_session_or_404(session_id, user)
        session.status = "archived"
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def _update_relationship(self, user: User, persona_id: uuid.UUID, emotion_signal: dict | None) -> None:
        """호감도 갱신 + 단계 변경 시 알림 생성.

        SAVEPOINT를 사용해 실패 시 메인 트랜잭션을 오염시키지 않음.
        """
        try:
            from app.services.notification_service import NotificationService
            from app.services.relationship_service import RelationshipService

            async with self.db.begin_nested():  # SAVEPOINT — 실패해도 외부 트랜잭션 보호
                rel_svc = RelationshipService(self.db)
                rel, stage_changed = await rel_svc.update_after_interaction(user.id, persona_id, emotion_signal)
                if stage_changed:
                    stage_labels = {
                        "stranger": "낯선 사이",
                        "acquaintance": "아는 사이",
                        "friend": "친구",
                        "close_friend": "절친",
                        "crush": "썸",
                        "lover": "연인",
                        "soulmate": "소울메이트",
                    }
                    label = stage_labels.get(rel.relationship_stage, rel.relationship_stage)
                    notif_svc = NotificationService(self.db)
                    await notif_svc.create(
                        user_id=user.id,
                        type_="relationship",
                        title=f"관계가 '{label}'(으)로 발전했어요!",
                        body=f"호감도: {rel.affection_level}/1000",
                        link="/relationships",
                    )
        except Exception:
            logger.warning("Relationship update failed, skipping", exc_info=True)

    # ── 헬퍼 ──

    async def _get_session_or_404(self, session_id: uuid.UUID, user: User) -> ChatSession:
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user.id,
                ChatSession.status != "deleted",
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        # 성인인증 철회 후에도 18+ 세션 접근 차단
        await self._check_session_age_gate(session, user)
        return session

    async def _check_session_age_gate(self, session: ChatSession, user: User) -> None:
        """세션의 페르소나 연령등급 vs 사용자 인증 상태 재검증."""
        from app.models.persona import Persona

        result = await self.db.execute(select(Persona.age_rating).where(Persona.id == session.persona_id))
        age_rating = result.scalar_one_or_none()
        if age_rating == "18+" and user.adult_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Adult verification required",
                headers={"X-Error-Code": "AUTH_ADULT_REQUIRED"},
            )

    async def _resolve_llm_model(self, session: ChatSession) -> LLMModel:
        """세션 또는 기본 LLM 모델 해석."""
        if session.llm_model_id:
            result = await self.db.execute(select(LLMModel).where(LLMModel.id == session.llm_model_id))
            model = result.scalar_one_or_none()
            if model:
                return model

        # 기본 모델: 활성 상태인 첫 번째 모델
        result = await self.db.execute(select(LLMModel).where(LLMModel.is_active == True).limit(1))
        model = result.scalar_one_or_none()
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No LLM model available",
            )
        return model

    async def _build_prompt(self, session: ChatSession, new_message: str) -> list[dict]:
        """프롬프트 컴파일. 사용자 페르소나, 관계, 기억 통합."""
        # 페르소나 로드
        persona_data = await self.persona_loader.load(session.persona_id)

        # 사용자 페르소나 로드
        user_persona = None
        if session.user_persona_id:
            user_persona = await self._load_user_persona(session.user_persona_id)

        # 관계 상태 로드
        relationship = await self._load_relationship(session.user_id, session.persona_id)

        # 사용자 기억 로드
        user_memories = await self._load_user_memories(session.user_id)

        # 최근 메시지 로드 (활성 경로만)
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id, ChatMessage.is_active == True)
            .order_by(ChatMessage.created_at.desc())
            .limit(MAX_HISTORY_MESSAGES)
        )
        history = result.scalars().all()
        recent_messages = [{"role": msg.role, "content": msg.content} for msg in reversed(history)]

        # 컴파일
        return self.compiler.compile(
            persona=persona_data,
            lorebook_entries=persona_data.get("lorebook", []),
            session_summary=session.summary_text,
            recent_messages=recent_messages,
            user_persona=user_persona,
            relationship=relationship,
            user_memories=user_memories,
        )

    async def _load_user_persona(self, user_persona_id: uuid.UUID) -> dict | None:
        from app.models.user_persona import UserPersona

        result = await self.db.execute(select(UserPersona).where(UserPersona.id == user_persona_id))
        up = result.scalar_one_or_none()
        if up is None:
            return None
        return {"display_name": up.display_name, "description": up.description}

    async def _load_relationship(self, user_id: uuid.UUID, persona_id: uuid.UUID) -> dict | None:
        from app.models.persona_relationship import PersonaRelationship

        result = await self.db.execute(
            select(PersonaRelationship).where(
                PersonaRelationship.user_id == user_id,
                PersonaRelationship.persona_id == persona_id,
            )
        )
        rel = result.scalar_one_or_none()
        if rel is None:
            return None
        return {"stage": rel.relationship_stage, "level": rel.affection_level}

    async def _load_user_memories(self, user_id: uuid.UUID) -> list[dict]:
        from app.models.user_memory import UserMemory

        result = await self.db.execute(
            select(UserMemory).where(UserMemory.user_id == user_id).order_by(UserMemory.created_at.desc()).limit(10)
        )
        memories = result.scalars().all()
        return [{"key": m.key, "value": m.value if isinstance(m.value, str) else str(m.value)} for m in memories]

    async def _log_usage(
        self,
        user: User,
        session: ChatSession,
        llm_model: LLMModel,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """토큰 사용량 기록."""
        input_cost = Decimal(str(input_tokens)) * Decimal(str(llm_model.input_cost_per_1m)) / Decimal("1000000")
        output_cost = Decimal(str(output_tokens)) * Decimal(str(llm_model.output_cost_per_1m)) / Decimal("1000000")
        total_cost = input_cost + output_cost

        log = TokenUsageLog(
            user_id=user.id,
            session_id=session.id,
            llm_model_id=llm_model.id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=total_cost,
        )
        self.db.add(log)

    async def _maybe_extract_memories(self, session: ChatSession, user: User) -> None:
        """N번째 메시지마다 대화에서 주요 사실을 추출하여 메모리에 저장."""
        try:
            # 현재 세션 메시지 수 확인
            count_result = await self.db.execute(
                select(func.count())
                .select_from(ChatMessage)
                .where(
                    ChatMessage.session_id == session.id,
                    ChatMessage.role == "user",
                    ChatMessage.is_active == True,
                )
            )
            msg_count = count_result.scalar() or 0
            if msg_count == 0 or msg_count % MEMORY_EXTRACTION_INTERVAL != 0:
                return

            # 최근 메시지 로드
            result = await self.db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id, ChatMessage.is_active == True)
                .order_by(ChatMessage.created_at.desc())
                .limit(MEMORY_EXTRACTION_INTERVAL * 2)
            )
            messages = result.scalars().all()
            if not messages:
                return

            conversation = "\n".join(
                f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}" for m in reversed(messages)
            )

            # LLM에 메모리 추출 요청
            extraction_prompt = [
                {
                    "role": "system",
                    "content": (
                        "You are a memory extraction assistant. "
                        "From the conversation below, extract up to 3 key facts about the user "
                        "that should be remembered for future conversations. "
                        "Return ONLY a JSON array of objects with 'key' and 'value' fields. "
                        "Keys should be short labels (e.g., 'favorite_food', 'hobby', 'name'). "
                        "Values should be concise strings. "
                        "If no memorable facts, return an empty array []."
                    ),
                },
                {"role": "user", "content": conversation},
            ]

            llm_model = await self._resolve_llm_model(session)
            result = await self.inference.generate(llm_model, extraction_prompt)
            response_text = result.get("content", "").strip()

            # JSON 파싱
            import json

            # ```json ... ``` 래핑 제거
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

            facts = json.loads(response_text)
            if not isinstance(facts, list):
                return

            # 메모리 저장 (upsert)
            from app.models.user_memory import UserMemory

            namespace = f"persona:{session.persona_id}"
            for fact in facts[:3]:
                key = str(fact.get("key", ""))[:100]
                value = str(fact.get("value", ""))
                if not key or not value:
                    continue

                existing = await self.db.execute(
                    select(UserMemory).where(
                        UserMemory.user_id == user.id,
                        UserMemory.namespace == namespace,
                        UserMemory.key == key,
                    )
                )
                mem = existing.scalar_one_or_none()
                if mem:
                    mem.value = value
                    mem.updated_at = datetime.now(UTC)
                else:
                    self.db.add(
                        UserMemory(
                            user_id=user.id,
                            memory_type="auto",
                            namespace=namespace,
                            key=key,
                            value=value,
                        )
                    )
        except Exception:
            logger.warning("Auto memory extraction failed, skipping", exc_info=True)
