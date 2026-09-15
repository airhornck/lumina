from __future__ import annotations

from typing import Dict, List

from knowledge_base.platform_registry import PlatformRegistry


class ComplianceScanner:
    """合规扫描器：基于平台审核规则做关键词命中检测。"""

    def scan(self, text: str, platform: str) -> List[str]:
        warnings: List[str] = []
        try:
            spec = PlatformRegistry().load(platform)
        except Exception:
            return warnings

        if not spec or not hasattr(spec, "audit_rules") or not spec.audit_rules:
            return warnings

        for rule in spec.audit_rules:
            if not isinstance(rule, dict):
                continue
            category = rule.get("category", "")
            forbidden = rule.get("forbidden_terms", [])
            for term in forbidden:
                if term in text:
                    suggestion = self._get_suggestion(term, category)
                    warnings.append(
                        f"命中 {category} 类禁用词：{term}"
                        + (f" → 建议替换为{suggestion}" if suggestion else "")
                    )

        return warnings

    def _get_suggestion(self, term: str, category: str) -> str:
        """根据禁用词类别给出替换建议"""
        suggestions: Dict[str, Dict[str, str]] = {
            "medical": {
                "疗效": "\"效果\"、\"体验\"",
                "治愈": "\"改善\"、\"缓解\"",
                "根治": "\"调理\"、\"养护\"",
            },
            "comparison": {
                "最好": "\"不错\"、\"推荐\"",
                "第一": "\"热门\"、\"优选\"",
                "最强": "\"出色\"、\"给力\"",
            },
            "sensitive": {
                "赚钱": "\"收益\"、\"回报\"",
                "暴富": "\"增长\"、\"积累\"",
            },
        }
        cat_suggestions = suggestions.get(category, {})
        replacement = cat_suggestions.get(term, "")
        return replacement
