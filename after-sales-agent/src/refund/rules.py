from datetime import date, timedelta

from src.core.config import Settings


class RefundRules:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(
        self,
        category: str,
        purchase_date: date,
        historical_return_count: int,
        yearly_spend: float,
    ) -> dict:
        days_since_purchase = (date.today() - purchase_date).days

        if days_since_purchase <= self.settings.refund_window_full_days:
            max_refund_pct = 1.0
        elif days_since_purchase <= self.settings.refund_window_partial_days:
            max_refund_pct = 0.7
        else:
            max_refund_pct = 0.3

        if (
            historical_return_count >= self.settings.fraud_check_max_count
            and category == "不良反应"
        ):
            max_refund_pct = min(max_refund_pct, 0.5)
            require_approval = True
            max_compensation = 0
        else:
            require_approval = False
            if category == "不良反应":
                max_compensation = 50
            elif category in ("物流包装", "产品体验"):
                max_compensation = 20
            else:
                max_compensation = 0

        if yearly_spend >= self.settings.vip_threshold_yearly:
            max_compensation = max_compensation * 1.5

        return {
            "max_refund_pct": max_refund_pct,
            "max_compensation": max_compensation,
            "requires_approval": require_approval,
            "is_fraud_risk": historical_return_count >= self.settings.fraud_check_max_count,
            "is_vip": yearly_spend >= self.settings.vip_threshold_yearly,
            "days_since_purchase": days_since_purchase,
        }
