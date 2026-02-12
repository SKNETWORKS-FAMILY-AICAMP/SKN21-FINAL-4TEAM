import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header

WEBTOON_DATA = {
    "title": "Solo Leveling",
    "platform": "kakao",
    "genre": ["action"],
    "age_rating": "15+",
}


async def _create_webtoon(client: AsyncClient, admin_headers: dict) -> str:
    """테스트용 웹툰 생성 후 ID 반환."""
    resp = await client.post("/api/admin/content/webtoons", json=WEBTOON_DATA, headers=admin_headers)
    return resp.json()["id"]


# ── 스포일러 설정 ──


@pytest.mark.asyncio
async def test_get_spoiler_default(client: AsyncClient, test_user, test_admin):
    """설정이 없을 때 기본값(off) 반환."""
    admin_headers = auth_header(test_admin)
    webtoon_id = await _create_webtoon(client, admin_headers)

    headers = auth_header(test_user)
    response = await client.get(f"/api/policy/spoiler/{webtoon_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "off"
    assert data["max_episode"] is None


@pytest.mark.asyncio
async def test_update_spoiler_setting(client: AsyncClient, test_user, test_admin):
    admin_headers = auth_header(test_admin)
    webtoon_id = await _create_webtoon(client, admin_headers)

    headers = auth_header(test_user)
    response = await client.put(
        f"/api/policy/spoiler/{webtoon_id}",
        json={"mode": "up_to", "max_episode": 50},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "up_to"
    assert data["max_episode"] == 50


@pytest.mark.asyncio
async def test_update_spoiler_full_mode(client: AsyncClient, test_user, test_admin):
    admin_headers = auth_header(test_admin)
    webtoon_id = await _create_webtoon(client, admin_headers)

    headers = auth_header(test_user)
    response = await client.put(
        f"/api/policy/spoiler/{webtoon_id}",
        json={"mode": "full"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "full"


@pytest.mark.asyncio
async def test_update_spoiler_invalid_mode(client: AsyncClient, test_user, test_admin):
    admin_headers = auth_header(test_admin)
    webtoon_id = await _create_webtoon(client, admin_headers)

    headers = auth_header(test_user)
    response = await client.put(
        f"/api/policy/spoiler/{webtoon_id}",
        json={"mode": "invalid_mode"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_spoiler_up_to_requires_max_episode(client: AsyncClient, test_user, test_admin):
    """up_to 모드에서 max_episode 누락 → 422."""
    admin_headers = auth_header(test_admin)
    webtoon_id = await _create_webtoon(client, admin_headers)

    headers = auth_header(test_user)
    response = await client.put(
        f"/api/policy/spoiler/{webtoon_id}",
        json={"mode": "up_to"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_spoiler_setting_update_overwrites(client: AsyncClient, test_user, test_admin):
    """같은 웹툰에 대해 다시 설정하면 덮어씀."""
    admin_headers = auth_header(test_admin)
    webtoon_id = await _create_webtoon(client, admin_headers)
    headers = auth_header(test_user)

    await client.put(
        f"/api/policy/spoiler/{webtoon_id}",
        json={"mode": "up_to", "max_episode": 10},
        headers=headers,
    )
    response = await client.put(
        f"/api/policy/spoiler/{webtoon_id}",
        json={"mode": "full"},
        headers=headers,
    )
    assert response.json()["mode"] == "full"

    # 조회해서 확인
    get_resp = await client.get(f"/api/policy/spoiler/{webtoon_id}", headers=headers)
    assert get_resp.json()["mode"] == "full"


@pytest.mark.asyncio
async def test_spoiler_isolation(client: AsyncClient, test_user, test_adult_user, test_admin):
    """다른 사용자의 스포일러 설정이 영향을 주지 않음."""
    admin_headers = auth_header(test_admin)
    webtoon_id = await _create_webtoon(client, admin_headers)

    # test_adult_user가 스포일러 설정
    adult_headers = auth_header(test_adult_user)
    await client.put(
        f"/api/policy/spoiler/{webtoon_id}",
        json={"mode": "full"},
        headers=adult_headers,
    )

    # test_user는 여전히 기본값
    user_headers = auth_header(test_user)
    response = await client.get(f"/api/policy/spoiler/{webtoon_id}", headers=user_headers)
    assert response.json()["mode"] == "off"


# ── 관리자 연령등급 정책 ──


@pytest.mark.asyncio
async def test_admin_get_age_rating_policy(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    response = await client.get("/api/admin/policy/age-rating", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "ratings" in data
    assert "18+" in data["adult_verification_required"]


@pytest.mark.asyncio
async def test_admin_update_age_rating_policy(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    response = await client.put("/api/admin/policy/age-rating", json={
        "ratings": ["all", "15+", "18+"],
        "default": "all",
        "adult_verification_required": ["18+"],
        "enabled": True,
    }, headers=headers)
    assert response.status_code == 200
    assert response.json()["ratings"] == ["all", "15+", "18+"]


@pytest.mark.asyncio
async def test_admin_policy_forbidden_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/admin/policy/age-rating", headers=headers)
    assert response.status_code == 403
