from typing import Optional
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RefundRule:
    scenario: str
    refund_policy: str
    compensation_max: float
    compensation_form: str
    coupon_scope: str
    follow_up_days: int
    upgrade_condition: str
    requires_approval: bool


class RuleStore:
    def __init__(self, file_path: Optional[str] = None):
        self._rules: dict[str, RefundRule] = {}
        if file_path and Path(file_path).exists():
            self._load(file_path)

    def add(self, rule: RefundRule):
        self._rules[rule.scenario] = rule

    def find(self, scenario: str) -> Optional[RefundRule]:
        return self._rules.get(scenario)

    def match(self, category: str, severity: str, is_first_time: bool) -> Optional[RefundRule]:
        key = f"{category}-{severity}-{'首次' if is_first_time else '多次'}"
        return self._rules.get(key) or self._rules.get(f"{category}-{severity}")

    def _load(self, file_path: str):
        data = json.loads(Path(file_path).read_text())
        for item in data:
            self.add(RefundRule(**item))
