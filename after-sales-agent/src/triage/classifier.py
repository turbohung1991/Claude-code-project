import json

from src.core.config import Settings
from src.core.llm import LLMClient
from src.core.models import TicketInput, TriageResult
from src.core.exceptions import TriageConfidenceTooLow
from src.triage.models import TRIAGE_SYSTEM_PROMPT


class TriageClassifier:
    def __init__(self, settings: Settings, llm: LLMClient):
        self.settings = settings
        self.llm = llm

    def classify(self, ticket: TicketInput) -> TriageResult:
        user_message = self._format_ticket(ticket)
        response = self.llm.complete(
            system_prompt=TRIAGE_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.1,
            max_tokens=512,
        )
        data = json.loads(response)
        data["ticket_id"] = ticket.ticket_id
        result = TriageResult(**data)

        # 硬规则：不良反应类 + 无图 → 强制要求上传凭证（不信任 LLM 判断）
        if "不良反应" in result.category:
            result.requires_images = not ticket.images
            if result.requires_images:
                result.reasoning += "（无实拍图/视频，已标记需上传凭证）"

        if result.confidence < self.settings.triage_confidence_threshold:
            raise TriageConfidenceTooLow(
                f"分类置信度 {result.confidence} 低于阈值 {self.settings.triage_confidence_threshold}"
            )

        if result.priority == "P0":
            result.suggested_sla_minutes = 30
        elif result.priority == "P1":
            result.suggested_sla_minutes = 120
        else:
            result.suggested_sla_minutes = 480

        return result

    def _format_ticket(self, ticket: TicketInput) -> str:
        image_count = len(ticket.images)
        image_info = f"已上传 {image_count} 张图片" if image_count > 0 else "未上传图片/视频"
        return f"""请分类以下售后工单：

买家ID：{ticket.buyer_id}
订单号：{ticket.order_id}
商品：{ticket.product_name}
原因：{ticket.reason}
诉求：{ticket.demand}
金额：{ticket.order_amount}元
购买日期：{ticket.purchase_date}
历史售后次数：{ticket.historical_return_count}
平台：{ticket.platform}
图片凭证：{image_info}"""
