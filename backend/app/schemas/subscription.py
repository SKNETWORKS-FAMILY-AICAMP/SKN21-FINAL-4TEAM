from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PlanResponse(BaseModel):
    id: UUID
    plan_key: str
    display_name: str
    price_krw: int
    daily_credits: int
    credit_rollover_days: int
    max_lounge_personas: int
    max_agent_actions: int
    features: dict | None = None

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    id: UUID
    plan: PlanResponse
    status: str
    started_at: datetime
    expires_at: datetime | None = None
    cancelled_at: datetime | None = None

    model_config = {"from_attributes": True}


class SubscribeRequest(BaseModel):
    plan_key: str


class AdminSubscriptionSummary(BaseModel):
    total_subscribers: int
    active_subscribers: int
    monthly_revenue_krw: int
    plan_breakdown: list[dict]
