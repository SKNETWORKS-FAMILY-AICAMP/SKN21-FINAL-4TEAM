from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://chatbot:chatbot@localhost:5432/chatbot"
    database_sync_url: str = "postgresql+psycopg://chatbot:chatbot@localhost:5432/chatbot"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth — SECRET_KEY는 반드시 .env에서 설정 (기본값 사용 금지)
    secret_key: str = ""
    access_token_expire_minutes: int = 10080  # 7일 (프로토타입 — 로그인 유지 편의)

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # RunPod
    runpod_api_key: str = ""
    runpod_endpoint_id: str = ""
    runpod_ltx_endpoint_id: str = ""  # LTX-Video-2 전용 엔드포인트

    # External LLM APIs
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    # Sentry
    sentry_dsn: str = ""

    # Pipeline
    pipeline_device: str = ""  # 'cuda', 'cpu', '' (auto-detect)
    emotion_model: str = "searle-j/kote_for_easygoing_people"
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    # True면 첫 호출 시 로드, False면 startup에서 로드
    pipeline_lazy_load: bool = True

    # Quotas (defaults for new users)
    default_daily_token_limit: int = 100_000  # 10만 토큰/일
    default_monthly_token_limit: int = 2_000_000  # 200만 토큰/월
    default_monthly_cost_limit: float = 10.0  # $10/월
    quota_enabled: bool = True

    # Credits
    free_daily_credits: int = 50
    premium_daily_credits: int = 300
    credit_system_enabled: bool = True

    # TTS
    tts_provider: str = "openai"  # openai | elevenlabs | google
    tts_default_voice: str = "alloy"  # OpenAI: alloy|echo|fable|onyx|nova|shimmer
    elevenlabs_api_key: str = ""
    elevenlabs_default_voice_id: str = ""
    tts_output_format: str = "mp3"  # mp3 | opus | aac | wav
    tts_enabled: bool = True

    # Image Generation
    image_gen_provider: str = "openai"  # openai | stability
    stability_api_key: str = ""
    image_gen_default_style: str = "anime"
    image_gen_enabled: bool = True

    # Uploads
    upload_dir: str = "uploads"
    max_upload_size: int = 5_242_880  # 5MB
    allowed_image_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    ]

    # Adult Verification
    # 프로덕션에서는 False로 설정 — 자가선언(생년월일 입력)으로 성인인증 우회 방지
    allow_self_declare: bool = False

    # Debate Platform
    debate_enabled: bool = False
    debate_default_elo: int = 1500
    debate_elo_k_factor: int = 32
    debate_turn_timeout_seconds: int = 60
    debate_orchestrator_model: str = "gpt-4o"
    debate_agent_connect_timeout: int = 30  # 로컬 에이전트 접속 대기 (초)
    debate_ws_heartbeat_interval: int = 15  # WebSocket 핑 간격 (초)
    debate_queue_timeout_seconds: int = 120  # 대기 큐 자동 매칭 타임아웃 (초)

    # Rate Limiting
    rate_limit_auth: int = 20
    rate_limit_chat: int = 60
    rate_limit_api: int = 300
    rate_limit_admin: int = 120
    rate_limit_window: int = 60  # seconds
    rate_limit_enabled: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# 프로덕션 안전 검증: 약한 시크릿 키로 기동 방지
if not settings.secret_key or settings.secret_key == "change-me-in-production":
    if settings.app_env != "development":
        raise RuntimeError(
            "SECRET_KEY must be set to a strong random value in production. "
            "Use: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    else:
        import warnings

        warnings.warn(
            "SECRET_KEY is not set. Using empty key for development only.",
            stacklevel=1,
        )
