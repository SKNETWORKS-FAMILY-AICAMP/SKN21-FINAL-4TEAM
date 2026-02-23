from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReportReason(str, Enum):
    inappropriate = "inappropriate"
    sexual = "sexual"
    harassment = "harassment"
    copyright = "copyright"
    spam = "spam"
    other = "other"


class ReportCreate(BaseModel):
    reason: ReportReason
    description: str | None = Field(default=None, max_length=1000)


class ReportResponse(BaseModel):
    id: int
    persona_id: str
    persona_name: str | None = None
    reporter_id: str
    reporter_nickname: str | None = None
    reason: str
    description: str | None
    status: str
    admin_note: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int


class ReportStatsResponse(BaseModel):
    pending: int
    reviewed: int
    dismissed: int
    total: int


class ReportActionType(str, Enum):
    dismiss = "dismiss"
    takedown = "takedown"
    ban_creator = "ban_creator"


class ReportAdminAction(BaseModel):
    action: ReportActionType
    admin_note: str | None = Field(default=None, max_length=1000)
    ban_days: int | None = Field(default=None, ge=1, le=3650, description="밴 기간(일). None이면 영구밴.")
