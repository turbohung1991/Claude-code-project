from typing import Optional
from src.knowledge.sku_store import SKUStore, SKUEntry
from src.knowledge.ingredient_store import IngredientStore, IngredientEntry
from src.knowledge.rule_store import RuleStore, RefundRule
from src.knowledge.case_store import CaseStore, CaseRecord


class KnowledgeBase:
    def __init__(
        self,
        sku_store: SKUStore,
        ingredient_store: IngredientStore,
        rule_store: RuleStore,
        case_store: CaseStore,
    ):
        self.skus = sku_store
        self.ingredients = ingredient_store
        self.rules = rule_store
        self.cases = case_store

    def get_product_context(self, sku: str) -> dict:
        entry = self.skus.lookup(sku)
        if not entry:
            return {"sku": sku, "found": False}
        return {
            "sku": entry.sku,
            "name": entry.name,
            "brand": entry.brand,
            "skin_types": entry.skin_types,
            "key_ingredients": entry.key_ingredients,
            "texture": entry.texture,
            "scent": entry.scent,
            "common_complaints": entry.common_complaints,
            "related_skus": entry.related_skus,
            "found": True,
        }

    def get_allergen_analysis(self, ingredients: list[str], symptoms: list[str]) -> dict:
        matches = self.ingredients.find_potential_allergens(ingredients, symptoms)
        return {
            "suspected_allergens": [
                {"name": m.name, "risk_level": m.risk_level, "function": m.function}
                for m in matches
            ],
            "safe_alternatives": self._find_alternatives(ingredients, matches),
        }

    def get_refund_rule(
        self, category: str, severity: str, is_first_time: bool
    ) -> Optional[dict]:
        rule = self.rules.match(category, severity, is_first_time)
        if not rule:
            return None
        return {
            "refund_policy": rule.refund_policy,
            "compensation_max": rule.compensation_max,
            "compensation_form": rule.compensation_form,
            "coupon_scope": rule.coupon_scope,
            "follow_up_days": rule.follow_up_days,
            "requires_approval": rule.requires_approval,
        }

    def get_similar_cases(self, category: str, sub_category: str, limit: int = 5) -> list[dict]:
        cases = self.cases.find_similar(category, sub_category, limit)
        return [
            {
                "ticket_id": c.ticket_id,
                "severity": c.severity,
                "decision": c.decision,
                "resolution": c.resolution,
                "user_feedback": c.user_feedback,
            }
            for c in cases
        ]

    def _find_alternatives(
        self, current_ingredients: list[str], allergens: list[IngredientEntry]
    ) -> list[dict]:
        allergen_names = {a.name for a in allergens}
        alternatives = []
        for entry in self.skus._skus.values():
            if not any(ing in entry.key_ingredients for ing in allergen_names):
                alternatives.append({"sku": entry.sku, "name": entry.name})
        return alternatives[:5]
