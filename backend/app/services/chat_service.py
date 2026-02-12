import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.llm_model import LLMModel
from app.models.token_usage_log import TokenUsageLog
from app.models.user import User
from app.prompt.compiler import PromptCompiler
from app.prompt.persona_loader import PersonaLoader
from app.services.inference_client import InferenceClient

# 최근 대화 히스토리 최대 메시지 수
MAX_HISTORY_MESSAGES = 20


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.compiler = PromptCompiler()
        self.persona_loader = PersonaLoader(db)
        self.inference = InferenceClient()

    async def create_session(
        self,
        user: User,
        persona_id: uuid.UUID,
        webtoon_id: uuid.UUID | None = None,
        llm_model_id: uuid.UUID | None = None,
    ) -> ChatSession:
        """새 채팅 세션 생성."""
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

        # LLM 모델 확인 (지정하지 않으면 기본 모델)
        if llm_model_id:
            model_result = await self.db.execute(
                select(LLMModel).where(LLMModel.id == llm_model_id, LLMModel.is_active == True)
            )
            if model_result.scalar_one_or_none() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM model not found")

        session = ChatSession(
            user_id=user.id,
            persona_id=persona_id,
            webtoon_id=webtoon_id,
            llm_model_id=llm_model_id,
            status="active",
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_user_sessions(self, user: User, skip: int = 0, limit: int = 20) -> dict:
        """사용자의 채팅 세션 목록."""
        count_query = (
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.user_id == user.id)
        )
        total = (await self.db.execute(count_query)).scalar()

        query = (
            select(ChatSession)
            .where(ChatSession.user_id == user.id)
            .order_by(ChatSession.last_active_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        items = result.scalars().all()
        return {"items": list(items), "total": total}

    async def get_session_messages(
        self, session_id: uuid.UUID, user: User, skip: int = 0, limit: int = 50
    ) -> dict:
        """세션 메시지 히스토리 조회."""
        session = await self._get_session_or_404(session_id, user)

        count_query = (
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == session.id)
        )
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

    async def send_message(
        self, session_id: uuid.UUID, user: User, content: str
    ) -> ChatMessage:
        """메시지 처리 → LLM 호출 → 응답 저장 (비스트리밍)."""
        session = await self._get_session_or_404(session_id, user)
        llm_model = await self._resolve_llm_model(session)

        # 1. 사용자 메시지 저장
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=content,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 2. 프롬프트 빌드
        prompt_messages = await self._build_prompt(session, content)

        # 3. LLM 호출
        result = await self.inference.generate(llm_model, prompt_messages)

        # 4. 어시스턴트 메시지 저장
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=result["content"],
            token_count=result.get("output_tokens"),
        )
        self.db.add(assistant_msg)

        # 5. 토큰 사용량 로깅
        await self._log_usage(
            user=user,
            session=session,
            llm_model=llm_model,
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
        )

        # 6. 세션 활성 시간 갱신
        session.last_active_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(assistant_msg)
        return assistant_msg

    async def send_message_stream(
        self, session_id: uuid.UUID, user: User, content: str
    ) -> AsyncGenerator[str, None]:
        """메시지 처리 → LLM SSE 스트리밍 → 응답 저장."""
        session = await self._get_session_or_404(session_id, user)
        llm_model = await self._resolve_llm_model(session)

        # 1. 사용자 메시지 저장
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=content,
        )
        self.db.add(user_msg)
        await self.db.flush()

        # 2. 프롬프트 빌드
        prompt_messages = await self._build_prompt(session, content)

        # 3. SSE 스트리밍
        full_response = []
        async for chunk in self.inference.generate_stream(llm_model, prompt_messages):
            full_response.append(chunk)
            yield chunk

        # 4. 어시스턴트 메시지 저장
        response_text = "".join(full_response)
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=response_text,
        )
        self.db.add(assistant_msg)

        # 5. 세션 활성 시간 갱신
        session.last_active_at = datetime.now(timezone.utc)
        await self.db.commit()

    # ── 헬퍼 ──

    async def _get_session_or_404(self, session_id: uuid.UUID, user: User) -> ChatSession:
        result = await self.db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user.id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return session

    async def _resolve_llm_model(self, session: ChatSession) -> LLMModel:
        """세션 또는 기본 LLM 모델 해석."""
        if session.llm_model_id:
            result = await self.db.execute(
                select(LLMModel).where(LLMModel.id == session.llm_model_id)
            )
            model = result.scalar_one_or_none()
            if model:
                return model

        # 기본 모델: 활성 상태인 첫 번째 모델
        result = await self.db.execute(
            select(LLMModel).where(LLMModel.is_active == True).limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No LLM model available",
            )
        return model

    async def _build_prompt(self, session: ChatSession, new_message: str) -> list[dict]:
        """프롬프트 컴파일."""
        # 페르소나 로드
        persona_data = await self.persona_loader.load(session.persona_id)

        # 최근 메시지 로드
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(MAX_HISTORY_MESSAGES)
        )
        history = result.scalars().all()
        recent_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(history)
        ]

        # 컴파일
        return self.compiler.compile(
            persona=persona_data,
            lorebook_entries=persona_data.get("lorebook", []),
            session_summary=session.summary_text,
            recent_messages=recent_messages,
        )

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
