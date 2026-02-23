import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    nickname: str
    password: str
    email: str | None = None

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("닉네임은 2자 이상이어야 합니다")
        if len(v) > 20:
            raise ValueError("닉네임은 20자 이하여야 합니다")
        if not re.match(r"^[a-zA-Z0-9가-힣_]+$", v):
            raise ValueError("닉네임은 한글, 영문, 숫자, 밑줄(_)만 사용 가능합니다")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다")
        if len(v) > 100:
            raise ValueError("비밀번호는 100자 이하여야 합니다")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("비밀번호에 영문자가 포함되어야 합니다")
        if not re.search(r"\d", v):
            raise ValueError("비밀번호에 숫자가 포함되어야 합니다")
        return v


class UserLogin(BaseModel):
    nickname: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    nickname: str
    role: str
    age_group: str
    adult_verified_at: datetime | None = None
    preferred_llm_model_id: UUID | None = None
    preferred_themes: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    nickname: str | None = None
    preferred_themes: list[str] | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("비밀번호는 8자 이상이어야 합니다")
        if len(v) > 100:
            raise ValueError("비밀번호는 100자 이하여야 합니다")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("비밀번호에 영문자가 포함되어야 합니다")
        if not re.search(r"\d", v):
            raise ValueError("비밀번호에 숫자가 포함되어야 합니다")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Admin 전용 스키마 ──


class AdminUserDetailResponse(BaseModel):
    """관리자용 사용자 상세 (관계 카운트 + 크레딧 포함)."""

    id: UUID
    nickname: str
    role: str
    age_group: str
    adult_verified_at: datetime | None = None
    preferred_llm_model_id: UUID | None = None
    preferred_themes: list[str] | None = None
    credit_balance: int = 0
    last_credit_grant_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    persona_count: int = 0
    session_count: int = 0
    message_count: int = 0
    subscription_status: str | None = None

    model_config = {"from_attributes": True}


class UserStats(BaseModel):
    total_users: int = 0
    superadmin_count: int = 0
    admin_count: int = 0
    adult_verified_count: int = 0
    unverified_count: int = 0
    minor_safe_count: int = 0


class BulkDeleteRequest(BaseModel):
    user_ids: list[UUID]

    @field_validator("user_ids")
    @classmethod
    def validate_max_ids(cls, v: list[UUID]) -> list[UUID]:
        if len(v) > 50:
            raise ValueError("최대 50명까지 선택 가능합니다")
        return v


class BulkDeleteResponse(BaseModel):
    deleted_count: int = 0
    skipped_admin_ids: list[UUID] = []
