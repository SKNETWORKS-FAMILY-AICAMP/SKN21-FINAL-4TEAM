import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.episode import Episode
from app.models.webtoon import Webtoon
from tests.conftest import auth_header

WEBTOON_ALL = {
    "title": "전연령 웹툰",
    "platform": "naver",
    "genre": ["comedy"],
    "age_rating": "all",
    "total_episodes": 0,
    "status": "ongoing",
}

WEBTOON_18 = {
    "title": "성인 웹툰",
    "platform": "kakao",
    "genre": ["romance"],
    "age_rating": "18+",
    "total_episodes": 0,
    "status": "ongoing",
}


@pytest_asyncio.fixture
async def webtoon_all(db_session: AsyncSession):
    wt = Webtoon(**WEBTOON_ALL)
    db_session.add(wt)
    await db_session.commit()
    await db_session.refresh(wt)
    return wt


@pytest_asyncio.fixture
async def webtoon_18(db_session: AsyncSession):
    wt = Webtoon(**WEBTOON_18)
    db_session.add(wt)
    await db_session.commit()
    await db_session.refresh(wt)
    return wt


@pytest_asyncio.fixture
async def episodes(db_session: AsyncSession, webtoon_all: Webtoon):
    eps = []
    for i in range(1, 4):
        ep = Episode(
            webtoon_id=webtoon_all.id,
            episode_number=i,
            title=f"제 {i}화",
            summary=f"제 {i}화 줄거리",
        )
        db_session.add(ep)
        eps.append(ep)
    await db_session.commit()
    for ep in eps:
        await db_session.refresh(ep)
    return eps


# ══════════════════════════════════
# GET /api/webtoons/
# ══════════════════════════════════


@pytest.mark.asyncio
async def test_list_webtoons_returns_all_rated(client: AsyncClient, test_user, webtoon_all, webtoon_18):
    """미인증 사용자는 전연령 웹툰만 조회 가능."""
    headers = auth_header(test_user)
    response = await client.get("/api/webtoons", headers=headers)
    assert response.status_code == 200
    data = response.json()
    titles = [w["title"] for w in data["items"]]
    assert "전연령 웹툰" in titles
    assert "성인 웹툰" not in titles


@pytest.mark.asyncio
async def test_list_webtoons_adult_sees_all(client: AsyncClient, test_adult_user, webtoon_all, webtoon_18):
    """성인인증 사용자는 모든 웹툰 조회 가능."""
    headers = auth_header(test_adult_user)
    response = await client.get("/api/webtoons", headers=headers)
    assert response.status_code == 200
    data = response.json()
    titles = [w["title"] for w in data["items"]]
    assert "전연령 웹툰" in titles
    assert "성인 웹툰" in titles


@pytest.mark.asyncio
async def test_list_webtoons_pagination(client: AsyncClient, test_user, webtoon_all):
    headers = auth_header(test_user)
    response = await client.get("/api/webtoons?skip=0&limit=1", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 1


@pytest.mark.asyncio
async def test_list_webtoons_filter_platform(client: AsyncClient, test_adult_user, webtoon_all, webtoon_18):
    headers = auth_header(test_adult_user)
    response = await client.get("/api/webtoons?platform=naver", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert all(w["platform"] == "naver" for w in data["items"])


@pytest.mark.asyncio
async def test_list_webtoons_filter_genre(client: AsyncClient, test_user, webtoon_all):
    headers = auth_header(test_user)
    response = await client.get("/api/webtoons?genre=comedy", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_list_webtoons_unauthorized(client: AsyncClient, webtoon_all):
    response = await client.get("/api/webtoons")
    assert response.status_code in (401, 403)


# ══════════════════════════════════
# GET /api/webtoons/{webtoon_id}
# ══════════════════════════════════


@pytest.mark.asyncio
async def test_get_webtoon_detail(client: AsyncClient, test_user, webtoon_all, episodes):
    headers = auth_header(test_user)
    response = await client.get(f"/api/webtoons/{webtoon_all.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "전연령 웹툰"
    assert len(data["episodes"]) == 3
    # 회차 번호 정렬 확인
    nums = [e["episode_number"] for e in data["episodes"]]
    assert nums == sorted(nums)


@pytest.mark.asyncio
async def test_get_webtoon_not_found(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get(f"/api/webtoons/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_webtoon_18_blocked_for_unverified(client: AsyncClient, test_user, webtoon_18):
    """미인증 사용자는 18+ 웹툰 상세 접근 불가."""
    headers = auth_header(test_user)
    response = await client.get(f"/api/webtoons/{webtoon_18.id}", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_webtoon_18_allowed_for_adult(client: AsyncClient, test_adult_user, webtoon_18):
    """성인인증 사용자는 18+ 웹툰 접근 가능."""
    headers = auth_header(test_adult_user)
    response = await client.get(f"/api/webtoons/{webtoon_18.id}", headers=headers)
    assert response.status_code == 200


# ══════════════════════════════════
# GET /api/webtoons/{id}/episodes/{num}
# ══════════════════════════════════


@pytest.mark.asyncio
async def test_get_episode_detail(client: AsyncClient, test_user, webtoon_all, episodes):
    headers = auth_header(test_user)
    response = await client.get(f"/api/webtoons/{webtoon_all.id}/episodes/1", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["episode_number"] == 1
    assert data["title"] == "제 1화"
    assert "emotions" in data
    assert "comment_stats" in data


@pytest.mark.asyncio
async def test_get_episode_not_found(client: AsyncClient, test_user, webtoon_all):
    headers = auth_header(test_user)
    response = await client.get(f"/api/webtoons/{webtoon_all.id}/episodes/999", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_episode_webtoon_not_found(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get(f"/api/webtoons/{uuid.uuid4()}/episodes/1", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_episode_18_blocked(client: AsyncClient, test_user, webtoon_18):
    """미인증 사용자는 18+ 웹툰의 에피소드 접근 불가."""
    headers = auth_header(test_user)
    response = await client.get(f"/api/webtoons/{webtoon_18.id}/episodes/1", headers=headers)
    assert response.status_code == 403
