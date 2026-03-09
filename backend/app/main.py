import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api import (
    auth,
    health,
    models,
    uploads,
    usage,
)
from app.api.admin.debate import agents as admin_debate_agents
from app.api.admin.debate import matches as admin_debate_matches
from app.api.admin.debate import seasons as admin_debate_seasons
from app.api.admin.debate import stats as admin_debate_stats
from app.api.admin.debate import templates as admin_debate_templates
from app.api.admin.debate import tournaments as admin_debate_tournaments
from app.api.admin.system import llm_models as admin_llm_models
from app.api.admin.system import monitoring as admin_monitoring
from app.api.admin.system import usage as admin_usage
from app.api.admin.system import users as admin_users
from app.core.config import settings
from app.core.database import engine
from app.core.observability import flush_langfuse, init_sentry, setup_prometheus
from app.core.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

# Sentry 초기화 (앱 모듈 로드 시 즉시)
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 토론 자동 매칭 태스크 + WS pub/sub 리스너 시작
    if settings.debate_enabled:
        from app.services.debate_matching_service import DebateAutoMatcher
        from app.services.debate_ws_manager import WSConnectionManager

        auto_matcher = DebateAutoMatcher.get_instance()
        auto_matcher.start()

        ws_manager = WSConnectionManager.get_instance()
        await ws_manager.start_pubsub_listener()

    yield

    # 토론 자동 매칭 태스크 + WS pub/sub 리스너 중지
    if settings.debate_enabled:
        auto_matcher.stop()
        await ws_manager.stop_pubsub_listener()
    # Langfuse 버퍼 플러시 후 종료
    flush_langfuse()
    await engine.dispose()


app = FastAPI(
    title="AI 에이전트 토론 플랫폼 API",
    version="1.0.0",
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
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Cookie"],
)

app.add_middleware(RateLimitMiddleware)

# User-facing routes
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(usage.router, prefix="/api/usage", tags=["usage"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])

# Debate routes (feature flag)
if settings.debate_enabled:
    from app.api import debate_agents, debate_matches, debate_topics, debate_tournaments, debate_ws

    app.include_router(debate_agents.router, prefix="/api/agents", tags=["debate-agents"])
    app.include_router(debate_topics.router, prefix="/api/topics", tags=["debate-topics"])
    app.include_router(debate_matches.router, prefix="/api/matches", tags=["debate-matches"])
    app.include_router(debate_tournaments.router, prefix="/api/tournaments", tags=["tournaments"])
    app.include_router(debate_ws.router, tags=["debate-ws"])

# Admin routes
app.include_router(admin_users.router, prefix="/api/admin/users", tags=["admin-users"])
app.include_router(admin_llm_models.router, prefix="/api/admin/models", tags=["admin-models"])
app.include_router(admin_usage.router, prefix="/api/admin/usage", tags=["admin-usage"])
app.include_router(admin_monitoring.router, prefix="/api/admin/monitoring", tags=["admin-monitoring"])
if settings.debate_enabled:
    _debate_prefix = "/api/admin/debate"
    _debate_tags = ["admin-debate"]
    app.include_router(admin_debate_stats.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_matches.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_agents.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_seasons.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_tournaments.router, prefix=_debate_prefix, tags=_debate_tags)
    app.include_router(admin_debate_templates.router, prefix=_debate_prefix, tags=_debate_tags)

# 업로드 파일 디렉토리 생성
os.makedirs(settings.upload_dir, exist_ok=True)


@app.get("/uploads/{path:path}")
async def serve_upload_file(path: str):
    """업로드 파일 서빙 (인증 불필요 — 프로필 이미지는 공개 자원)."""
    upload_dir = Path(settings.upload_dir).resolve()
    file_path = (upload_dir / path).resolve()

    # 경로 순회 공격 방지
    if not file_path.is_relative_to(upload_dir):
        return JSONResponse(status_code=403, content={"detail": "Access denied"})
    if not file_path.is_file():
        return JSONResponse(status_code=404, content={"detail": "File not found"})

    return FileResponse(str(file_path))
