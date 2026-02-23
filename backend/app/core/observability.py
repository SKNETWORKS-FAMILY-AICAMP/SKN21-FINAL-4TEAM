"""Observability 통합 모듈: Langfuse + Sentry + Prometheus."""

import logging
from contextvars import ContextVar

from app.core.config import settings

logger = logging.getLogger(__name__)

# Langfuse 트레이스 컨텍스트를 request 단위로 전파
_current_trace: ContextVar = ContextVar("langfuse_trace", default=None)
_langfuse_client = None


def get_langfuse():
    """Langfuse 클라이언트 싱글턴."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.info("Langfuse keys not configured, tracing disabled.")
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info("Langfuse client initialized (host=%s)", settings.langfuse_host)
        return _langfuse_client
    except Exception:
        logger.warning("Failed to initialize Langfuse", exc_info=True)
        return None


def create_trace(name: str, user_id: str | None = None, session_id: str | None = None, metadata: dict | None = None):
    """새 Langfuse 트레이스 생성 + ContextVar에 저장."""
    langfuse = get_langfuse()
    if langfuse is None:
        return None

    trace = langfuse.trace(
        name=name,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata or {},
    )
    _current_trace.set(trace)
    return trace


def get_current_trace():
    """현재 request의 Langfuse 트레이스 반환."""
    return _current_trace.get(None)


def create_span(name: str, **kwargs):
    """현재 트레이스에 span 추가."""
    trace = get_current_trace()
    if trace is None:
        return None
    return trace.span(name=name, **kwargs)


def create_generation(name: str, model: str, input_messages: list[dict], **kwargs):
    """LLM generation 이벤트 기록."""
    trace = get_current_trace()
    if trace is None:
        return None
    return trace.generation(
        name=name,
        model=model,
        input=input_messages,
        **kwargs,
    )


def flush_langfuse():
    """Langfuse 버퍼 플러시."""
    langfuse = get_langfuse()
    if langfuse:
        langfuse.flush()


# ── Sentry ──

_sentry_initialized = False


def init_sentry():
    """Sentry SDK 초기화."""
    global _sentry_initialized
    if _sentry_initialized:
        return

    if not settings.sentry_dsn:
        logger.info("Sentry DSN not configured, error tracking disabled.")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            traces_sample_rate=0.1 if settings.app_env == "production" else 1.0,
            profiles_sample_rate=0.1 if settings.app_env == "production" else 1.0,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
            send_default_pii=False,  # PII 최소화 원칙
        )
        _sentry_initialized = True
        logger.info("Sentry initialized (env=%s)", settings.app_env)
    except Exception:
        logger.warning("Failed to initialize Sentry", exc_info=True)


def set_sentry_user(user_id: str, role: str):
    """Sentry에 현재 사용자 컨텍스트 설정."""
    try:
        import sentry_sdk

        sentry_sdk.set_user({"id": user_id, "role": role})
    except Exception:
        pass


def capture_exception(exc: Exception, **context):
    """Sentry에 예외 전송."""
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    except Exception:
        logger.error("Failed to capture exception to Sentry", exc_info=True)


# ── Prometheus ──


def setup_prometheus(app):
    """Prometheus 메트릭 계측 설정."""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/health", "/metrics"],
        )
        instrumentator.instrument(app).expose(app, endpoint="/metrics")

        logger.info("Prometheus instrumentation enabled at /metrics")
    except Exception:
        logger.warning("Failed to setup Prometheus", exc_info=True)


# ── 커스텀 Prometheus 메트릭 ──

_llm_request_duration = None
_llm_token_counter = None
_pipeline_duration = None


def get_metrics():
    """커스텀 Prometheus 메트릭 싱글턴."""
    global _llm_request_duration, _llm_token_counter, _pipeline_duration

    if _llm_request_duration is not None:
        return _llm_request_duration, _llm_token_counter, _pipeline_duration

    try:
        from prometheus_client import Counter, Histogram

        _llm_request_duration = Histogram(
            "llm_request_duration_seconds",
            "LLM API request duration",
            labelnames=["provider", "model"],
            buckets=[0.5, 1, 2, 5, 10, 30, 60],
        )

        _llm_token_counter = Counter(
            "llm_tokens_total",
            "Total LLM tokens processed",
            labelnames=["provider", "model", "direction"],  # direction: input/output
        )

        _pipeline_duration = Histogram(
            "pipeline_duration_seconds",
            "NLP pipeline processing duration",
            labelnames=["pipeline"],  # emotion, embedding, reranker, pii, korean_nlp
            buckets=[0.01, 0.05, 0.1, 0.5, 1, 5],
        )

        return _llm_request_duration, _llm_token_counter, _pipeline_duration
    except Exception:
        return None, None, None


def record_llm_metrics(provider: str, model: str, duration: float, input_tokens: int, output_tokens: int):
    """LLM 호출 메트릭 기록."""
    duration_hist, token_counter, _ = get_metrics()
    if duration_hist:
        duration_hist.labels(provider=provider, model=model).observe(duration)
    if token_counter:
        token_counter.labels(provider=provider, model=model, direction="input").inc(input_tokens)
        token_counter.labels(provider=provider, model=model, direction="output").inc(output_tokens)


def record_pipeline_duration(pipeline_name: str, duration: float):
    """파이프라인 처리 시간 기록."""
    _, _, pipeline_hist = get_metrics()
    if pipeline_hist:
        pipeline_hist.labels(pipeline=pipeline_name).observe(duration)
