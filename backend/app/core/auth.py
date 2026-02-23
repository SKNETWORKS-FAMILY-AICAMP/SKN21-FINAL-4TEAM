import logging
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """bcrypt 해시 비밀번호 검증."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """평문 비밀번호 → bcrypt 해시."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """JWT 액세스 토큰 생성. sub 클레임에 사용자 ID를 포함."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """JWT 토큰 디코딩. 유효하지 않으면 None 반환."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


# --- 토큰 블랙리스트 (Redis 기반) ---

_BLACKLIST_PREFIX = "token_blacklist:"


async def blacklist_token(token: str) -> None:
    """토큰을 블랙리스트에 추가. 토큰 만료 시간까지만 유지."""
    from app.core.redis import redis_client

    payload = decode_access_token(token)
    if payload is None:
        return
    exp = payload.get("exp", 0)
    ttl = max(int(exp - datetime.now(UTC).timestamp()), 0)
    if ttl > 0:
        try:
            await redis_client.setex(f"{_BLACKLIST_PREFIX}{token}", ttl, "1")
        except Exception:
            logger.warning("Failed to blacklist token (Redis unavailable)")


async def is_token_blacklisted(token: str) -> bool:
    """토큰이 블랙리스트에 있는지 확인."""
    from app.core.redis import redis_client

    try:
        return await redis_client.exists(f"{_BLACKLIST_PREFIX}{token}") > 0
    except Exception:
        logger.warning("Failed to check token blacklist (Redis unavailable)")
        return False


async def blacklist_all_user_tokens(user_id: str) -> None:
    """사용자의 모든 토큰을 무효화 (비밀번호 변경 등). 토큰 버전 번호로 처리."""
    from app.core.redis import redis_client

    try:
        await redis_client.set(f"user_token_revoked:{user_id}", str(datetime.now(UTC).timestamp()))
    except Exception:
        logger.warning("Failed to revoke user tokens (Redis unavailable)")
