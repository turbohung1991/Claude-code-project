from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from src.api.schemas import (
    TriageRequest, TriageResponse,
    AllergyRequest, AllergyResponse,
    RefundRequest, RefundResponse,
    ReplyRequest, ReplyResponse,
    HealthResponse,
)
from src.core.config import Settings, get_settings
from src.core.llm import LLMClient
from src.core.models import TicketInput
from src.core.exceptions import TriageConfidenceTooLow

router = APIRouter()


def get_llm(settings: Settings = Depends(get_settings)) -> LLMClient:
    return LLMClient(settings)


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version="0.1.0")


@router.post("/triage", response_model=TriageResponse)
async def triage_ticket(
    request: TriageRequest,
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm),
):
    from src.triage.classifier import TriageClassifier

    classifier = TriageClassifier(settings, llm)
    ticket = TicketInput(
        ticket_id=request.ticket_id,
        buyer_id=request.buyer_id,
        order_id=request.order_id,
        product_sku=request.product_sku,
        product_name=request.product_name,
        reason=request.reason,
        images=request.images,
        demand=request.demand,
        order_amount=request.order_amount,
        purchase_date=date.fromisoformat(request.purchase_date),
        platform=request.platform,
        historical_return_count=request.historical_return_count,
        yearly_spend=request.yearly_spend,
    )

    try:
        result = classifier.classify(ticket)
    except TriageConfidenceTooLow as e:
        raise HTTPException(status_code=422, detail=str(e))

    return TriageResponse(
        ticket_id=result.ticket_id,
        category=result.category,
        sub_category=result.sub_category,
        priority=result.priority,
        confidence=result.confidence,
        reasoning=result.reasoning,
        suggested_handler=result.suggested_handler,
        suggested_sla_minutes=result.suggested_sla_minutes,
    )


@router.post("/allergy/assess", response_model=AllergyResponse)
async def assess_allergy(
    request: AllergyRequest,
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm),
):
    from src.allergy.handler import AllergyHandler
    from src.allergy.batch_trace import BatchTracker
    from src.knowledge.retrieval import KnowledgeBase
    from src.knowledge.sku_store import SKUStore
    from src.knowledge.ingredient_store import IngredientStore
    from src.knowledge.rule_store import RuleStore
    from src.knowledge.case_store import CaseStore

    kb = KnowledgeBase(
        sku_store=SKUStore(),
        ingredient_store=IngredientStore(),
        rule_store=RuleStore(),
        case_store=CaseStore(),
    )
    tracker = BatchTracker(alert_threshold=settings.allergy_batch_alert_threshold)
    handler = AllergyHandler(llm, kb, tracker)

    result = handler.handle(
        ticket_id=request.ticket_id,
        product_sku=request.product_sku,
        reason=request.reason,
        images=request.images,
        batch_number=request.batch_number,
    )

    return AllergyResponse(
        ticket_id=result["ticket_id"],
        severity=result["severity"],
        symptoms_detected=result["symptoms_detected"],
        requires_legal_review=result["requires_legal_review"],
        requires_escalation=result["requires_escalation"],
        batch_alert=result.get("batch_alert"),
        reasoning=result["reasoning"],
    )


@router.post("/refund/decide", response_model=RefundResponse)
async def decide_refund(
    request: RefundRequest,
    settings: Settings = Depends(get_settings),
    llm: LLMClient = Depends(get_llm),
):
    from src.refund.engine import RefundEngine

    engine = RefundEngine(settings, llm)
    result = engine.decide(
        ticket_id=request.ticket_id,
        category=request.category,
        severity=request.severity,
        product_sku=request.product_sku,
        order_amount=request.order_amount,
        purchase_date=request.purchase_date,
        historical_return_count=request.historical_return_count,
        yearly_spend=request.yearly_spend,
    )

    return RefundResponse(
        ticket_id=result.ticket_id,
        refund_type=result.refund_type,
        refund_amount=result.refund_amount,
        compensation_type=result.compensation_type,
        compensation_amount=result.compensation_amount,
        compensation_scope=result.compensation_scope,
        compensation_valid_days=result.compensation_valid_days,
        reasoning=result.reasoning,
        confidence=result.confidence,
        requires_approval=result.requires_approval,
    )


@router.post("/reply/generate", response_model=ReplyResponse)
async def generate_reply(
    request: ReplyRequest,
    llm: LLMClient = Depends(get_llm),
):
    from src.reply.generator import ReplyGenerator

    generator = ReplyGenerator(llm)
    result = generator.generate(
        ticket_id=request.ticket_id,
        category=request.category,
        sub_category=request.sub_category,
        severity=request.severity,
        product_name=request.product_name,
        buyer_message=request.buyer_message,
        refund_decision=request.refund_decision,
    )

    return ReplyResponse(
        ticket_id=result["ticket_id"],
        reply_text=result["reply_text"],
        sentiment_detected=result["sentiment_detected"],
        quality_flags=result["quality_flags"],
        passed_hard_rules=result["passed_hard_rules"],
    )
