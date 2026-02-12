from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, personas, lorebook, webtoons, policy, auth, models, usage, health
from app.api.admin import users as admin_users
from app.api.admin import personas as admin_personas
from app.api.admin import content as admin_content
from app.api.admin import policy as admin_policy
from app.api.admin import llm_models as admin_llm_models
from app.api.admin import usage as admin_usage
from app.api.admin import monitoring as admin_monitoring
from app.api.admin import system as admin_system
from app.core.config import settings
from app.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Webtoon Review Chatbot API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Admin routes
app.include_router(admin_users.router, prefix="/api/admin/users", tags=["admin-users"])
app.include_router(admin_personas.router, prefix="/api/admin/personas", tags=["admin-personas"])
app.include_router(admin_content.router, prefix="/api/admin/content", tags=["admin-content"])
app.include_router(admin_policy.router, prefix="/api/admin/policy", tags=["admin-policy"])
app.include_router(admin_llm_models.router, prefix="/api/admin/models", tags=["admin-models"])
app.include_router(admin_usage.router, prefix="/api/admin/usage", tags=["admin-usage"])
app.include_router(admin_monitoring.router, prefix="/api/admin/monitoring", tags=["admin-monitoring"])
app.include_router(admin_system.router, prefix="/api/admin/system", tags=["admin-system"])
