from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class Category(StrEnum):
    ADVERSE_REACTION = "不良反应"
    PRODUCT_EXPERIENCE = "产品体验"
    LOGISTICS = "物流包装"
    ORDER_ISSUE = "订单问题"
    GENERAL = "通用"


class SubCategory(StrEnum):
    REDNESS_STING = "泛红刺痛"
    ACNE_BREAKOUT = "爆痘"
    PEELING = "脱皮"
    ITCHING = "瘙痒"
    TEXTURE_WRONG = "质地不对"
    SMELL_WRONG = "气味不对"
    PILLING = "搓泥"
    NO_EFFECT = "效果不符"
    DAMAGED = "破损漏液"
    WRONG_ITEM = "错发漏发"
    NEAR_EXPIRY = "临期品"
    PACKAGING = "包装问题"
    NOT_RECEIVED = "未收到货"
    DUPLICATE_CHARGE = "重复扣款"
    COUPON = "优惠券问题"
    DONT_WANT = "不想要"
    WRONG_ORDER = "拍错"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class Severity(StrEnum):
    MILD = "轻度"
    MODERATE = "中度"
    SEVERE = "重度"


class TicketInput(BaseModel):
    ticket_id: str
    buyer_id: str
    order_id: str
    product_sku: str
    product_name: str
    reason: str
    images: list[str] = Field(default_factory=list)
    demand: str
    order_amount: float
    purchase_date: date
    platform: str
    historical_return_count: int = 0
    yearly_spend: float = 0


class TriageResult(BaseModel):
    ticket_id: str
    category: Category
    sub_category: SubCategory
    priority: Priority
    confidence: float
    reasoning: str
    suggested_handler: str
    suggested_sla_minutes: int


class AllergyRiskResult(BaseModel):
    ticket_id: str
    severity: Severity
    symptoms_detected: list[str]
    requires_legal_review: bool
    requires_escalation: bool
    reasoning: str


class BatchAlert(BaseModel):
    batch_number: str
    allergy_rate_7d: float
    total_orders: int
    allergy_cases: int
    should_alert: bool


class RefundDecision(BaseModel):
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


class ReplyOutput(BaseModel):
    ticket_id: str
    reply_text: str
    sentiment_detected: str
    quality_flags: list[str]
    passed_hard_rules: bool
