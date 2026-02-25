"""화면 활성화/비활성화 플래그 관리 서비스 (Redis 기반).

Redis 키 없으면 기본값 True(활성). AOF+RDB 영구 저장이므로 재시작 후에도 유지된다.
"""
from dataclasses import dataclass

from app.core.redis import get_redis

_FLAG_PREFIX = "feature_flag:"


@dataclass
class ScreenFlagMeta:
    key: str
    label: str
    description: str
    category: str  # "user" | "admin"


ALL_SCREENS: list[ScreenFlagMeta] = [
    # 사용자 화면
    ScreenFlagMeta("chat", "채팅", "채팅 세션 생성 및 대화 (sessions, chat/*)", "user"),
    ScreenFlagMeta("personas", "페르소나", "페르소나 목록/생성/수정", "user"),
    ScreenFlagMeta("community", "커뮤니티", "커뮤니티 게시글 및 댓글", "user"),
    ScreenFlagMeta("character_pages", "캐릭터 페이지", "캐릭터 프로필/팔로우/피드", "user"),
    ScreenFlagMeta("character_chats", "캐릭터 채팅", "캐릭터 간 1:1 대화", "user"),
    ScreenFlagMeta("debate", "AI 토론", "AI 에이전트 토론 플랫폼", "user"),
    ScreenFlagMeta("favorites", "즐겨찾기", "페르소나 즐겨찾기", "user"),
    ScreenFlagMeta("relationships", "관계도", "캐릭터 호감도 및 관계 추적", "user"),
    ScreenFlagMeta("pending_posts", "승인 큐", "게시물 수동 퍼블리싱 대기 관리", "user"),
    ScreenFlagMeta("mypage", "마이페이지", "마이페이지 (프로필/설정/사용량/구독)", "user"),
    ScreenFlagMeta("notifications", "알림", "알림 목록 및 읽음 처리", "user"),
    # 관리자 전용 화면
    ScreenFlagMeta("admin_video_gen", "영상 생성 관리", "관리자 영상 생성 관리 화면", "admin"),
    ScreenFlagMeta("admin_debate", "AI 토론 관리", "관리자 AI 토론 관리 화면", "admin"),
]

_ALL_KEYS: set[str] = {m.key for m in ALL_SCREENS}


async def get_all_flags() -> dict[str, bool]:
    """모든 화면 플래그 상태 반환. Redis에 값이 없으면 기본값 True(활성)."""
    redis = await get_redis()
    keys = [f"{_FLAG_PREFIX}{m.key}" for m in ALL_SCREENS]
    values = await redis.mget(*keys)
    return {
        meta.key: (val is None or val == "1")
        for meta, val in zip(ALL_SCREENS, values, strict=True)
    }


async def set_flag(key: str, enabled: bool) -> None:
    """단일 화면 플래그 설정."""
    if key not in _ALL_KEYS:
        raise ValueError(f"Unknown feature flag key: {key}")
    redis = await get_redis()
    await redis.set(f"{_FLAG_PREFIX}{key}", "1" if enabled else "0")


async def reset_all_flags() -> None:
    """모든 플래그를 기본값(활성화)으로 리셋 — Redis 키 삭제로 처리."""
    redis = await get_redis()
    keys = [f"{_FLAG_PREFIX}{m.key}" for m in ALL_SCREENS]
    if keys:
        await redis.delete(*keys)
