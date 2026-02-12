from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UsageSummary(BaseModel):
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    daily_input_tokens: int
    daily_output_tokens: int
    daily_cost: float
    monthly_input_tokens: int
    monthly_output_tokens: int
    monthly_cost: float


class UsageHistoryItem(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    cost: float
    model_name: str | None = None


class TokenUsageLogResponse(BaseModel):
    id: int
    user_id: UUID
    session_id: UUID | None
    llm_model_id: UUID
    input_tokens: int
    output_tokens: int
    cost: float
    created_at: datetime

    model_config = {"from_attributes": True}
