import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    auth,
    board,
    character_cards,
    character_chats,
    character_pages,
    chat,
    credits,
    favorites,
    health,
    image_gen,
    lorebook,
    lounge,
    memories,
    models,
    notifications,
    pending_posts,
    personas,
    policy,
    relationships,
    subscriptions,
    tts,
    uploads,
    usage,
    user_personas,
    webtoons,
    world_events,
)
from app.api.admin import agents as admin_agents
from app.api.admin import debate as admin_debate
from app.api.admin import board as admin_board
from app.api.admin import reports as admin_reports
from app.api.admin import content as admin_content
from app.api.admin import credits as admin_credits
from app.api.admin import llm_models as admin_llm_models
from app.api.admin import monitoring as admin_monitoring
from app.api.admin import personas as admin_personas
from app.api.admin import policy as admin_policy
from app.api.admin import subscriptions as admin_subscriptions
from app.api.admin import system as admin_system
from app.api.admin import usage as admin_usage
from app.api.admin import users as admin_users
from app.api.admin import video_gen as admin_video_gen
from app.api.admin import world_events as admin_world_events
from app.core.config import settings
from app.core.database import engine
from app.core.observability import flush_langfuse, init_sentry, setup_prometheus
from app.core.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

# Sentry 초기화 (앱 모듈 로드 시 즉시)
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 파이프라인 모델 사전 로드 (pipeline_lazy_load=False일 때)
    if not settings.pipeline_lazy_load:
        from app.pipeline import preload_pipelines

        preload_pipelines()

    # 배치 스케줄러 워커 시작
    from app.services.batch_scheduler import BatchScheduler

    scheduler = BatchScheduler.get_instance()
    scheduler.start()

    # 에이전트 스케줄러 시작 (라운지 자동 활동)
    from app.services.agent_scheduler import AgentScheduler

    agent_scheduler = AgentScheduler.get_instance()
    agent_scheduler.start()

    # 토론 자동 매칭 태스크 시작
    if settings.debate_enabled:
        from app.services.debate_auto_match import DebateAutoMatcher

        auto_matcher = DebateAutoMatcher.get_instance()
        auto_matcher.start()

    yield

    # 토론 자동 매칭 태스크 중지
    if settings.debate_enabled:
        auto_matcher.stop()
    # 에이전트 스케줄러 중지
    agent_scheduler.stop()
    # 배치 스케줄러 워커 중지
    scheduler.stop()
    # Langfuse 버퍼 플러시 후 종료
    flush_langfuse()
    await engine.dispose()


app = FastAPI(
    title="Webtoon Review Chatbot API",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

# Prometheus 계측 (/metrics 엔드포인트 노출)
setup_prometheus(app)


@app.exception_handler(NotImplementedError)
async def not_implemented_handler(request: Request, exc: NotImplementedError):
    return JSONResponse(status_code=501, content={"detail": "Not implemented"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """프로덕션에서 내부 에러 메시지 노출 방지."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    if settings.debug:
        return JSONResponse(status_code=500, content={"detail": str(exc)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

app.add_middleware(RateLimitMiddleware)

# User-facing routes
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(personas.router, prefix="/api/personas", tags=["personas"])
app.include_router(lorebook.router, prefix="/api/lorebook", tags=["lorebook"])
app.include_router(webtoons.router, prefix="/api/webtoons", tags=["webtoons"])
app.include_router(policy.router, prefix="/api/policy", tags=["policy"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(usage.router, prefix="/api/usage", tags=["usage"])
app.include_router(credits.router, prefix="/api/credits", tags=["credits"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])
app.include_router(board.router, prefix="/api/board", tags=["board"])
app.include_router(lounge.router, prefix="/api/lounge", tags=["lounge"])
app.include_router(user_personas.router, prefix="/api/user-personas", tags=["user-personas"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["favorites"])
app.include_router(relationships.router, prefix="/api/relationships", tags=["relationships"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(character_cards.router, prefix="/api/character-cards", tags=["character-cards"])
app.include_router(memories.router, prefix="/api/memories", tags=["memories"])
app.include_router(tts.router, prefix="/api/tts", tags=["tts"])
app.include_router(image_gen.router, prefix="/api/image-gen", tags=["image-gen"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(character_pages.router, prefix="/api/character-pages", tags=["character-pages"])
app.include_router(character_chats.router, prefix="/api/character-chats", tags=["character-chats"])
app.include_router(pending_posts.router, prefix="/api/pending-posts", tags=["pending-posts"])
app.include_router(world_events.router, prefix="/api/world-events", tags=["world-events"])

# Debate routes (feature flag)
if settings.debate_enabled:
    from app.api import debate_agents, debate_matches, debate_topics, debate_ws

    app.include_router(debate_agents.router, prefix="/api/agents", tags=["debate-agents"])
    app.include_router(debate_topics.router, prefix="/api/topics", tags=["debate-topics"])
    app.include_router(debate_matches.router, prefix="/api/matches", tags=["debate-matches"])
    app.include_router(debate_ws.router, tags=["debate-ws"])

# Admin routes
app.include_router(admin_users.router, prefix="/api/admin/users", tags=["admin-users"])
app.include_router(admin_personas.router, prefix="/api/admin/personas", tags=["admin-personas"])
app.include_router(admin_content.router, prefix="/api/admin/content", tags=["admin-content"])
app.include_router(admin_policy.router, prefix="/api/admin/policy", tags=["admin-policy"])
app.include_router(admin_llm_models.router, prefix="/api/admin/models", tags=["admin-models"])
app.include_router(admin_usage.router, prefix="/api/admin/usage", tags=["admin-usage"])
app.include_router(admin_monitoring.router, prefix="/api/admin/monitoring", tags=["admin-monitoring"])
app.include_router(admin_system.router, prefix="/api/admin/system", tags=["admin-system"])
app.include_router(admin_credits.router, prefix="/api/admin/credits", tags=["admin-credits"])
app.include_router(admin_subscriptions.router, prefix="/api/admin/subscriptions", tags=["admin-subscriptions"])
app.include_router(admin_board.router, prefix="/api/admin/board", tags=["admin-board"])
app.include_router(admin_reports.router, prefix="/api/admin/reports", tags=["admin-reports"])
app.include_router(admin_agents.router, prefix="/api/admin/agents", tags=["admin-agents"])
app.include_router(admin_video_gen.router, prefix="/api/admin/video-gen", tags=["admin-video-gen"])
app.include_router(admin_world_events.router, prefix="/api/admin/world-events", tags=["admin-world-events"])
if settings.debate_enabled:
    app.include_router(admin_debate.router, prefix="/api/admin/debate", tags=["admin-debate"])

# 업로드 파일 정적 서빙 (라우터 등록 이후에 마운트 — catch-all이므로 순서 중요)
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
