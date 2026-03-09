"""BYOK API 키 암호화. Fernet 대칭 암호화로 사용자 API 키를 안전하게 저장."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _derive_fernet_key() -> bytes:
    # ENCRYPTION_KEY가 설정되면 우선 사용, 없으면 SECRET_KEY에서 파생 (하위 호환)
    source = settings.encryption_key if settings.encryption_key else settings.secret_key
    digest = hashlib.sha256(source.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_api_key(plaintext: str) -> str:
    """API 키를 Fernet으로 암호화하여 base64 문자열 반환."""
    f = Fernet(_derive_fernet_key())
    return f.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """암호화된 API 키를 복호화."""
    f = Fernet(_derive_fernet_key())
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt API key: invalid key or corrupted data") from exc
