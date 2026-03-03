"""Redis 기반 슬라이딩 윈도우 Rate Limiter.

Sorted Set을 사용한 슬라이딩 윈도우 알고리즘으로 요청 빈도를 제한한다.
키 패턴: rate_limit:{identifier}:{route_group}
"""

import logging
import time

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

# Rate limit을 적용하지 않는 경로
BYPASS_PATHS = {"/health", "/metrics"}

# route group → (limit, window) 매핑을 설정에서 동적 구성
ROUTE_GROUP_PREFIXES = [
    ("/api/admin", "admin"),
    ("/api/auth", "auth"),
    ("/api/chat", "chat"),
    # 토론 라우트: SSE 스트림 연결 + 다수 폴링 요청으로 일반 limit 초과 빈발
    ("/api/matches", "debate"),
    ("/api/topics", "debate"),
    ("/api/agents", "debate"),
    ("/api/tournaments", "debate"),
]


def _get_route_group(path: str) -> str:
    """요청 경로에서 rate limit 그룹을 결정한다."""
    for prefix, group in ROUTE_GROUP_PREFIXES:
        if path.startswith(prefix):
            return group
    return "api"


def _get_rate_limit_config(route_group: str) -> tuple[int, int]:
    """route group에 대한 (limit, window_seconds) 반환."""
    limit_map = {
        "auth": settings.rate_limit_auth,
        "chat": settings.rate_limit_chat,
        "api": settings.rate_limit_api,
        "debate": settings.rate_limit_debate,
        "admin": settings.rate_limit_admin,
    }
    limit = limit_map.get(route_group, settings.rate_limit_api)
    return limit, settings.rate_limit_window


def _extract_identifier(request: Request) -> str:
    """JWT sub 클레임(인증된 사용자) 또는 클라이언트 IP를 식별자로 추출한다."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except JWTError:
            pass

    # 인증 실패 또는 토큰 없음 → X-Real-IP (nginx 프록시 헤더) 우선, 없으면 소켓 IP
    real_ip = (
        request.headers.get("x-real-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    return f"ip:{real_ip}"


async def check_rate_limit(identifier: str, route_group: str) -> tuple[bool, int, int, int]:
    """슬라이딩 윈도우 rate limit 검사.

    Returns:
        (allowed, limit, remaining, reset_timestamp)
    """
    limit, window = _get_rate_limit_config(route_group)
    now = time.time()
    window_start = now - window
    reset_at = int(now) + window
    key = f"rate_limit:{identifier}:{route_group}"

    pipe = redis_client.pipeline()
    # 윈도우 밖의 오래된 항목 제거
    pipe.zremrangebyscore(key, 0, window_start)
    # 현재 요청 추가 (score=timestamp, member=timestamp로 고유성 보장)
    pipe.zadd(key, {str(now): now})
    # 현재 윈도우 내 요청 수
    pipe.zcard(key)
    # 키 TTL 설정 (윈도우 크기 + 여유 1초)
    pipe.expire(key, window + 1)
    results = await pipe.execute()

    current_count = results[2]
    remaining = max(0, limit - current_count)
    allowed = current_count <= limit

    return allowed, limit, remaining, reset_at


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI 미들웨어: 모든 요청에 슬라이딩 윈도우 rate limit을 적용한다."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # rate limit 비활성화 시 바이패스
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # 헬스체크, 메트릭 등 바이패스 경로
        if request.url.path in BYPASS_PATHS:
            return await call_next(request)

        # SSE 스트림은 지속 연결이므로 rate limit 제외 (/stream으로 끝나는 경로)
        if request.url.path.endswith("/stream"):
            return await call_next(request)

        identifier = _extract_identifier(request)
        route_group = _get_route_group(request.url.path)

        try:
            allowed, limit, remaining, reset_at = await check_rate_limit(identifier, route_group)
        except Exception:
            # Redis 장애 시 요청을 허용한다 (graceful degradation)
            logger.warning("Rate limit check failed (Redis unavailable), allowing request", exc_info=True)
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": reset_at - int(time.time()),
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                    "Retry-After": str(reset_at - int(time.time())),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response
