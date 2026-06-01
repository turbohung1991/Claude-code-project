import json

from src.core.llm import LLMClient

SENTIMENT_PROMPT = """分析用户消息的情绪，输出 JSON（只输出 JSON）：
{
  "sentiment": "愤怒|焦虑|失望|理性|困惑",
  "urgency": "高|中|低",
  "tone_guidance": "如何回应的建议"
}"""


class SentimentDetector:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def detect(self, message: str) -> dict:
        response = self.llm.complete(
            system_prompt=SENTIMENT_PROMPT,
            user_message=message,
            temperature=0.1,
            max_tokens=256,
        )
        return json.loads(response)

    def get_tone_adjustment(self, sentiment: str) -> dict:
        adjustments = {
            "愤怒": {"urgency_boost": True, "apology_first": True, "be_concise": True},
            "焦虑": {"provide_timeline": True, "reduce_uncertainty": True},
            "失望": {"extra_care": True, "highlight_solution": True},
            "理性": {"be_concise": True, "focus_on_solution": True},
            "困惑": {"clarify_step_by_step": True, "avoid_jargon": True},
        }
        return adjustments.get(sentiment, {})
