from typing import Optional
from src.core.llm import LLMClient
from src.reply.templates import TemplateStore
from src.reply.sentiment import SentimentDetector
from src.reply.quality import QualityChecker
from src.reply.models import REPLY_GENERATION_PROMPT


class ReplyGenerator:
    def __init__(self, llm: LLMClient):
        self.llm = llm
        self.templates = TemplateStore()
        self.sentiment = SentimentDetector(llm)
        self.quality = QualityChecker()

    def generate(
        self,
        ticket_id: str,
        category: str,
        sub_category: str,
        severity: str,
        product_name: str,
        buyer_message: str,
        refund_decision: Optional[dict] = None,
    ) -> dict:
        sentiment_result = self.sentiment.detect(buyer_message)
        tone = self.sentiment.get_tone_adjustment(sentiment_result["sentiment"])

        template = self.templates.match(category, severity, is_first=True)
        if not template:
            template = self.templates.get("通用")

        context = self._build_context(
            ticket_id, category, sub_category, severity,
            product_name, refund_decision, tone,
        )

        raw_reply = self.llm.complete(
            system_prompt=REPLY_GENERATION_PROMPT,
            user_message=f"模板：{template['骨架']}\n上下文：{context}\n用户消息：{buyer_message}",
            temperature=0.3,
            max_tokens=512,
        )

        quality_result = self.quality.check(raw_reply, refund_decision)

        if not quality_result["passed"]:
            raw_reply = self._retry_with_violations(
                raw_reply, quality_result["hard_violations"],
                template, context, buyer_message,
            )
            quality_result = self.quality.check(raw_reply, refund_decision)

        return {
            "ticket_id": ticket_id,
            "reply_text": raw_reply.strip(),
            "sentiment_detected": sentiment_result["sentiment"],
            "quality_flags": quality_result["soft_flags"],
            "passed_hard_rules": quality_result["passed"],
        }

    def _build_context(self, ticket_id, category, sub_category, severity, product_name, refund, tone):
        parts = [
            f"工单号：{ticket_id}",
            f"问题：{category}-{sub_category}-{severity}",
            f"产品：{product_name}",
        ]
        if refund:
            parts.append(f"退款方案：{refund.get('refund_type')} {refund.get('refund_amount')}元")
            comp = refund.get('compensation_amount', 0)
            if comp > 0:
                parts.append(f"补偿：{comp}元{refund.get('compensation_type')}")
        if tone.get("urgency_boost"):
            parts.append("注意：用户情绪激动，优先道歉，缩短篇幅")
        if tone.get("provide_timeline"):
            parts.append("注意：主动告知处理时间节点")
        if tone.get("extra_care"):
            parts.append("注意：加强关怀语气")
        return "\n".join(parts)

    def _retry_with_violations(self, reply, violations, template, context, user_msg):
        return self.llm.complete(
            system_prompt=REPLY_GENERATION_PROMPT,
            user_message=(
                f"模板：{template['骨架']}\n上下文：{context}\n"
                f"上次回复违反规则：{violations}\n请修正后重新生成。\n用户消息：{user_msg}"
            ),
            temperature=0.2,
            max_tokens=512,
        )
