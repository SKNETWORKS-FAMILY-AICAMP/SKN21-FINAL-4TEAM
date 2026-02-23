from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ModelUsage(BaseModel):
    model_name: str
    provider: str
    tier: str = "economy"
    credit_per_1k_tokens: int = 1
    input_cost_per_1m: float
    output_cost_per_1m: float
    input_tokens: int
    output_tokens: int
    cost: float
    request_count: int
    daily_input_tokens: int = 0
    daily_output_tokens: int = 0
    daily_cost: float = 0.0
    daily_request_count: int = 0
    monthly_input_tokens: int = 0
    monthly_output_tokens: int = 0
    monthly_cost: float = 0.0
    monthly_request_count: int = 0


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
    by_model: list[ModelUsage] = []


class UsageHistoryItem(BaseModel):
    date: str
    input_tokens: int
    output_tokens: int
    cost: float


class ModelDailyUsage(BaseModel):
    date: str
    model_name: str
    input_tokens: int
    output_tokens: int
    cost: float


class UsageHistoryResponse(BaseModel):
    daily: list[UsageHistoryItem]
    by_model_daily: list[ModelDailyUsage]


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
