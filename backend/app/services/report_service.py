import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona
from app.models.persona_report import PersonaReport
from app.models.user import User
from app.schemas.report import ReportCreate


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_report(
        self,
        persona_id: uuid.UUID,
        reporter_id: uuid.UUID,
        data: ReportCreate,
    ) -> PersonaReport:
        """페르소나 신고 생성. 자기 페르소나 신고 불가, 중복 신고 불가."""
        # 페르소나 존재 확인
        result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        persona = result.scalar_one_or_none()
        if persona is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

        # 자기 페르소나 신고 불가
        if persona.created_by == reporter_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot report your own persona",
            )

        # 중복 신고 확인
        existing = await self.db.execute(
            select(PersonaReport).where(
                PersonaReport.persona_id == persona_id,
                PersonaReport.reporter_id == reporter_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Already reported this persona",
            )

        report = PersonaReport(
            persona_id=persona_id,
            reporter_id=reporter_id,
            reason=data.reason.value,
            description=data.description,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def list_reports(
        self,
        status_filter: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """관리자용 신고 목록 조회. persona/reporter JOIN으로 이름/닉네임 포함."""
        reporter = User.__table__.alias("reporter")

        query = (
            select(
                PersonaReport,
                Persona.display_name.label("persona_name"),
                reporter.c.nickname.label("reporter_nickname"),
            )
            .join(Persona, PersonaReport.persona_id == Persona.id)
            .join(reporter, PersonaReport.reporter_id == reporter.c.id)
        )

        count_query = select(func.count()).select_from(PersonaReport)

        if status_filter:
            query = query.where(PersonaReport.status == status_filter)
            count_query = count_query.where(PersonaReport.status == status_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(PersonaReport.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        rows = result.all()

        items = []
        for report, persona_name, reporter_nickname in rows:
            items.append({
                "id": report.id,
                "persona_id": str(report.persona_id),
                "persona_name": persona_name,
                "reporter_id": str(report.reporter_id),
                "reporter_nickname": reporter_nickname,
                "reason": report.reason,
                "description": report.description,
                "status": report.status,
                "admin_note": report.admin_note,
                "reviewed_by": str(report.reviewed_by) if report.reviewed_by else None,
                "reviewed_at": report.reviewed_at,
                "created_at": report.created_at,
            })

        return {"items": items, "total": total}

    async def get_stats(self) -> dict:
        """신고 통계 (상태별 건수)."""
        result = await self.db.execute(
            select(PersonaReport.status, func.count()).group_by(PersonaReport.status)
        )
        counts = {row[0]: row[1] for row in result.all()}
        pending = counts.get("pending", 0)
        reviewed = counts.get("reviewed", 0)
        dismissed = counts.get("dismissed", 0)
        return {
            "pending": pending,
            "reviewed": reviewed,
            "dismissed": dismissed,
            "total": pending + reviewed + dismissed,
        }

    async def review_report(
        self,
        report_id: int,
        action: str,
        admin_id: uuid.UUID,
        note: str | None = None,
        ban_days: int | None = None,
    ) -> PersonaReport:
        """신고 처리. dismiss/takedown/ban_creator. ban_days=None이면 영구밴."""
        result = await self.db.execute(
            select(PersonaReport).where(PersonaReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

        if report.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Report already processed",
            )

        now = datetime.now(timezone.utc)

        if action == "dismiss":
            report.status = "dismissed"
        elif action == "takedown":
            report.status = "reviewed"
            # 해당 페르소나 차단
            await self.db.execute(
                update(Persona)
                .where(Persona.id == report.persona_id)
                .values(moderation_status="blocked")
            )
        elif action == "ban_creator":
            report.status = "reviewed"
            # 해당 페르소나의 생성자 조회
            persona_result = await self.db.execute(
                select(Persona.created_by).where(Persona.id == report.persona_id)
            )
            creator_id = persona_result.scalar_one_or_none()
            if creator_id:
                # 해당 생성자의 모든 공개 페르소나 차단
                await self.db.execute(
                    update(Persona)
                    .where(
                        Persona.created_by == creator_id,
                        Persona.visibility == "public",
                    )
                    .values(moderation_status="blocked")
                )
                # 기간 밴 설정: ban_days=None이면 영구밴 (9999일)
                if ban_days is not None:
                    banned_until = now + timedelta(days=ban_days)
                else:
                    banned_until = now + timedelta(days=9999)
                await self.db.execute(
                    update(User)
                    .where(User.id == creator_id)
                    .values(banned_until=banned_until)
                )

        report.admin_note = note
        report.reviewed_by = admin_id
        report.reviewed_at = now

        await self.db.commit()
        await self.db.refresh(report)
        return report
