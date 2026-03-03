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
    debate_elo_k_factor: int = 32              # ELO K 팩터
    debate_elo_score_diff_scale: int = 100    # 판정 점수차 정규화 기준 (0~100 범위)
    debate_elo_score_diff_weight: float = 1.0  # 점수차 배수 가중치 (0=사용 안 함, 1=최대 2배)
    debate_elo_score_mult_max: float = 2.0    # 점수차 배수 상한
    debate_elo_forfeit_score_diff: int = 100  # 몰수패 시 적용 점수차 (최대 패널티)
    debate_turn_timeout_seconds: int = 60
    debate_turn_delay_seconds: float = 1.5  # 턴 사이 딜레이 (초) — 관전 UX 개선
    debate_orchestrator_model: str = "gpt-4o"
    debate_agent_connect_timeout: int = 30  # 로컬 에이전트 접속 대기 (초)
    debate_ws_heartbeat_interval: int = 15  # WebSocket 핑 간격 (초)
    debate_queue_timeout_seconds: int = 120  # 대기 큐 자동 매칭 타임아웃 (초)
    debate_pending_timeout_seconds: int = 600  # pending/waiting_agent 매치 자동 error 처리 (초)
    debate_daily_topic_limit: int = 5  # 사용자 일일 토픽 등록 한도
    debate_credit_cost: int = 5  # 매치 참가 시 차감 크레딧
    debate_turn_review_enabled: bool = True   # 턴 검토 기능 ON/OFF
    debate_turn_review_timeout: int = 10      # 검토 LLM 타임아웃 (초)
    debate_turn_review_model: str = ""        # 빈 문자열이면 debate_orchestrator_model 사용

    # Orchestrator Optimization (Phase 1–3)
    # 2026-02 GPT 전 모델 벤치마크 결과 반영:
    #   Review 2위 gpt-5-nano: 성능 8.907점 (현행 gpt-4o-mini 8.602점), 비용 43% 절감
    #   Judge  5위 gpt-4.1:    성능 8.936점 (현행 gpt-4o 8.501점), 비용 20% 절감
    #   전체 매치 비용: $0.01329 vs 현행 $0.01739 (23.6% 절감)
    debate_review_model: str = "gpt-5-nano"   # Phase1: 경량 검토 모델 (벤치마크 최적: 성능↑ 비용↓)
    debate_judge_model: str = "gpt-4.1"       # Phase1: 중량 판정 모델 (벤치마크 최적: 성능↑ 비용↓)
    debate_review_fast_path: bool = True       # Phase3: 정규식 무위반 턴은 LLM 검토 스킵
    debate_orchestrator_optimized: bool = True # 최적화 오케스트레이터 활성화 (Phase 1-3 통합)

    # 토론 요약 리포트 (기능 11)
    debate_summary_enabled: bool = True
    debate_summary_model: str = "gpt-4o-mini"

    # Rate Limiting
    rate_limit_auth: int = 20
    rate_limit_chat: int = 30
    rate_limit_api: int = 60
    rate_limit_debate: int = 120  # 토론 관련 엔드포인트 (SSE 포함) — 일반보다 2배
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
