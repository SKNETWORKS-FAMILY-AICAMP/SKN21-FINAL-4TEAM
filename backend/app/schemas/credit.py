from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreditBalanceResponse(BaseModel):
    balance: int
    daily_credits: int
    granted_today: bool
    plan_key: str

    model_config = {"from_attributes": True}


class CreditHistoryItem(BaseModel):
    id: int
    amount: int
    balance_after: int
    tx_type: str
    reference_id: str | None = None
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditCostItem(BaseModel):
    action: str
    model_tier: str
    cost: int

    model_config = {"from_attributes": True}


class CreditPurchaseRequest(BaseModel):
    package: str = Field(description="'small'(500석), 'medium'(3000석), 'large'(10000석)")


class CreditPurchaseResponse(BaseModel):
    credits_added: int
    price_krw: int
    new_balance: int


class AdminCreditGrantRequest(BaseModel):
    user_id: UUID
    amount: int = Field(gt=0, le=100000)
    description: str | None = None


class AdminCreditSummary(BaseModel):
    total_credits_granted: int
    total_credits_spent: int
    total_credits_purchased: int
    active_users_today: int
