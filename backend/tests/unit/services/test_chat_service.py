"""ChatService 단위 테스트. DB/LLM/파이프라인 의존성을 mock."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_service import ChatService


def _make_user(role="user", adult_verified=False):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.role = role
    user.adult_verified_at = datetime.now(timezone.utc) if adult_verified else None
    return user


def _make_session(persona_id=None, llm_model_id=None):
    session = MagicMock()
    session.id = uuid.uuid4()
    session.persona_id = persona_id or uuid.uuid4()
    session.llm_model_id = llm_model_id or uuid.uuid4()
    session.last_active_at = datetime.now(timezone.utc)
    session.summary_text = None
    return session


def _make_llm_model():
    model = MagicMock()
    model.id = uuid.uuid4()
    model.provider = "openai"
    model.model_id = "gpt-4o"
    model.input_cost_per_1m = 5.0
    model.output_cost_per_1m = 15.0
    model.is_active = True
    return model


def _make_pii_detector():
    pii = MagicMock()
    pii.mask.side_effect = lambda text: text.replace("010-1234-5678", "<전화번호>")
    return pii


def _make_emotion_analyzer():
    emotion = MagicMock()
    emotion.get_dominant_emotion.return_value = {"label": "행복", "intensity": 0.9, "confidence": 0.9}
    return emotion


@patch("app.services.chat_service.settings")
class TestChatServicePIIMasking:
    @pytest.mark.asyncio
    async def test_send_message_masks_pii_in_user_input(self, mock_settings):
        mock_settings.quota_enabled = False
        mock_settings.credit_system_enabled = False
        db = AsyncMock()
        pii = _make_pii_detector()
        emotion = _make_emotion_analyzer()
        service = ChatService(db=db, pii_detector=pii, emotion_analyzer=emotion)

        session = _make_session()
        llm_model = _make_llm_model()

        # mock 헬퍼
        service._get_session_or_404 = AsyncMock(return_value=session)
        service._resolve_llm_model = AsyncMock(return_value=llm_model)
        service._build_prompt = AsyncMock(return_value=[{"role": "user", "content": "hi"}])
        service.inference.generate = AsyncMock(return_value={
            "content": "답변입니다",
            "input_tokens": 50,
            "output_tokens": 30,
        })
        service._log_usage = AsyncMock()

        # ChatMessage 저장 mock
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await service.send_message(session.id, _make_user(), "제 번호는 010-1234-5678입니다")

        # PII 마스킹이 호출되었는지 확인
        pii.mask.assert_called_once()
        call_arg = pii.mask.call_args[0][0]
        assert "010-1234-5678" in call_arg

    @pytest.mark.asyncio
    async def test_send_message_saves_masked_content(self, mock_settings):
        mock_settings.quota_enabled = False
        mock_settings.credit_system_enabled = False
        db = AsyncMock()
        pii = _make_pii_detector()
        emotion = _make_emotion_analyzer()
        service = ChatService(db=db, pii_detector=pii, emotion_analyzer=emotion)

        session = _make_session()
        service._get_session_or_404 = AsyncMock(return_value=session)
        service._resolve_llm_model = AsyncMock(return_value=_make_llm_model())
        service._build_prompt = AsyncMock(return_value=[])
        service.inference.generate = AsyncMock(return_value={
            "content": "응답", "input_tokens": 10, "output_tokens": 5,
        })
        service._log_usage = AsyncMock()

        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await service.send_message(session.id, _make_user(), "전화 010-1234-5678")

        # db.add 첫 호출이 user message → 마스킹된 content 확인
        user_msg = db.add.call_args_list[0][0][0]
        assert "010-1234-5678" not in user_msg.content
        assert "<전화번호>" in user_msg.content


@patch("app.services.chat_service.settings")
class TestChatServiceEmotionAnalysis:
    @pytest.mark.asyncio
    async def test_send_message_attaches_emotion_signal(self, mock_settings):
        mock_settings.quota_enabled = False
        mock_settings.credit_system_enabled = False
        db = AsyncMock()
        pii = MagicMock()
        pii.mask.side_effect = lambda t: t
        emotion = _make_emotion_analyzer()
        service = ChatService(db=db, pii_detector=pii, emotion_analyzer=emotion)

        session = _make_session()
        service._get_session_or_404 = AsyncMock(return_value=session)
        service._resolve_llm_model = AsyncMock(return_value=_make_llm_model())
        service._build_prompt = AsyncMock(return_value=[])
        service.inference.generate = AsyncMock(return_value={
            "content": "기쁜 답변", "input_tokens": 10, "output_tokens": 5,
        })
        service._log_usage = AsyncMock()

        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await service.send_message(session.id, _make_user(), "안녕")

        # 감정 분석 호출 확인
        emotion.get_dominant_emotion.assert_called_once_with("기쁜 답변")

        # 어시스턴트 메시지에 emotion_signal 포함 확인
        assistant_msg = db.add.call_args_list[1][0][0]
        assert assistant_msg.emotion_signal == {"label": "행복", "intensity": 0.9, "confidence": 0.9}

    @pytest.mark.asyncio
    async def test_emotion_failure_does_not_break_message(self, mock_settings):
        """감정 분석 실패 시 메시지 저장은 계속 진행."""
        mock_settings.quota_enabled = False
        mock_settings.credit_system_enabled = False
        db = AsyncMock()
        pii = MagicMock()
        pii.mask.side_effect = lambda t: t
        emotion = MagicMock()
        emotion.get_dominant_emotion.side_effect = RuntimeError("model error")
        service = ChatService(db=db, pii_detector=pii, emotion_analyzer=emotion)

        session = _make_session()
        service._get_session_or_404 = AsyncMock(return_value=session)
        service._resolve_llm_model = AsyncMock(return_value=_make_llm_model())
        service._build_prompt = AsyncMock(return_value=[])
        service.inference.generate = AsyncMock(return_value={
            "content": "답변", "input_tokens": 10, "output_tokens": 5,
        })
        service._log_usage = AsyncMock()

        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        # 예외 없이 정상 완료
        await service.send_message(session.id, _make_user(), "테스트")

        # 메시지는 저장됨, emotion_signal은 None
        assistant_msg = db.add.call_args_list[1][0][0]
        assert assistant_msg.emotion_signal is None
