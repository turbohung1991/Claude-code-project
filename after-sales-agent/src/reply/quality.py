from typing import Optional
from src.knowledge.constraints import ComplianceConstraints


class QualityChecker:
    def __init__(self):
        self.compliance = ComplianceConstraints()

    def check(self, reply: str, refund_decision: Optional[dict] = None) -> dict:
        hard_violations = []
        soft_flags = []

        # 硬规则
        medical_terms = ["诊断", "处方", "治疗", "用药"]
        for term in medical_terms:
            if term in reply:
                hard_violations.append(f"包含医疗术语'{term}'")

        if "效果" in reply or "功效" in reply:
            hard_violations.append("包含效果/功效承诺")

        if refund_decision:
            refund_amount = refund_decision.get("refund_amount")
            if refund_amount and str(refund_amount) not in reply and "退款" in reply:
                hard_violations.append(f"回复未包含退款金额 {refund_amount}")

        action_keywords = ["已为您", "为您办理", "已处理", "已安排"]
        if not any(kw in reply for kw in action_keywords):
            hard_violations.append("缺少操作确认语句")

        # 合规红线
        compliance_violations = self.compliance.check_text(reply)
        hard_violations.extend(compliance_violations)

        # 软规则
        if len(reply) > 200:
            soft_flags.append(f"回复过长 ({len(reply)} 字)")

        return {
            "passed": len(hard_violations) == 0,
            "hard_violations": hard_violations,
            "soft_flags": soft_flags,
        }
