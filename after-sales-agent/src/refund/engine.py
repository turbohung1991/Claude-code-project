import json
from datetime import date

from src.core.llm import LLMClient
from src.core.config import Settings
from src.refund.rules import RefundRules
from src.refund.models import REFUND_DECISION_PROMPT
from src.core.models import RefundDecision


class RefundEngine:
    def __init__(self, settings: Settings, llm: LLMClient):
        self.rules = RefundRules(settings)
        self.llm = llm
        self.settings = settings

    def decide(
        self,
        ticket_id: str,
        category: str,
        severity: str,
        product_sku: str,
        order_amount: float,
        purchase_date: str,
        historical_return_count: int,
        yearly_spend: float,
    ) -> RefundDecision:
        purchase = date.fromisoformat(purchase_date) if isinstance(purchase_date, str) else purchase_date

        rule_result = self.rules.evaluate(
            category, purchase, historical_return_count, yearly_spend
        )

        max_refund = round(order_amount * rule_result["max_refund_pct"], 2)
        max_compensation = round(rule_result["max_compensation"], 2)

        if rule_result["requires_approval"] or rule_result["is_fraud_risk"]:
            return RefundDecision(
                ticket_id=ticket_id,
                refund_type="部分退款" if max_refund > 0 else "不退款",
                refund_amount=max_refund,
                compensation_type="无",
                compensation_amount=0,
                compensation_scope="",
                compensation_valid_days=0,
                reasoning="命中风控规则，需人工审核",
                confidence=1.0,
                requires_approval=True,
            )

        user_message = f"""工单：{ticket_id}
问题类别：{category}，严重度：{severity}
订单金额：{order_amount}元
最大退款：{max_refund}元，最大补偿金：{max_compensation}元
用户年消费：{yearly_spend}元（{'VIP' if rule_result['is_vip'] else '普通'}）
距购买：{rule_result['days_since_purchase']}天"""

        response = self.llm.complete(
            system_prompt=REFUND_DECISION_PROMPT,
            user_message=user_message,
            temperature=0.2,
            max_tokens=512,
        )
        data = json.loads(response)
        data["refund_amount"] = min(data.get("refund_amount", 0), max_refund)
        data["compensation_amount"] = min(data.get("compensation_amount", 0), max_compensation)
        return RefundDecision(ticket_id=ticket_id, **data)
