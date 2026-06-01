import json
from unittest.mock import Mock

from src.reply.generator import ReplyGenerator


class TestReplyGenerator:
    def test_generate_allergy_reply(self):
        mock_llm = Mock()
        mock_llm.complete.side_effect = [
            json.dumps({"sentiment": "失望", "urgency": "中", "tone_guidance": "加强关怀"}),
            "非常抱歉这个产品让您感到不适。已为您办理全额退款189元，同时为您准备了一张30元温和修复线专享券。",
        ]

        generator = ReplyGenerator(mock_llm)
        result = generator.generate(
            ticket_id="TK-001",
            category="不良反应",
            sub_category="泛红刺痛",
            severity="轻度",
            product_name="XX品牌精华液",
            buyer_message="用了两天脸上红了，之前用别家都没事",
            refund_decision={
                "refund_type": "全额退款",
                "refund_amount": 189,
                "compensation_type": "优惠券",
                "compensation_amount": 30,
                "compensation_scope": "温和修复类",
            },
        )

        assert result["ticket_id"] == "TK-001"
        assert "退款" in result["reply_text"]
        assert result["sentiment_detected"] == "失望"

    def test_generate_retry_on_violation(self):
        mock_llm = Mock()
        mock_llm.complete.side_effect = [
            json.dumps({"sentiment": "理性", "urgency": "低", "tone_guidance": "简洁"}),
            "这款产品效果很好，您再试试吧。已退款。",
            "好的，已为您办理退货退款169元。如果您需要，可以了解一下我们家其他产品。",
        ]

        generator = ReplyGenerator(mock_llm)
        result = generator.generate(
            ticket_id="TK-002",
            category="通用",
            sub_category="不想要",
            severity="",
            product_name="XX面霜",
            buyer_message="不想要了，退了吧",
            refund_decision={"refund_type": "全额退款", "refund_amount": 169},
        )

        assert result["passed_hard_rules"]
        assert mock_llm.complete.call_count == 3
