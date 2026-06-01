from src.knowledge.constraints import ComplianceConstraints


class AllergyCompliance:
    def __init__(self, constraints: ComplianceConstraints):
        self.constraints = constraints

    def requires_legal_review(self, reason: str) -> bool:
        for kw in self.constraints.COMPLIANCE_KEYWORDS:
            if kw in reason:
                return True
        return False

    def check_required_actions(self, severity: str, reason: str) -> list[str]:
        actions = []
        if self.requires_legal_review(reason):
            actions.append("USE_LEGAL_TEMPLATE")
        if severity in ("中度", "重度"):
            actions.append("NOTIFY_OPS_MANAGER")
        if severity == "重度":
            actions.append("HALT_BATCH_SHIPPING")
        return actions

    def get_legal_safe_template(self, severity: str) -> str:
        if severity == "重度":
            return (
                "看到您的反馈我们非常重视。"
                "建议您先暂停使用，并到皮肤科就诊确认情况。"
                "我们同步为您办理退货退款，有任何问题随时联系我们。"
            )
        return (
            "非常抱歉这个产品让您不舒服了。"
            "已为您办理退款，建议先停用观察。"
            "如果是敏感肌，我们可以为您推荐更温和的替代产品。"
        )
