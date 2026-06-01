from typing import Optional
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BrandConstraint:
    brand: str
    rules: list[str]


class ComplianceConstraints:
    """品牌和法务合规约束，硬编码基线 + JSON 扩展。"""

    HARD_RULES = [
        "禁止给出医疗诊断或用药建议",
        "出现'破溃''化脓''眼部肿胀''呼吸困难'必须建议就医",
        "禁止承诺产品效果或功效",
        "禁止说'是我们产品的问题'，只能表达为'不适合您的肤质'",
    ]

    COMPLIANCE_KEYWORDS = ["破溃", "化脓", "眼部肿胀", "呼吸困难", "溃烂"]

    def __init__(self, file_path: Optional[str] = None):
        self._brand_constraints: dict[str, BrandConstraint] = {}
        if file_path and Path(file_path).exists():
            self._load(file_path)

    def check_text(self, text: str) -> list[str]:
        """返回违规项列表，空列表表示通过。"""
        violations = []
        for kw in self.COMPLIANCE_KEYWORDS:
            if kw in text and "建议就医" not in text:
                violations.append(f"包含高危关键词'{kw}'但未建议就医")
        if "效果" in text or "功效" in text:
            violations.append("包含效果/功效承诺类表述")
        if "我们产品的问题" in text or "产品质量问题" in text:
            violations.append("暗示产品责任")
        return violations

    def _load(self, file_path: str):
        data = json.loads(Path(file_path).read_text())
        for item in data:
            self._brand_constraints[item["brand"]] = BrandConstraint(**item)
