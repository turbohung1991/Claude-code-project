from src.knowledge.sku_store import SKUStore, SKUEntry
from src.knowledge.ingredient_store import IngredientStore, IngredientEntry
from src.knowledge.rule_store import RuleStore, RefundRule
from src.knowledge.case_store import CaseStore, CaseRecord
from src.knowledge.constraints import ComplianceConstraints


class TestSKUStore:
    def test_add_and_lookup_sku(self):
        store = SKUStore()
        entry = SKUEntry(
            sku="LP-001",
            name="氨基酸温和洁面乳 150ml",
            brand="TestBrand",
            category="洁面",
            skin_types=["干性", "敏感肌"],
            key_ingredients=["椰油酰甘氨酸钾", "泛醇", "神经酰胺"],
            texture="乳液状低泡",
            scent="无香精",
            ph=5.5,
            period_after_opening="6M",
            batch_pattern=r"LP\d{6}",
            related_skus=["LP-002"],
            common_complaints=["泡沫少被误认为洗不干净"],
        )
        store.add(entry)

        result = store.lookup("LP-001")
        assert result is not None
        assert result.name == "氨基酸温和洁面乳 150ml"
        assert result.brand == "TestBrand"
        assert "敏感肌" in result.skin_types

    def test_lookup_nonexistent_returns_none(self):
        store = SKUStore()
        assert store.lookup("NONEXISTENT") is None

    def test_search_by_skin_type(self):
        store = SKUStore()
        store.add(SKUEntry(
            sku="LP-001", name="洁面", brand="B", category="洁面",
            skin_types=["干性"], key_ingredients=[], texture="",
            scent="", ph=7.0, period_after_opening="12M", batch_pattern="",
            related_skus=[], common_complaints=[],
        ))
        store.add(SKUEntry(
            sku="LP-002", name="面霜", brand="B", category="面霜",
            skin_types=["敏感肌"], key_ingredients=[], texture="",
            scent="", ph=7.0, period_after_opening="12M", batch_pattern="",
            related_skus=[], common_complaints=[],
        ))

        results = store.search_by_skin_type("敏感肌")
        assert len(results) == 1
        assert results[0].sku == "LP-002"


class TestIngredientStore:
    def test_add_and_lookup_ingredient(self):
        store = IngredientStore()
        entry = IngredientEntry(
            name="烟酰胺",
            aliases=["维生素B3", "Niacinamide"],
            function="美白、控油、修复屏障",
            risk_level="中",
            common_reactions={
                "cause": "不耐受/浓度过高",
                "symptoms": ["泛红", "刺痛", "干燥脱皮"],
                "onset": "3-7天连续使用后",
                "mitigation": "停用 → 精简护肤 → 建立耐受从低浓度开始",
            },
            incompatible_with=["高浓度VC"],
            safe_for_pregnancy=False,
        )
        store.add(entry)

        result = store.lookup("烟酰胺")
        assert result is not None
        assert result.risk_level == "中"
        assert not result.safe_for_pregnancy

    def test_lookup_by_alias(self):
        store = IngredientStore()
        store.add(IngredientEntry(
            name="烟酰胺", aliases=["维生素B3", "Niacinamide"],
            function="美白", risk_level="低",
            common_reactions={"cause": "", "symptoms": [], "onset": "", "mitigation": ""},
            incompatible_with=[], safe_for_pregnancy=True,
        ))

        assert store.lookup("维生素B3") is not None
        assert store.lookup("Niacinamide") is not None

    def test_find_potential_allergens(self):
        store = IngredientStore()
        store.add(IngredientEntry(
            name="烟酰胺", aliases=[], function="美白",
            risk_level="中",
            common_reactions={
                "cause": "不耐受",
                "symptoms": ["泛红", "刺痛"],
                "onset": "3-7天",
                "mitigation": "停用",
            },
            incompatible_with=[], safe_for_pregnancy=True,
        ))
        store.add(IngredientEntry(
            name="泛醇", aliases=[], function="修复",
            risk_level="低",
            common_reactions={"cause": "", "symptoms": [], "onset": "", "mitigation": ""},
            incompatible_with=[], safe_for_pregnancy=True,
        ))

        results = store.find_potential_allergens(["烟酰胺", "泛醇"], ["泛红", "刺痛"])
        assert len(results) == 1
        assert results[0].name == "烟酰胺"


class TestRuleStore:
    def test_match_rule(self):
        store = RuleStore()
        store.add(RefundRule(
            scenario="不良反应-轻度-首次",
            refund_policy="全额退款",
            compensation_max=50,
            compensation_form="优惠券",
            coupon_scope="温和修复类",
            follow_up_days=7,
            upgrade_condition="无",
            requires_approval=False,
        ))

        rule = store.match("不良反应", "轻度", is_first_time=True)
        assert rule is not None
        assert rule.compensation_max == 50


class TestCaseStore:
    def test_add_and_find_similar(self):
        store = CaseStore()
        store.add(CaseRecord(
            ticket_id="TK-001", category="不良反应", sub_category="泛红刺痛",
            severity="轻度", product_sku="LP-001",
            reason_summary="使用后泛红", decision={},
            resolution="全额退款", user_feedback="满意", created_at="2026-06-01",
        ))
        store.add(CaseRecord(
            ticket_id="TK-002", category="物流包装", sub_category="破损漏液",
            severity="轻度", product_sku="LP-003",
            reason_summary="瓶子碎了", decision={},
            resolution="补发", user_feedback="满意", created_at="2026-06-01",
        ))

        results = store.find_similar("不良反应", "泛红刺痛")
        assert len(results) == 1
        assert results[0].ticket_id == "TK-001"


class TestComplianceConstraints:
    def test_medical_keyword_triggers_violation(self):
        cc = ComplianceConstraints()
        violations = cc.check_text("您脸部破溃，建议先停用")
        assert len(violations) == 1
        assert "破溃" in violations[0]

    def test_effect_claim_triggers_violation(self):
        cc = ComplianceConstraints()
        violations = cc.check_text("我们这款产品效果很好")
        assert len(violations) >= 1

    def test_clean_text_passes(self):
        cc = ComplianceConstraints()
        violations = cc.check_text("非常抱歉，已为您办理退款")
        assert len(violations) == 0
