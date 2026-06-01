from typing import Optional
from datetime import date

from src.core.llm import LLMClient
from src.knowledge.retrieval import KnowledgeBase
from src.allergy.risk import SeverityAssessor
from src.allergy.compliance import AllergyCompliance
from src.allergy.batch_trace import BatchTracker
from src.knowledge.constraints import ComplianceConstraints


class AllergyHandler:
    def __init__(
        self,
        llm: LLMClient,
        kb: KnowledgeBase,
        batch_tracker: BatchTracker,
    ):
        self.assessor = SeverityAssessor(llm)
        self.compliance = AllergyCompliance(ComplianceConstraints())
        self.kb = kb
        self.batch_tracker = batch_tracker

    def handle(
        self,
        ticket_id: str,
        product_sku: str,
        reason: str,
        images: list[str],
        batch_number: Optional[str] = None,
    ) -> dict:
        risk = self.assessor.assess(ticket_id, reason, images)
        actions = self.compliance.check_required_actions(risk.severity, reason)

        product = self.kb.get_product_context(product_sku)
        allergens = {}
        if product.get("found"):
            allergens = self.kb.get_allergen_analysis(
                product["key_ingredients"], risk.symptoms_detected
            )

        batch_alert = None
        if batch_number:
            self.batch_tracker.record(batch_number, ticket_id, date.today())
            batch_alert = self.batch_tracker.check_alert(batch_number)

        follow_up_days = [7] if risk.severity == "轻度" else [7, 14]

        return {
            "ticket_id": ticket_id,
            "severity": risk.severity,
            "symptoms_detected": risk.symptoms_detected,
            "requires_legal_review": risk.requires_legal_review,
            "requires_escalation": risk.requires_escalation,
            "reasoning": risk.reasoning,
            "required_actions": actions,
            "legal_template": self.compliance.get_legal_safe_template(risk.severity)
            if risk.requires_legal_review else None,
            "product_context": product,
            "allergen_analysis": allergens,
            "batch_alert": batch_alert,
            "follow_up_days": follow_up_days,
        }
