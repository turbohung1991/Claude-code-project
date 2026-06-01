from typing import Optional
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IngredientEntry:
    name: str
    aliases: list[str]
    function: str
    risk_level: str
    common_reactions: dict
    incompatible_with: list[str]
    safe_for_pregnancy: bool


class IngredientStore:
    def __init__(self, file_path: Optional[str] = None):
        self._ingredients: dict[str, IngredientEntry] = {}
        self._alias_map: dict[str, str] = {}
        if file_path and Path(file_path).exists():
            self._load(file_path)

    def add(self, entry: IngredientEntry):
        self._ingredients[entry.name] = entry
        for alias in entry.aliases:
            self._alias_map[alias.lower()] = entry.name

    def lookup(self, name: str) -> Optional[IngredientEntry]:
        key = self._alias_map.get(name.lower(), name)
        return self._ingredients.get(key)

    def find_potential_allergens(
        self, ingredients: list[str], symptoms: list[str]
    ) -> list[IngredientEntry]:
        results = []
        for ing_name in ingredients:
            entry = self.lookup(ing_name)
            if not entry:
                continue
            ing_symptoms = entry.common_reactions.get("symptoms", [])
            if any(s in ing_symptoms for s in symptoms):
                results.append(entry)
        return results

    def _load(self, file_path: str):
        data = json.loads(Path(file_path).read_text())
        for item in data:
            self.add(IngredientEntry(**item))
