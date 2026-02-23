"""게시판 API 통합 테스트."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models.user import User
from tests.conftest import auth_header


async def _grant_credits(db_session, user, amount=1000):
    """테스트 유저에게 크레딧 부여."""
    await db_session.execute(
        update(User).where(User.id == user.id).values(credit_balance=amount)
    )
    await db_session.commit()


async def _seed_board(db_session):
    """테스트용 게시판 시드 데이터."""
    from app.models.board import Board

    board = Board(
        board_key="test-free",
        display_name="테스트 자유게시판",
        age_rating="all",
        is_active=True,
        sort_order=1,
    )
    db_session.add(board)
    await db_session.commit()
    await db_session.refresh(board)
    return board


async def _seed_18_board(db_session):
    from app.models.board import Board

    board = Board(
        board_key="test-adult",
        display_name="성인 게시판",
        age_rating="18+",
        is_active=True,
        sort_order=2,
    )
    db_session.add(board)
    await db_session.commit()
    await db_session.refresh(board)
    return board


async def _create_post(client, headers, board_id, title="테스트 글", content="테스트 내용"):
    resp = await client.post(f"/api/board/{board_id}/posts", json={
        "title": title,
        "content": content,
    }, headers=headers)
    return resp


# ── 게시판 목록 ──


@pytest.mark.asyncio
async def test_get_boards(client: AsyncClient, test_user, db_session):
    await _seed_board(db_session)
    headers = auth_header(test_user)
    resp = await client.get("/api/board/boards", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["board_key"] == "test-free"


@pytest.mark.asyncio
async def test_get_boards_filters_18_for_unverified(client: AsyncClient, test_user, db_session):
    """미인증 사용자에게 18+ 게시판이 안 보인다."""
    await _seed_18_board(db_session)
    headers = auth_header(test_user)
    resp = await client.get("/api/board/boards", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # 18+ 게시판이 필터링됨
    board_keys = [b["board_key"] for b in data]
    assert "test-adult" not in board_keys


@pytest.mark.asyncio
async def test_get_boards_shows_18_for_adult(client: AsyncClient, test_adult_user, db_session):
    await _seed_board(db_session)
    await _seed_18_board(db_session)
    headers = auth_header(test_adult_user)
    resp = await client.get("/api/board/boards", headers=headers)
    data = resp.json()
    board_keys = [b["board_key"] for b in data]
    assert "test-adult" in board_keys


# ── 게시글 작성 ──


@pytest.mark.asyncio
async def test_create_post_success(client: AsyncClient, test_user, db_session):
    board = await _seed_board(db_session)
    await _grant_credits(db_session, test_user)
    headers = auth_header(test_user)
    resp = await _create_post(client, headers, str(board.id))
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data


@pytest.mark.asyncio
async def test_create_post_board_not_found(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    resp = await _create_post(client, headers, str(uuid.uuid4()))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_post_18_board_blocked(client: AsyncClient, test_user, db_session):
    """미인증 사용자가 18+ 게시판에 글 작성 → 403."""
    board = await _seed_18_board(db_session)
    headers = auth_header(test_user)
    resp = await _create_post(client, headers, str(board.id))
    assert resp.status_code == 403


# ── 피드 ──


@pytest.mark.asyncio
async def test_get_feed_empty(client: AsyncClient, test_user, db_session):
    board = await _seed_board(db_session)
    headers = auth_header(test_user)
    resp = await client.get(f"/api/board/{board.id}/posts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_get_feed_with_posts(client: AsyncClient, test_user, db_session):
    board = await _seed_board(db_session)
    await _grant_credits(db_session, test_user)
    headers = auth_header(test_user)
    await _create_post(client, headers, str(board.id), "글1", "내용1")
    await _create_post(client, headers, str(board.id), "글2", "내용2")

    resp = await client.get(f"/api/board/{board.id}/posts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


# ── 게시글 상세 ──


@pytest.mark.asyncio
async def test_get_post_detail(client: AsyncClient, test_user, db_session):
    board = await _seed_board(db_session)
    await _grant_credits(db_session, test_user)
    headers = auth_header(test_user)
    create_resp = await _create_post(client, headers, str(board.id))
    post_id = create_resp.json()["id"]

    resp = await client.get(f"/api/board/posts/{post_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["post"]["id"] == post_id
    assert data["comments"] == []


# ── 댓글 ──


@pytest.mark.asyncio
async def test_create_comment(client: AsyncClient, test_user, db_session):
    board = await _seed_board(db_session)
    await _grant_credits(db_session, test_user)
    headers = auth_header(test_user)
    create_resp = await _create_post(client, headers, str(board.id))
    post_id = create_resp.json()["id"]

    resp = await client.post(f"/api/board/posts/{post_id}/comments", json={
        "content": "좋은 글이네요!",
    }, headers=headers)
    assert resp.status_code == 201
    assert "id" in resp.json()


@pytest.mark.asyncio
async def test_create_reply(client: AsyncClient, test_user, db_session):
    """답글 작성."""
    board = await _seed_board(db_session)
    await _grant_credits(db_session, test_user)
    headers = auth_header(test_user)
    create_resp = await _create_post(client, headers, str(board.id))
    post_id = create_resp.json()["id"]

    comment_resp = await client.post(f"/api/board/posts/{post_id}/comments", json={
        "content": "첫 댓글",
    }, headers=headers)
    comment_id = comment_resp.json()["id"]

    reply_resp = await client.post(f"/api/board/posts/{post_id}/comments", json={
        "content": "답글입니다",
        "parent_id": comment_id,
    }, headers=headers)
    assert reply_resp.status_code == 201


# ── 리액션 ──


@pytest.mark.asyncio
async def test_toggle_post_reaction(client: AsyncClient, test_user, db_session):
    board = await _seed_board(db_session)
    await _grant_credits(db_session, test_user)
    headers = auth_header(test_user)
    create_resp = await _create_post(client, headers, str(board.id))
    post_id = create_resp.json()["id"]

    # 좋아요 추가
    resp1 = await client.post(f"/api/board/posts/{post_id}/reactions", json={
        "reaction_type": "like",
    }, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["toggled"] is True
    assert resp1.json()["new_count"] == 1

    # 좋아요 제거
    resp2 = await client.post(f"/api/board/posts/{post_id}/reactions", json={
        "reaction_type": "like",
    }, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["toggled"] is False
    assert resp2.json()["new_count"] == 0


# ── 관리자 ──


@pytest.mark.asyncio
async def test_admin_get_posts(client: AsyncClient, test_admin, test_user, db_session):
    board = await _seed_board(db_session)
    await _grant_credits(db_session, test_user)
    user_headers = auth_header(test_user)
    await _create_post(client, user_headers, str(board.id))

    admin_headers = auth_header(test_admin)
    resp = await client.get("/api/admin/board/posts", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_admin_hide_post(client: AsyncClient, test_admin, test_user, db_session):
    board = await _seed_board(db_session)
    await _grant_credits(db_session, test_user)
    user_headers = auth_header(test_user)
    create_resp = await _create_post(client, user_headers, str(board.id))
    post_id = create_resp.json()["id"]

    admin_headers = auth_header(test_admin)
    resp = await client.put(f"/api/admin/board/posts/{post_id}/hide", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_requires_admin_role(client: AsyncClient, test_user):
    """일반 사용자가 관리자 API 접근 → 403."""
    headers = auth_header(test_user)
    resp = await client.get("/api/admin/board/posts", headers=headers)
    assert resp.status_code == 403
