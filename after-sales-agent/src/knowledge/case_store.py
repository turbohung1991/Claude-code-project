from typing import Optional
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CaseRecord:
    ticket_id: str
    category: str
    sub_category: str
    severity: str
    product_sku: str
    reason_summary: str
    decision: dict
    resolution: str
    user_feedback: str
    created_at: str


class CaseStore:
    def __init__(self, file_path: Optional[str] = None):
        self._cases: list[CaseRecord] = []
        if file_path and Path(file_path).exists():
            self._load(file_path)

    def add(self, case: CaseRecord):
        self._cases.append(case)

    def find_similar(self, category: str, sub_category: str, limit: int = 5) -> list[CaseRecord]:
        matches = [
            c for c in self._cases
            if c.category == category and c.sub_category == sub_category
        ]
        return sorted(matches, key=lambda c: c.created_at, reverse=True)[:limit]

    def find_by_sku(self, sku: str, limit: int = 10) -> list[CaseRecord]:
        return [c for c in self._cases if c.product_sku == sku][-limit:]

    def _load(self, file_path: str):
        data = json.loads(Path(file_path).read_text())
        for item in data:
            self.add(CaseRecord(**item))
