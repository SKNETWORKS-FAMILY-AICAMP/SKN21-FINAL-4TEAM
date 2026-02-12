import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spoiler_setting import SpoilerSetting
from app.models.user import User

VALID_SPOILER_MODES = ("off", "theme_only", "up_to", "full")


class PolicyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 스포일러 설정 ──

    async def get_spoiler_setting(self, user: User, webtoon_id: uuid.UUID) -> dict:
        """사용자의 웹툰별 스포일러 설정 조회. 없으면 기본값 반환."""
        result = await self.db.execute(
            select(SpoilerSetting).where(
                SpoilerSetting.user_id == user.id,
                SpoilerSetting.webtoon_id == webtoon_id,
            )
        )
        setting = result.scalar_one_or_none()

        if setting is None:
            return {
                "webtoon_id": str(webtoon_id),
                "mode": "off",
                "max_episode": None,
            }

        return {
            "id": setting.id,
            "webtoon_id": str(setting.webtoon_id),
            "mode": setting.mode,
            "max_episode": setting.max_episode,
            "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
        }

    async def update_spoiler_setting(
        self, user: User, webtoon_id: uuid.UUID, mode: str, max_episode: int | None = None
    ) -> dict:
        """스포일러 설정 생성 또는 변경."""
        if mode not in VALID_SPOILER_MODES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid mode. Must be one of: {', '.join(VALID_SPOILER_MODES)}",
            )

        if mode == "up_to" and max_episode is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="max_episode is required when mode is 'up_to'",
            )

        result = await self.db.execute(
            select(SpoilerSetting).where(
                SpoilerSetting.user_id == user.id,
                SpoilerSetting.webtoon_id == webtoon_id,
            )
        )
        setting = result.scalar_one_or_none()

        if setting is None:
            setting = SpoilerSetting(
                user_id=user.id,
                webtoon_id=webtoon_id,
                mode=mode,
                max_episode=max_episode,
            )
            self.db.add(setting)
        else:
            setting.mode = mode
            setting.max_episode = max_episode
            setting.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(setting)

        return {
            "id": setting.id,
            "webtoon_id": str(setting.webtoon_id),
            "mode": setting.mode,
            "max_episode": setting.max_episode,
            "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
        }

    # ── 연령 게이트 ──

    async def check_age_gate(self, user: User, age_rating: str) -> bool:
        """연령등급 게이트 검증. False면 접근 차단."""
        if age_rating == "all":
            return True
        if age_rating in ("12+", "15+"):
            return True
        if age_rating == "18+":
            return user.adult_verified_at is not None
        return False

    # ── 정책 스냅샷 ──

    async def build_policy_snapshot(self, user: User, webtoon_id: uuid.UUID | None) -> dict:
        """메시지 생성 시점 정책 상태 스냅샷."""
        snapshot = {
            "user_id": str(user.id),
            "age_group": user.age_group,
            "adult_verified": user.adult_verified_at is not None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if webtoon_id:
            spoiler = await self.get_spoiler_setting(user, webtoon_id)
            snapshot["spoiler"] = spoiler

        return snapshot
