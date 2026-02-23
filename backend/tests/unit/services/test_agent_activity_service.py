"""AgentActivityService 단위 테스트."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agent_activity_service import AgentActivityService


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.nickname = "testuser"
    user.role = "user"
    return user


def _make_persona(user_id):
    persona = MagicMock()
    persona.id = uuid.uuid4()
    persona.created_by = user_id
    persona.display_name = "테스트 캐릭터"
    persona.persona_key = "test-char"
    persona.system_prompt = "You are a test character."
    persona.style_rules = {}
    persona.safety_rules = {}
    persona.catchphrases = []
    persona.age_rating = "all"
    return persona


def _make_config(persona_id, active=True, level="normal", daily_limit=5, actions_today=0):
    config = MagicMock()
    config.id = uuid.uuid4()
    config.persona_id = persona_id
    config.is_active = active
    config.activity_level = level
    config.interest_tags = []
    config.allowed_boards = []
    config.daily_action_limit = daily_limit
    config.actions_today = actions_today
    config.last_action_at = None
    return config


def _make_post(board_id=None, user_id=None, persona_id=None):
    post = MagicMock()
    post.id = uuid.uuid4()
    post.board_id = board_id or uuid.uuid4()
    post.author_user_id = user_id
    post.author_persona_id = persona_id
    post.title = "테스트 게시글"
    post.content = "웹툰 리뷰입니다."
    post.is_hidden = False
    post.is_ai_generated = False
    return post


class TestGetConfig:

    @pytest.mark.asyncio
    async def test_returns_existing_config(self):
        user = _make_user()
        persona = _make_persona(user.id)
        config = _make_config(persona.id)

        db = AsyncMock()
        # _verify_persona_ownership
        persona_result = MagicMock()
        persona_result.scalar_one_or_none.return_value = persona
        # get_config
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config
        db.execute = AsyncMock(side_effect=[persona_result, config_result])

        service = AgentActivityService(db)
        result = await service.get_config(persona.id, user)

        assert result.persona_id == persona.id

    @pytest.mark.asyncio
    async def test_creates_default_config_when_none(self):
        user = _make_user()
        persona = _make_persona(user.id)

        db = AsyncMock()
        persona_result = MagicMock()
        persona_result.scalar_one_or_none.return_value = persona
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(side_effect=[persona_result, config_result])
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        service = AgentActivityService(db)
        result = await service.get_config(persona.id, user)

        # 새 config가 생성되어 add됨
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_non_owner(self):
        user = _make_user()
        other_persona_id = uuid.uuid4()

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        service = AgentActivityService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.get_config(other_persona_id, user)
        assert exc_info.value.status_code == 403


class TestActivateDeactivate:

    @pytest.mark.asyncio
    async def test_activate(self):
        user = _make_user()
        persona = _make_persona(user.id)
        config = _make_config(persona.id, active=False)

        db = AsyncMock()
        persona_result = MagicMock()
        persona_result.scalar_one_or_none.return_value = persona
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config
        db.execute = AsyncMock(side_effect=[persona_result, config_result])
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        service = AgentActivityService(db)
        result = await service.activate(persona.id, user)

        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_deactivate(self):
        user = _make_user()
        persona = _make_persona(user.id)
        config = _make_config(persona.id, active=True)

        db = AsyncMock()
        persona_result = MagicMock()
        persona_result.scalar_one_or_none.return_value = persona
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config
        db.execute = AsyncMock(side_effect=[persona_result, config_result])
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        service = AgentActivityService(db)
        result = await service.deactivate(persona.id, user)

        assert result.is_active is False


class TestSelectResponders:

    def test_excludes_self_reaction(self):
        """자기 글에는 반응하지 않는다."""
        service = AgentActivityService(AsyncMock())
        persona_id = uuid.uuid4()
        config = _make_config(persona_id)
        post = _make_post(persona_id=persona_id)

        selected = service._select_responders([config], post)
        assert len(selected) == 0

    def test_max_count_limit(self):
        """최대 반응 수 제한."""
        service = AgentActivityService(AsyncMock())
        post = _make_post(user_id=uuid.uuid4())

        # 10개 active config 생성
        configs = [_make_config(uuid.uuid4(), level="active") for _ in range(10)]

        with patch("random.random", return_value=0.1):  # 항상 반응
            selected = service._select_responders(configs, post, max_count=3)

        assert len(selected) <= 3

    def test_quiet_low_probability(self):
        """quiet 레벨은 반응 확률이 낮다."""
        service = AgentActivityService(AsyncMock())
        post = _make_post(user_id=uuid.uuid4())
        config = _make_config(uuid.uuid4(), level="quiet")

        # random.random() = 0.5 → quiet 가중치 0.2보다 큼 → 반응 안함
        with patch("random.random", return_value=0.5):
            selected = service._select_responders([config], post)

        assert len(selected) == 0


class TestGeneratePersonaPost:

    @pytest.mark.asyncio
    @patch("app.services.agent_activity_service.settings")
    async def test_skips_inactive_config(self, mock_settings):
        mock_settings.credit_system_enabled = False
        config = _make_config(uuid.uuid4(), active=False)

        db = AsyncMock()
        service = AgentActivityService(db)
        result = await service.generate_persona_post(config)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.agent_activity_service.settings")
    async def test_skips_when_limit_reached(self, mock_settings):
        mock_settings.credit_system_enabled = False
        config = _make_config(uuid.uuid4(), active=True, level="active", daily_limit=5, actions_today=5)

        db = AsyncMock()
        service = AgentActivityService(db)
        result = await service.generate_persona_post(config)

        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.agent_activity_service.settings")
    async def test_skips_non_active_level(self, mock_settings):
        """activity_level이 'active'가 아니면 자발적 게시 안함."""
        mock_settings.credit_system_enabled = False
        config = _make_config(uuid.uuid4(), active=True, level="normal")

        db = AsyncMock()
        service = AgentActivityService(db)
        result = await service.generate_persona_post(config)

        assert result is None


class TestAdminSummary:

    @pytest.mark.asyncio
    async def test_returns_summary_structure(self):
        db = AsyncMock()

        # 쿼리 결과 mock
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        tokens_result = MagicMock()
        tokens_result.one.return_value = (0, 0)
        cost_result = MagicMock()
        cost_result.scalar.return_value = 0

        db.execute = AsyncMock(side_effect=[
            count_result,  # total_today
            count_result,  # total_all
            count_result,  # active_personas
            tokens_result,  # tokens_today
            cost_result,   # cost_today
        ])

        service = AgentActivityService(db)
        result = await service.get_admin_summary()

        assert "total_actions_today" in result
        assert "active_personas" in result
        assert "total_cost_today" in result
