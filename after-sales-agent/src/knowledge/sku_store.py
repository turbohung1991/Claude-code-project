from typing import Optional
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SKUEntry:
    sku: str
    name: str
    brand: str
    category: str
    skin_types: list[str]
    key_ingredients: list[str]
    texture: str
    scent: str
    ph: float
    period_after_opening: str
    batch_pattern: str
    related_skus: list[str]
    common_complaints: list[str]


class SKUStore:
    def __init__(self, file_path: Optional[str] = None):
        self._skus: dict[str, SKUEntry] = {}
        self._file_path = file_path
        if file_path and Path(file_path).exists():
            self._load(file_path)

    def add(self, entry: SKUEntry):
        self._skus[entry.sku] = entry

    def lookup(self, sku: str) -> Optional[SKUEntry]:
        return self._skus.get(sku)

    def search_by_skin_type(self, skin_type: str) -> list[SKUEntry]:
        return [s for s in self._skus.values() if skin_type in s.skin_types]

    def search_by_ingredient(self, ingredient: str) -> list[SKUEntry]:
        return [s for s in self._skus.values() if ingredient in s.key_ingredients]

    def _load(self, file_path: str):
        data = json.loads(Path(file_path).read_text())
        for item in data:
            self.add(SKUEntry(**item))

    def save(self, file_path: str):
        Path(file_path).write_text(
            json.dumps([vars(s) for s in self._skus.values()], ensure_ascii=False, indent=2)
        )

    def extract_batch(self, sku: str, raw_batch: str) -> Optional[str]:
        entry = self.lookup(sku)
        if entry and re.match(entry.batch_pattern, raw_batch):
            return raw_batch
        return None
