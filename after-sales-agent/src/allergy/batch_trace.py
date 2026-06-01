from collections import defaultdict
from datetime import date, timedelta


class BatchTracker:
    def __init__(self, alert_threshold: float = 0.005):
        self.alert_threshold = alert_threshold
        self._records: dict[str, list[dict]] = defaultdict(list)

    def record(self, batch_number: str, ticket_id: str, date_reported: date):
        self._records[batch_number].append({
            "ticket_id": ticket_id,
            "date_reported": date_reported,
        })

    def check_alert(self, batch_number: str, window_days: int = 7) -> dict:
        records = self._records.get(batch_number, [])
        cutoff = date.today() - timedelta(days=window_days)
        recent = [r for r in records if r["date_reported"] >= cutoff]

        total_orders = self._get_total_orders(batch_number)
        if total_orders == 0:
            return {
                "batch_number": batch_number,
                "allergy_rate_7d": 0,
                "total_orders": 0,
                "allergy_cases": len(recent),
                "should_alert": False,
            }

        allergy_rate = len(recent) / total_orders
        return {
            "batch_number": batch_number,
            "allergy_rate_7d": round(allergy_rate, 4),
            "total_orders": total_orders,
            "allergy_cases": len(recent),
            "should_alert": allergy_rate > self.alert_threshold,
        }

    def _get_total_orders(self, batch_number: str) -> int:
        return len(self._records.get(batch_number, [])) * 50
