import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header

PERSONA_DATA = {
    "persona_key": "chat-persona",
    "version": "v1.0",
    "display_name": "Chat Test Character",
    "system_prompt": "You are a friendly webtoon reviewer.",
    "style_rules": {"tone": "casual"},
    "safety_rules": {},
}

MOCK_LLM_RESPONSE = {
    "content": "This is a mock LLM response about the webtoon!",
    "input_tokens": 150,
    "output_tokens": 30,
    "finish_reason": "stop",
}


async def _setup_persona_and_model(client, headers, db_session):
    """테스트용 페르소나 + LLM 모델 생성."""
    # 페르소나 생성
    resp = await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    persona_id = resp.json()["id"]

    # LLM 모델 직접 DB 삽입
    from app.models.llm_model import LLMModel
    model = LLMModel(
        id=uuid.uuid4(),
        provider="openai",
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        input_cost_per_1m=0.15,
        output_cost_per_1m=0.60,
        max_context_length=128000,
        is_active=True,
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)

    return persona_id, str(model.id)


# ── 세션 생성 ──


@pytest.mark.asyncio
async def test_create_session_success(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    persona_id, model_id = await _setup_persona_and_model(client, headers, db_session)

    response = await client.post("/api/chat/sessions", json={
        "persona_id": persona_id,
        "llm_model_id": model_id,
    }, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["persona_id"] == persona_id
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_create_session_invalid_persona(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.post("/api/chat/sessions", json={
        "persona_id": str(uuid.uuid4()),
    }, headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_session_18_requires_adult(client: AsyncClient, test_user, test_adult_user, db_session):
    """18+ 페르소나 세션은 성인인증 필요."""
    # 성인인증 사용자가 18+ 페르소나 생성
    adult_headers = auth_header(test_adult_user)
    data = {**PERSONA_DATA, "persona_key": "adult-chat", "age_rating": "18+"}
    resp = await client.post("/api/personas/", json=data, headers=adult_headers)
    persona_id = resp.json()["id"]

    # 미인증 사용자가 세션 생성 시도
    user_headers = auth_header(test_user)
    response = await client.post("/api/chat/sessions", json={
        "persona_id": persona_id,
    }, headers=user_headers)
    assert response.status_code == 403


# ── 세션 목록 ──


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    persona_id, model_id = await _setup_persona_and_model(client, headers, db_session)

    # 2개 세션 생성
    await client.post("/api/chat/sessions", json={"persona_id": persona_id}, headers=headers)
    await client.post("/api/chat/sessions", json={"persona_id": persona_id}, headers=headers)

    response = await client.get("/api/chat/sessions", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_sessions_isolation(client: AsyncClient, test_user, test_adult_user, db_session):
    """다른 사용자의 세션이 보이지 않음."""
    headers_user = auth_header(test_user)
    persona_id, _ = await _setup_persona_and_model(client, headers_user, db_session)

    # test_user 세션 생성
    await client.post("/api/chat/sessions", json={"persona_id": persona_id}, headers=headers_user)

    # test_adult_user의 세션 목록은 비어있어야 함
    headers_adult = auth_header(test_adult_user)
    response = await client.get("/api/chat/sessions", headers=headers_adult)
    assert response.json()["total"] == 0


# ── 메시지 전송 (비스트리밍, LLM mock) ──


@pytest.mark.asyncio
async def test_send_message(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    persona_id, model_id = await _setup_persona_and_model(client, headers, db_session)

    # 세션 생성
    sess_resp = await client.post("/api/chat/sessions", json={
        "persona_id": persona_id,
        "llm_model_id": model_id,
    }, headers=headers)
    session_id = sess_resp.json()["id"]

    # LLM mock
    with patch("app.services.chat_service.InferenceClient.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_LLM_RESPONSE

        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "Tell me about this webtoon"},
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "assistant"
        assert data["content"] == MOCK_LLM_RESPONSE["content"]
        assert data["token_count"] == 30
        mock_gen.assert_called_once()


@pytest.mark.asyncio
async def test_send_message_wrong_session(client: AsyncClient, test_user, test_adult_user, db_session):
    """다른 사용자의 세션에 메시지 전송 → 404."""
    headers_user = auth_header(test_user)
    persona_id, _ = await _setup_persona_and_model(client, headers_user, db_session)

    sess_resp = await client.post("/api/chat/sessions", json={
        "persona_id": persona_id,
    }, headers=headers_user)
    session_id = sess_resp.json()["id"]

    # 다른 사용자가 메시지 전송 시도
    headers_adult = auth_header(test_adult_user)
    response = await client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": "Hacked"},
        headers=headers_adult,
    )
    assert response.status_code == 404


# ── 메시지 히스토리 ──


@pytest.mark.asyncio
async def test_get_messages(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    persona_id, model_id = await _setup_persona_and_model(client, headers, db_session)

    sess_resp = await client.post("/api/chat/sessions", json={
        "persona_id": persona_id,
        "llm_model_id": model_id,
    }, headers=headers)
    session_id = sess_resp.json()["id"]

    # 메시지 전송
    with patch("app.services.chat_service.InferenceClient.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_LLM_RESPONSE
        await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "Hello"},
            headers=headers,
        )

    # 히스토리 조회
    response = await client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # user + assistant
    assert data["items"][0]["role"] == "user"
    assert data["items"][0]["content"] == "Hello"
    assert data["items"][1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_get_messages_wrong_session(client: AsyncClient, test_user, test_adult_user, db_session):
    """다른 사용자의 세션 메시지 조회 → 404."""
    headers_user = auth_header(test_user)
    persona_id, _ = await _setup_persona_and_model(client, headers_user, db_session)

    sess_resp = await client.post("/api/chat/sessions", json={
        "persona_id": persona_id,
    }, headers=headers_user)
    session_id = sess_resp.json()["id"]

    headers_adult = auth_header(test_adult_user)
    response = await client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers_adult)
    assert response.status_code == 404


# ── SSE 스트리밍 ──


@pytest.mark.asyncio
async def test_send_message_stream(client: AsyncClient, test_user, db_session):
    headers = auth_header(test_user)
    persona_id, model_id = await _setup_persona_and_model(client, headers, db_session)

    sess_resp = await client.post("/api/chat/sessions", json={
        "persona_id": persona_id,
        "llm_model_id": model_id,
    }, headers=headers)
    session_id = sess_resp.json()["id"]

    # 스트리밍 mock
    async def mock_stream(*args, **kwargs):
        for chunk in ["Hello ", "from ", "stream!"]:
            yield chunk

    with patch("app.services.chat_service.InferenceClient.generate_stream", side_effect=mock_stream):
        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages/stream",
            json={"content": "Stream test"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        # SSE 데이터 파싱
        body = response.text
        assert "Hello " in body
        assert "from " in body
        assert "stream!" in body
        assert "[DONE]" in body


# ── No LLM model available ──


@pytest.mark.asyncio
async def test_send_message_no_model(client: AsyncClient, test_user, db_session):
    """LLM 모델이 없으면 503."""
    headers = auth_header(test_user)

    # 페르소나만 생성 (LLM 모델 없음)
    resp = await client.post("/api/personas/", json=PERSONA_DATA, headers=headers)
    persona_id = resp.json()["id"]

    sess_resp = await client.post("/api/chat/sessions", json={
        "persona_id": persona_id,
    }, headers=headers)
    session_id = sess_resp.json()["id"]

    response = await client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"content": "Hello"},
        headers=headers,
    )
    assert response.status_code == 503
