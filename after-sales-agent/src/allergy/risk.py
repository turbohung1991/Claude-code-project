import json

from src.core.llm import LLMClient
from src.allergy.models import ALLERGY_RISK_PROMPT
from src.core.models import AllergyRiskResult


class SeverityAssessor:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def assess(self, ticket_id: str, reason: str, images: list[str]) -> AllergyRiskResult:
        user_message = f"用户描述：{reason}"
        if images:
            user_message += f"\n附图片 {len(images)} 张"

        response = self.llm.complete(
            system_prompt=ALLERGY_RISK_PROMPT,
            user_message=user_message,
            temperature=0.1,
            max_tokens=512,
        )
        data = json.loads(response)
        return AllergyRiskResult(ticket_id=ticket_id, **data)
