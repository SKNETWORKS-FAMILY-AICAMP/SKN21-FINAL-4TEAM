from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.schemas.report import (
    ReportAdminAction,
    ReportListResponse,
    ReportStatsResponse,
)
from app.services.report_service import ReportService

router = APIRouter()


@router.get("", response_model=ReportListResponse)
async def list_reports(
    status: str | None = Query(None, pattern="^(pending|reviewed|dismissed)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """신고 목록 조회 (관리자)."""
    service = ReportService(db)
    return await service.list_reports(status_filter=status, skip=skip, limit=limit)


@router.get("/stats", response_model=ReportStatsResponse)
async def report_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """신고 통계 (관리자)."""
    service = ReportService(db)
    return await service.get_stats()


@router.put("/{report_id}/action")
async def action_report(
    report_id: int,
    data: ReportAdminAction,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """신고 처리 — dismiss/takedown/ban_creator (관리자)."""
    service = ReportService(db)
    report = await service.review_report(
        report_id=report_id,
        action=data.action.value,
        admin_id=admin.id,
        note=data.admin_note,
        ban_days=data.ban_days,
    )
    return {"id": report.id, "status": report.status}
