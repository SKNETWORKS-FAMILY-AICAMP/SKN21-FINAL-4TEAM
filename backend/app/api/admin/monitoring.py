from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.llm_model import LLMModel
from app.models.persona import Persona
from app.models.token_usage_log import TokenUsageLog
from app.models.user import User

router = APIRouter()


@router.get("/stats")
async def get_system_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """시스템 통계 (사용자수, 세션수, 메시지수, 페르소나수)."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # 전체 카운트
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar()
    total_sessions = (await db.execute(select(func.count()).select_from(ChatSession))).scalar()
    total_messages = (await db.execute(select(func.count()).select_from(ChatMessage))).scalar()
    total_personas = (await db.execute(select(func.count()).select_from(Persona))).scalar()

    # 오늘 활성 세션
    active_today = (
        await db.execute(select(func.count()).select_from(ChatSession).where(ChatSession.last_active_at >= today_start))
    ).scalar()

    # 최근 7일 신규 사용자
    new_users_week = (
        await db.execute(select(func.count()).select_from(User).where(User.created_at >= week_ago))
    ).scalar()

    # 오늘 메시지 수
    messages_today = (
        await db.execute(select(func.count()).select_from(ChatMessage).where(ChatMessage.created_at >= today_start))
    ).scalar()

    # 모더레이션 대기 페르소나
    pending_moderation = (
        await db.execute(select(func.count()).select_from(Persona).where(Persona.moderation_status == "pending"))
    ).scalar()

    return {
        "totals": {
            "users": total_users,
            "sessions": total_sessions,
            "messages": total_messages,
            "personas": total_personas,
        },
        "today": {
            "active_sessions": active_today,
            "messages": messages_today,
        },
        "weekly": {
            "new_users": new_users_week,
        },
        "moderation": {
            "pending_personas": pending_moderation,
        },
    }


@router.get("/logs")
async def get_activity_logs(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=200),
):
    """최근 활동 로그 (토큰 사용, 세션 생성 등)."""
    since = datetime.now(UTC) - timedelta(days=days)

    # 최근 토큰 사용 로그 (사용자 닉네임, 모델명 JOIN)
    usage_query = (
        select(
            TokenUsageLog.id,
            TokenUsageLog.user_id,
            TokenUsageLog.session_id,
            TokenUsageLog.llm_model_id,
            TokenUsageLog.input_tokens,
            TokenUsageLog.output_tokens,
            TokenUsageLog.cost,
            TokenUsageLog.created_at,
            User.nickname.label("user_nickname"),
            LLMModel.display_name.label("model_name"),
            LLMModel.provider.label("model_provider"),
        )
        .join(User, TokenUsageLog.user_id == User.id)
        .outerjoin(LLMModel, TokenUsageLog.llm_model_id == LLMModel.id)
        .where(TokenUsageLog.created_at >= since)
        .order_by(TokenUsageLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(usage_query)
    logs = result.all()

    return {
        "logs": [
            {
                "id": log.id,
                "user_id": str(log.user_id),
                "user_nickname": log.user_nickname or str(log.user_id)[:8],
                "session_id": str(log.session_id) if log.session_id else None,
                "llm_model_id": str(log.llm_model_id) if log.llm_model_id else None,
                "model_name": log.model_name,
                "model_provider": log.model_provider,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "total_tokens": log.input_tokens + log.output_tokens,
                "cost": float(log.cost),
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "period_days": days,
        "total_returned": len(logs),
    }


@router.get("/logs/{log_id}")
async def get_log_detail(
    log_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """로그 상세 — 해당 LLM 호출의 실제 대화 내용(사용자 입력 + 모델 응답)."""
    # 로그 조회
    log_result = await db.execute(
        select(TokenUsageLog).where(TokenUsageLog.id == log_id)
    )
    log = log_result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")

    messages = []
    if log.session_id:
        # 로그 생성 시각 직전~직후의 user + assistant 메시지를 찾음
        # assistant 응답: 로그 시각과 가장 가까운 assistant 메시지
        window_start = log.created_at - timedelta(seconds=30)
        window_end = log.created_at + timedelta(seconds=30)

        msg_query = (
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.session_id == log.session_id,
                    ChatMessage.created_at >= window_start,
                    ChatMessage.created_at <= window_end,
                    ChatMessage.role.in_(["user", "assistant"]),
                )
            )
            .order_by(ChatMessage.created_at.asc())
            .limit(4)
        )
        msg_result = await db.execute(msg_query)
        msgs = msg_result.scalars().all()

        # 시간 윈도우에 결과가 없으면 로그 시각 직전 마지막 user+assistant 2개를 가져옴
        if not msgs:
            fallback_query = (
                select(ChatMessage)
                .where(
                    and_(
                        ChatMessage.session_id == log.session_id,
                        ChatMessage.created_at <= log.created_at + timedelta(seconds=5),
                        ChatMessage.role.in_(["user", "assistant"]),
                    )
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(2)
            )
            fallback_result = await db.execute(fallback_query)
            msgs = list(reversed(fallback_result.scalars().all()))

        messages = [
            {
                "role": m.role,
                "content": m.content,
                "token_count": m.token_count,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ]

    return {
        "id": log.id,
        "input_tokens": log.input_tokens,
        "output_tokens": log.output_tokens,
        "total_tokens": log.input_tokens + log.output_tokens,
        "cost": float(log.cost),
        "created_at": log.created_at.isoformat(),
        "session_id": str(log.session_id) if log.session_id else None,
        "messages": messages,
    }
