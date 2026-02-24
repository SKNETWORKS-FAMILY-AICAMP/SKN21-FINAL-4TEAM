"""성인인증 서비스.

프로토타입: 실제 본인인증 API 대신 mock provider 사용.
확장 시: 휴대폰 본인인증(PASS), 카드 인증, SSO 등 실제 provider 교체.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.consent_log import ConsentLog
from app.models.user import User

logger = logging.getLogger(__name__)

# 동의 만료 기간 (개인정보 보호법 — 목적 달성 후 파기)
CONSENT_EXPIRY_DAYS = 365


class VerifyMethod(str, Enum):
    PHONE = "phone"
    CARD = "card"
    SSO = "sso"
    SELF_DECLARE = "self_declare"  # 프로토타입용 자가 선언


class VerifyStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AdultVerifyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify(self, user: User, method: str, extra: dict | None = None) -> dict:
        """성인인증 처리.

        1. 이미 인증된 사용자 체크
        2. method별 provider 호출 (프로토타입: 테스트용 검증 로직)
        3. 사용자 상태 업데이트
        4. 동의 이력 기록
        """
        # 이미 인증 완료
        if user.adult_verified_at is not None:
            return {
                "status": "already_verified",
                "verified_at": user.adult_verified_at.isoformat(),
                "method": user.auth_method,
            }

        # 자가선언 비활성화 체크 (프로덕션 보안)
        if method == VerifyMethod.SELF_DECLARE and not settings.allow_self_declare:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Self-declaration verification is disabled. Please use phone, card, or SSO verification.",
            )

        # method 검증
        if method not in [m.value for m in VerifyMethod]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid method. Allowed: {', '.join(m.value for m in VerifyMethod)}",
            )

        # provider 호출에 사용할 추가 데이터 저장
        self._extra = extra or {}

        # provider 호출 (프로토타입: 테스트용 검증 로직)
        verification_result = await self._call_provider(method, user)

        if not verification_result["success"]:
            # 인증 실패 이력 기록
            await self._log_consent(
                user_id=user.id,
                consent_type="adult_verify",
                consent_status="revoked",
                scope={"method": method, "reason": verification_result.get("reason", "rejected")},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=verification_result.get("reason", "Verification failed"),
            )

        # 성인인증 성공: 사용자 상태 업데이트
        now = datetime.now(UTC)
        user.age_group = "adult_verified"
        user.adult_verified_at = now
        user.auth_method = method

        # 청소년보호법 시행령 기반 동의 이력 기록
        await self._log_consent(
            user_id=user.id,
            consent_type="adult_verify",
            consent_status="granted",
            scope={
                "method": method,
                "provider_ref": verification_result.get("reference_id"),
            },
            expires_at=now + timedelta(days=CONSENT_EXPIRY_DAYS),
        )

        await self.db.commit()
        await self.db.refresh(user)

        return {
            "status": "verified",
            "verified_at": now.isoformat(),
            "method": method,
        }

    async def check_status(self, user: User) -> dict:
        """성인인증 상태 확인."""
        if user.adult_verified_at is None:
            available = [m.value for m in VerifyMethod if m != VerifyMethod.SELF_DECLARE or settings.allow_self_declare]
        return {
                "verified": False,
                "age_group": user.age_group,
                "available_methods": available,
            }

        # 동의 만료 체크
        consent = await self._get_latest_consent(user.id)
        expired = False
        if consent and consent.expires_at and consent.expires_at < datetime.now(UTC):
            expired = True

        return {
            "verified": not expired,
            "age_group": user.age_group,
            "verified_at": user.adult_verified_at.isoformat(),
            "method": user.auth_method,
            "expired": expired,
        }

    async def revoke(self, user: User) -> dict:
        """성인인증 철회 (사용자 요청 시)."""
        if user.adult_verified_at is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Not verified",
            )

        user.age_group = "unverified"
        user.adult_verified_at = None
        user.auth_method = None

        await self._log_consent(
            user_id=user.id,
            consent_type="adult_verify",
            consent_status="revoked",
            scope={"reason": "user_requested"},
        )

        await self.db.commit()
        await self.db.refresh(user)

        return {"status": "revoked"}

    async def get_consent_history(self, user_id: uuid.UUID) -> list[dict]:
        """사용자의 동의 이력 조회."""
        result = await self.db.execute(
            select(ConsentLog).where(ConsentLog.user_id == user_id).order_by(ConsentLog.created_at.desc()).limit(20)
        )
        logs = result.scalars().all()
        return [
            {
                "id": log.id,
                "consent_type": log.consent_type,
                "status": log.status,
                "scope": log.scope,
                "expires_at": log.expires_at.isoformat() if log.expires_at else None,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

    # ── Provider ──

    async def _call_provider(self, method: str, user: User) -> dict:
        """인증 provider 호출. 프로토타입: 모든 요청을 성공 처리.

        확장 시 이 메서드를 실제 인증 API (PASS, 카드사, SSO)로 교체.
        """
        match method:
            case VerifyMethod.PHONE:
                return await self._verify_phone(user)
            case VerifyMethod.CARD:
                return await self._verify_card(user)
            case VerifyMethod.SSO:
                return await self._verify_sso(user)
            case VerifyMethod.SELF_DECLARE:
                return await self._verify_self_declare(user)
            case _:
                return {"success": False, "reason": "Unknown method"}

    async def _verify_phone(self, user: User) -> dict:
        """휴대폰 본인인증 (테스트용: 인증코드 '123456'으로 고정)."""
        code = self._extra.get("code", "")
        if code != "123456":
            return {"success": False, "reason": "인증코드가 올바르지 않습니다"}
        phone = self._extra.get("phone_number", "")
        if not phone or len(phone) < 10:
            return {"success": False, "reason": "올바른 전화번호를 입력하세요"}
        logger.info("Phone verification for user %s (test mode)", user.id)
        return {
            "success": True,
            "reference_id": f"PHONE-TEST-{uuid.uuid4().hex[:8]}",
        }

    async def _verify_card(self, user: User) -> dict:
        """카드 본인인증 (테스트용: 생년 기반 연령 확인)."""
        birth_year = self._extra.get("birth_year", 0)
        card_last4 = self._extra.get("card_last4", "")
        if not card_last4 or len(card_last4) != 4 or not card_last4.isdigit():
            return {"success": False, "reason": "카드 마지막 4자리를 입력하세요"}
        if not self._check_adult_age(birth_year):
            return {"success": False, "reason": "만 19세 미만은 성인인증이 불가합니다"}
        logger.info("Card verification for user %s (test mode)", user.id)
        return {
            "success": True,
            "reference_id": f"CARD-TEST-{uuid.uuid4().hex[:8]}",
        }

    async def _verify_sso(self, user: User) -> dict:
        """SSO 인증 (테스트용: 생년 기반 연령 확인)."""
        birth_year = self._extra.get("birth_year", 0)
        if not self._check_adult_age(birth_year):
            return {"success": False, "reason": "만 19세 미만은 성인인증이 불가합니다"}
        logger.info("SSO verification for user %s (test mode)", user.id)
        return {
            "success": True,
            "reference_id": f"SSO-TEST-{uuid.uuid4().hex[:8]}",
        }

    async def _verify_self_declare(self, user: User) -> dict:
        """자가 선언 (테스트용: 생년 기반 연령 확인)."""
        birth_year = self._extra.get("birth_year", 0)
        if not self._check_adult_age(birth_year):
            return {"success": False, "reason": "만 19세 미만은 성인인증이 불가합니다"}
        logger.info("Self-declare verification for user %s (test mode)", user.id)
        return {
            "success": True,
            "reference_id": f"SELF-TEST-{uuid.uuid4().hex[:8]}",
        }

    @staticmethod
    def _check_adult_age(birth_year: int) -> bool:
        """한국 기준 만 19세 이상인지 확인."""
        if not birth_year or birth_year < 1900:
            return False
        current_year = datetime.now(UTC).year
        return (current_year - birth_year) >= 19

    # ── 헬퍼 ──

    async def _log_consent(
        self,
        user_id: uuid.UUID,
        consent_type: str,
        consent_status: str,
        scope: dict | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        consent = ConsentLog(
            user_id=user_id,
            consent_type=consent_type,
            status=consent_status,
            scope=scope,
            expires_at=expires_at,
        )
        self.db.add(consent)

    async def _get_latest_consent(self, user_id: uuid.UUID) -> ConsentLog | None:
        result = await self.db.execute(
            select(ConsentLog)
            .where(
                ConsentLog.user_id == user_id,
                ConsentLog.consent_type == "adult_verify",
                ConsentLog.status == "granted",
            )
            .order_by(ConsentLog.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
