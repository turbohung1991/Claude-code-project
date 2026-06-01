from typing import Optional

from pydantic import BaseModel, Field


class TriageRequest(BaseModel):
    ticket_id: str
    buyer_id: str
    order_id: str
    product_sku: str
    product_name: str
    reason: str
    images: list[str] = Field(default_factory=list)
    demand: str
    order_amount: float
    purchase_date: str
    platform: str
    historical_return_count: int = 0
    yearly_spend: float = 0


class TriageResponse(BaseModel):
    ticket_id: str
    category: str
    sub_category: str
    priority: str
    confidence: float
    reasoning: str
    suggested_handler: str
    suggested_sla_minutes: int


class AllergyRequest(BaseModel):
    ticket_id: str
    product_sku: str
    reason: str
    images: list[str] = Field(default_factory=list)
    batch_number: Optional[str] = None


class AllergyResponse(BaseModel):
    ticket_id: str
    severity: str
    symptoms_detected: list[str]
    requires_legal_review: bool
    requires_escalation: bool
    batch_alert: Optional[dict]
    reasoning: str


class RefundRequest(BaseModel):
    ticket_id: str
    category: str
    severity: str
    product_sku: str
    order_amount: float
    purchase_date: str
    buyer_id: str
    historical_return_count: int
    yearly_spend: float


class RefundResponse(BaseModel):
    ticket_id: str
    refund_type: str
    refund_amount: float
    compensation_type: str
    compensation_amount: float
    compensation_scope: str
    compensation_valid_days: int
    reasoning: str
    confidence: float
    requires_approval: bool


class ReplyRequest(BaseModel):
    ticket_id: str
    category: str
    sub_category: str
    severity: str
    product_sku: str
    product_name: str
    buyer_message: str
    refund_decision: Optional[dict] = None


class ReplyResponse(BaseModel):
    ticket_id: str
    reply_text: str
    sentiment_detected: str
    quality_flags: list[str]
    passed_hard_rules: bool


class HealthResponse(BaseModel):
    status: str
    version: str
