import json
from unittest.mock import Mock

from src.triage.classifier import TriageClassifier
from src.core.models import TicketInput
from src.core.exceptions import TriageConfidenceTooLow


class TestTriageClassifier:
    def test_classify_allergy_redness(self, test_settings):
        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps({
            "category": "不良反应",
            "sub_category": "泛红刺痛",
            "priority": "P0",
            "confidence": 0.94,
            "reasoning": "用户描述泛红起小疙瘩，符合过敏初发特征",
            "suggested_handler": "过敏专组",
            "suggested_sla_minutes": 30,
        })

        classifier = TriageClassifier(test_settings, mock_llm)
        ticket = TicketInput(
            ticket_id="TK-001", buyer_id="U1", order_id="O1",
            product_sku="LP-001", product_name="洁面乳",
            reason="用了两次脸上泛红起小疙瘩", demand="退货退款",
            order_amount=189, purchase_date="2026-05-15",
            platform="淘宝", historical_return_count=0,
        )

        result = classifier.classify(ticket)
        assert result.category == "不良反应"
        assert result.priority == "P0"
        assert result.confidence == 0.94

    def test_low_confidence_raises(self, test_settings):
        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps({
            "category": "通用",
            "sub_category": "不想要",
            "priority": "P2",
            "confidence": 0.55,
            "reasoning": "不确定",
            "suggested_handler": "普通客服",
            "suggested_sla_minutes": 480,
        })

        classifier = TriageClassifier(test_settings, mock_llm)
        ticket = TicketInput(
            ticket_id="TK-002", buyer_id="U2", order_id="O2",
            product_sku="LP-001", product_name="洁面乳",
            reason="不太确定要不要退", demand="退货",
            order_amount=189, purchase_date="2026-05-15",
            platform="淘宝", historical_return_count=0,
        )

        try:
            classifier.classify(ticket)
            assert False, "应该抛出异常"
        except TriageConfidenceTooLow:
            pass
