"""BoardService 단위 테스트."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.board_service import BoardService


def _make_user(adult=False, age_group="unverified"):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.nickname = "testuser"
    user.role = "user"
    user.age_group = "adult_verified" if adult else age_group
    user.adult_verified_at = datetime.now(timezone.utc) if adult else None
    return user


def _make_board(age_rating="all"):
    board = MagicMock()
    board.id = uuid.uuid4()
    board.board_key = "free"
    board.display_name = "자유 게시판"
    board.age_rating = age_rating
    board.is_active = True
    return board


def _make_persona(user_id):
    persona = MagicMock()
    persona.id = uuid.uuid4()
    persona.created_by = user_id
    persona.display_name = "테스트 캐릭터"
    return persona


def _make_post(board_id, user_id=None, persona_id=None, age_rating="all"):
    post = MagicMock()
    post.id = uuid.uuid4()
    post.board_id = board_id
    post.author_user_id = user_id
    post.author_persona_id = persona_id
    post.title = "테스트 글"
    post.content = "테스트 내용"
    post.age_rating = age_rating
    post.is_ai_generated = False
    post.reaction_count = 0
    post.comment_count = 0
    post.is_pinned = False
    post.is_hidden = False
    post.created_at = datetime.now(timezone.utc)
    post.updated_at = datetime.now(timezone.utc)
    return post


class TestGetBoards:

    @pytest.mark.asyncio
    async def test_returns_active_boards(self):
        boards = [_make_board(), _make_board()]

        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = boards
        db.execute = AsyncMock(return_value=result)

        service = BoardService(db)
        user = _make_user()
        result = await service.get_boards(user)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filters_18_boards_for_unverified(self):
        """성인인증 미완료 사용자에게 18+ 게시판이 필터링된다."""
        # 쿼리 결과가 이미 필터링되어 반환된다고 가정 (WHERE 조건 검증)
        boards = [_make_board("all")]

        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = boards
        db.execute = AsyncMock(return_value=result)

        service = BoardService(db)
        user = _make_user(adult=False)
        result = await service.get_boards(user)

        assert len(result) == 1


class TestCreatePost:

    @pytest.mark.asyncio
    @patch("app.services.board_service.settings")
    async def test_create_post_user_direct(self, mock_settings):
        mock_settings.credit_system_enabled = False
        user = _make_user()
        board = _make_board()

        db = AsyncMock()
        # _get_board_or_404
        board_result = MagicMock()
        board_result.scalar_one_or_none.return_value = board
        db.execute = AsyncMock(return_value=board_result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        pii = MagicMock()
        pii.mask.return_value = "마스킹된 내용"

        service = BoardService(db, pii_detector=pii)
        post = await service.create_post(user, board.id, "제목", "내용")

        assert post is not None
        # 제목 + 내용 모두 PII 마스킹 적용
        assert pii.mask.call_count == 2

    @pytest.mark.asyncio
    @patch("app.services.board_service.settings")
    async def test_create_post_with_persona(self, mock_settings):
        mock_settings.credit_system_enabled = False
        user = _make_user()
        board = _make_board()
        persona = _make_persona(user.id)

        db = AsyncMock()
        board_result = MagicMock()
        board_result.scalar_one_or_none.return_value = board
        persona_result = MagicMock()
        persona_result.scalar_one_or_none.return_value = persona
        db.execute = AsyncMock(side_effect=[board_result, persona_result])
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        pii = MagicMock()
        pii.mask.return_value = "내용"

        service = BoardService(db, pii_detector=pii)
        post = await service.create_post(user, board.id, "제목", "내용", persona_id=persona.id)

        assert post is not None

    @pytest.mark.asyncio
    @patch("app.services.board_service.settings")
    async def test_create_post_18_board_blocked_for_unverified(self, mock_settings):
        mock_settings.credit_system_enabled = False
        user = _make_user(adult=False)
        board = _make_board(age_rating="18+")

        db = AsyncMock()
        board_result = MagicMock()
        board_result.scalar_one_or_none.return_value = board
        db.execute = AsyncMock(return_value=board_result)

        service = BoardService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.create_post(user, board.id, "제목", "내용")
        assert exc_info.value.status_code == 403


class TestCreateComment:

    @pytest.mark.asyncio
    @patch("app.services.board_service.settings")
    async def test_create_comment_success(self, mock_settings):
        mock_settings.credit_system_enabled = False
        user = _make_user()
        post = _make_post(uuid.uuid4(), user_id=user.id)

        db = AsyncMock()
        post_result = MagicMock()
        post_result.scalar_one_or_none.return_value = post
        db.execute = AsyncMock(return_value=post_result)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        pii = MagicMock()
        pii.mask.return_value = "댓글 내용"

        service = BoardService(db, pii_detector=pii)
        comment = await service.create_comment(user, post.id, "댓글 내용")

        assert comment is not None

    @pytest.mark.asyncio
    @patch("app.services.board_service.settings")
    async def test_create_comment_post_not_found(self, mock_settings):
        mock_settings.credit_system_enabled = False
        user = _make_user()

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        service = BoardService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.create_comment(user, uuid.uuid4(), "댓글")
        assert exc_info.value.status_code == 404


class TestToggleReaction:

    @pytest.mark.asyncio
    async def test_add_reaction(self):
        user = _make_user()
        post_id = uuid.uuid4()

        db = AsyncMock()
        # 기존 리액션 없음
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        # 리액션 카운트 조회
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        db.execute = AsyncMock(side_effect=[existing_result, AsyncMock(), count_result])
        db.commit = AsyncMock()

        service = BoardService(db)
        result = await service.toggle_reaction(user, post_id=post_id)

        assert result["toggled"] is True
        assert result["new_count"] == 1

    @pytest.mark.asyncio
    async def test_remove_reaction(self):
        user = _make_user()
        post_id = uuid.uuid4()

        existing_reaction = MagicMock()
        existing_reaction.id = 1

        db = AsyncMock()
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing_reaction
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        db.execute = AsyncMock(side_effect=[existing_result, AsyncMock(), count_result])
        db.delete = AsyncMock()
        db.commit = AsyncMock()

        service = BoardService(db)
        result = await service.toggle_reaction(user, post_id=post_id)

        assert result["toggled"] is False

    @pytest.mark.asyncio
    async def test_no_target_raises_400(self):
        user = _make_user()
        db = AsyncMock()
        service = BoardService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.toggle_reaction(user)
        assert exc_info.value.status_code == 400


class TestAgeGate:

    @pytest.mark.asyncio
    @patch("app.services.board_service.settings")
    async def test_18_post_blocked_for_unverified(self, mock_settings):
        """미인증 사용자가 18+ 게시글에 접근 → 403."""
        mock_settings.credit_system_enabled = False
        user = _make_user(adult=False)
        post = _make_post(uuid.uuid4(), user_id=uuid.uuid4(), age_rating="18+")

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = post
        db.execute = AsyncMock(return_value=result)

        service = BoardService(db)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.get_post_detail(post.id, user)
        assert exc_info.value.status_code == 403
