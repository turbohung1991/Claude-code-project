from typing import Optional
TEMPLATES = {
    "不良反应-轻度-首次": {
        "骨架": (
            "非常抱歉这个产品让您感到不适。{refund_action}。"
            "如果您的皮肤比较敏感，我们推荐尝试 {alternative_product}，"
            "它更加温和，专为敏感肌设计。{coupon_note}"
        ),
        "约束": ["不含医疗诊断", "不含功效承诺"],
    },
    "不良反应-中重度": {
        "骨架": (
            "看到您的反馈我们非常重视。{medical_advice}。"
            "我们同步{refund_action}。"
            "后续有任何问题随时联系我们，我们会全程跟进。"
        ),
        "约束": ["必须包含就医建议", "操作确认", "升级通知"],
    },
    "物流包装-破损漏液": {
        "骨架": (
            "非常抱歉！物流过程中出现了这样的问题。"
            "{resend_action}。破损的无需寄回。"
            "预计 {delivery_time} 内发出，单号出来后第一时间通知您。"
        ),
        "约束": ["补发/退款确认", "时间承诺"],
    },
    "物流包装-错发漏发": {
        "骨架": (
            "很抱歉给您发错了！已经为您安排{corrective_action}。"
            "错误的商品无需寄回，您留着用或者送给朋友都可以。"
        ),
        "约束": ["补发确认"],
    },
    "产品体验": {
        "骨架": (
            "感谢您的反馈！{explanation}。"
            "当然如果您确实不适应，{return_policy}。"
            "{alternative_suggestion}"
        ),
        "约束": ["解释差异化", "开放退货", "不可贬低竞品"],
    },
    "通用": {
        "骨架": (
            "好的，已为您{action}。{additional_help}"
        ),
        "约束": ["操作确认"],
    },
}


class TemplateStore:
    def get(self, scenario: str) -> Optional[dict]:
        return TEMPLATES.get(scenario)

    def match(self, category: str, severity: str, is_first: bool) -> Optional[dict]:
        key = f"{category}-{severity}-{'首次' if is_first else '多次'}"
        return (
            self.get(key)
            or self.get(f"{category}-{severity}")
            or self.get(category)
            or self.get("通用")
        )
