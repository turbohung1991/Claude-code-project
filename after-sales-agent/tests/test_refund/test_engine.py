import json
from datetime import date, timedelta
from unittest.mock import Mock

from src.refund.rules import RefundRules
from src.refund.engine import RefundEngine


class TestRefundRules:
    def test_recent_allergy_gets_full_refund(self, test_settings):
        rules = RefundRules(test_settings)
        result = rules.evaluate(
            category="不良反应",
            purchase_date=date.today() - timedelta(days=2),
            historical_return_count=0,
            yearly_spend=1000,
        )
        assert result["max_refund_pct"] == 1.0
        assert result["max_compensation"] >= 30

    def test_fraud_risk_limits_refund(self, test_settings):
        rules = RefundRules(test_settings)
        result = rules.evaluate(
            category="不良反应",
            purchase_date=date.today() - timedelta(days=1),
            historical_return_count=3,
            yearly_spend=1000,
        )
        assert result["max_refund_pct"] <= 0.5
        assert result["requires_approval"]

    def test_old_purchase_gets_partial(self, test_settings):
        rules = RefundRules(test_settings)
        result = rules.evaluate(
            category="产品体验",
            purchase_date=date.today() - timedelta(days=90),
            historical_return_count=0,
            yearly_spend=1000,
        )
        assert result["max_refund_pct"] <= 0.3

    def test_vip_gets_higher_compensation(self, test_settings):
        rules = RefundRules(test_settings)
        regular = rules.evaluate(
            category="不良反应",
            purchase_date=date.today() - timedelta(days=2),
            historical_return_count=0,
            yearly_spend=1000,
        )
        vip = rules.evaluate(
            category="不良反应",
            purchase_date=date.today() - timedelta(days=2),
            historical_return_count=0,
            yearly_spend=6000,
        )
        assert vip["max_compensation"] > regular["max_compensation"]


class TestRefundEngine:
    def test_decide_allergy_mild_full_refund(self, test_settings):
        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps({
            "refund_type": "全额退款",
            "refund_amount": 189,
            "compensation_type": "优惠券",
            "compensation_amount": 30,
            "compensation_scope": "温和修复类产品",
            "compensation_valid_days": 30,
            "reasoning": "首次过敏轻度，全额退+温和产品券",
            "confidence": 0.9,
            "requires_approval": False,
        })

        engine = RefundEngine(test_settings, mock_llm)
        result = engine.decide(
            ticket_id="TK-001",
            category="不良反应",
            severity="轻度",
            product_sku="LP-001",
            order_amount=189,
            purchase_date=(date.today() - timedelta(days=2)).isoformat(),
            historical_return_count=0,
            yearly_spend=1000,
        )
        assert result.refund_type == "全额退款"
        assert result.refund_amount == 189
        assert result.compensation_amount == 30

    def test_fraud_risk_bypasses_llm(self, test_settings):
        mock_llm = Mock()
        engine = RefundEngine(test_settings, mock_llm)

        result = engine.decide(
            ticket_id="TK-002",
            category="不良反应",
            severity="轻度",
            product_sku="LP-001",
            order_amount=189,
            purchase_date=date.today().isoformat(),
            historical_return_count=5,
            yearly_spend=500,
        )
        assert result.requires_approval
        mock_llm.complete.assert_not_called()
