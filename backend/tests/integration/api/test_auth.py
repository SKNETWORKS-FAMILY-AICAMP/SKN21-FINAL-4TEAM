import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "nickname": "newuser",
        "password": "securepass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_with_email(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "nickname": "emailuser",
        "password": "securepass123",
        "email": "test@example.com",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_register_duplicate_nickname(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "nickname": "dupuser",
        "password": "pass1",
    })
    response = await client.post("/api/auth/register", json={
        "nickname": "dupuser",
        "password": "pass2",
    })
    assert response.status_code == 409
    assert "Nickname already taken" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_missing_password(client: AsyncClient):
    response = await client.post("/api/auth/register", json={
        "nickname": "nopassuser",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "nickname": "loginuser",
        "password": "mypassword",
    })
    response = await client.post("/api/auth/login", json={
        "nickname": "loginuser",
        "password": "mypassword",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/auth/register", json={
        "nickname": "wrongpwuser",
        "password": "correct",
    })
    response = await client.post("/api/auth/login", json={
        "nickname": "wrongpwuser",
        "password": "wrong",
    })
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post("/api/auth/login", json={
        "nickname": "ghost",
        "password": "noexist",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["nickname"] == "testuser"
    assert data["role"] == "user"
    assert data["age_group"] == "unverified"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient):
    response = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_adult_verify_success(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.post("/api/auth/adult-verify", json={"method": "phone_verify"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["age_group"] == "adult_verified"
    assert data["adult_verified_at"] is not None


@pytest.mark.asyncio
async def test_admin_endpoint_blocked_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/admin/users/", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_allowed_for_admin(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    response = await client.get("/api/admin/users/", headers=headers)
    # 501 (NotImplementedError) 이 아닌 403이 아님을 확인 — 관리자는 통과
    assert response.status_code != 403
