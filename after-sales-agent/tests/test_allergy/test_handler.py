import json
from unittest.mock import Mock

from src.allergy.risk import SeverityAssessor
from src.allergy.compliance import AllergyCompliance
from src.allergy.handler import AllergyHandler
from src.allergy.batch_trace import BatchTracker
from src.knowledge.constraints import ComplianceConstraints


class TestSeverityAssessor:
    def test_assess_mild_reaction(self):
        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps({
            "severity": "轻度",
            "symptoms_detected": ["局部泛红", "轻微刺痛"],
            "requires_legal_review": False,
            "requires_escalation": False,
            "reasoning": "仅有局部泛红，无其他严重症状",
        })

        assessor = SeverityAssessor(mock_llm)
        result = assessor.assess("TK-001", "用了之后脸颊有点红，不严重", [])
        assert result.severity == "轻度"
        assert not result.requires_legal_review


class TestAllergyCompliance:
    def test_detects_severe_keywords(self):
        compliance = AllergyCompliance(ComplianceConstraints())
        assert compliance.requires_legal_review("脸部眼部肿胀，还化脓了")

    def test_no_false_positive(self):
        compliance = AllergyCompliance(ComplianceConstraints())
        assert not compliance.requires_legal_review("用了以后有点红")

    def test_severe_requires_all_actions(self):
        compliance = AllergyCompliance(ComplianceConstraints())
        actions = compliance.check_required_actions("重度", "大面积溃烂")
        assert "USE_LEGAL_TEMPLATE" in actions
        assert "HALT_BATCH_SHIPPING" in actions
        assert "NOTIFY_OPS_MANAGER" in actions


class TestAllergyHandler:
    def test_handle_mild_allergy(self):
        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps({
            "severity": "轻度",
            "symptoms_detected": ["泛红"],
            "requires_legal_review": False,
            "requires_escalation": False,
            "reasoning": "仅泛红",
        })

        mock_kb = Mock()
        mock_kb.get_product_context.return_value = {
            "sku": "LP-001", "name": "洁面乳", "brand": "Test",
            "skin_types": ["敏感肌"], "key_ingredients": ["烟酰胺"],
            "texture": "乳液", "scent": "无香", "common_complaints": [],
            "related_skus": [], "found": True,
        }
        mock_kb.get_allergen_analysis.return_value = {
            "suspected_allergens": [],
            "safe_alternatives": [],
        }

        tracker = BatchTracker()
        handler = AllergyHandler(mock_llm, mock_kb, tracker)

        result = handler.handle(
            ticket_id="TK-001",
            product_sku="LP-001",
            reason="用了有点红",
            images=[],
            batch_number="LP202605",
        )

        assert result["severity"] == "轻度"
        assert not result["requires_legal_review"]
        assert len(result["symptoms_detected"]) == 1
