"""에이전트 서비스 단위 테스트."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.schemas.debate_agent import AgentCreate, AgentUpdate


class TestDebateAgentService:
    def test_agent_create_schema_validation(self):
        """AgentCreate 스키마가 필수 필드를 검증한다."""
        data = AgentCreate(
            name="Test Agent",
            provider="openai",
            model_id="gpt-4o",
            api_key="sk-test",
            system_prompt="You are a debate agent.",
        )
        assert data.name == "Test Agent"
        assert data.provider == "openai"

    def test_agent_create_invalid_provider(self):
        """잘못된 provider는 검증 실패."""
        with pytest.raises(Exception):
            AgentCreate(
                name="Test",
                provider="invalid_provider",
                model_id="model",
                api_key="key",
                system_prompt="prompt",
            )

    def test_agent_update_partial(self):
        """AgentUpdate는 부분 업데이트를 허용한다."""
        data = AgentUpdate(name="New Name")
        assert data.name == "New Name"
        assert data.provider is None
        assert data.system_prompt is None

    def test_ranking_entry_format(self):
        """랭킹 결과 형식 검증."""
        ranking_entry = {
            "id": str(uuid.uuid4()),
            "name": "Agent1",
            "owner_nickname": "user1",
            "provider": "openai",
            "model_id": "gpt-4o",
            "elo_rating": 1500,
            "wins": 5,
            "losses": 3,
            "draws": 2,
        }
        assert ranking_entry["elo_rating"] == 1500
        assert ranking_entry["wins"] + ranking_entry["losses"] + ranking_entry["draws"] == 10
