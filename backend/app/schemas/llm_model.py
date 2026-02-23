from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LLMModelCreate(BaseModel):
    provider: str
    model_id: str
    display_name: str
    input_cost_per_1m: float
    output_cost_per_1m: float
    max_context_length: int
    is_adult_only: bool = False
    tier: str = "economy"
    credit_per_1k_tokens: int = 1
    metadata: dict | None = None


class LLMModelUpdate(BaseModel):
    display_name: str | None = None
    input_cost_per_1m: float | None = None
    output_cost_per_1m: float | None = None
    max_context_length: int | None = None
    is_adult_only: bool | None = None
    is_active: bool | None = None
    tier: str | None = None
    credit_per_1k_tokens: int | None = None
    metadata: dict | None = None


class LLMModelResponse(BaseModel):
    id: UUID
    provider: str
    model_id: str
    display_name: str
    input_cost_per_1m: float
    output_cost_per_1m: float
    max_context_length: int
    is_adult_only: bool
    is_active: bool
    tier: str
    credit_per_1k_tokens: int
    created_at: datetime

    model_config = {"from_attributes": True}
