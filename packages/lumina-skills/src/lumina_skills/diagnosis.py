from __future__ import annotations

from typing import Any, Dict, List

from knowledge_base.platform_registry import PlatformRegistry


async def diagnose_account(
    account_url: str,
    platform: str,
    user_id: str,
    analysis_depth: str = "standard",
) -> Dict[str, Any]:
    """账号基因诊断（占位 + 平台规范加载；可接爬虫/LLM）。"""
    _ = account_url, analysis_depth
    plib = PlatformRegistry()
    spec = plib.load(platform)
    return {
        "account_gene": {
            "content_types": ["lifestyle", "tutorial"],
            "style_tags": ["亲和", "干货"],
            "audience_sketch": "18-35 岁女性为主（占位）",
        },
        "health_score": 72.0,
        "key_issues": ["更新频率不稳定", "钩子前 3 秒偏弱"],
        "improvement_suggestions": [
            {"area": "hook", "tip": "参考平台 DNA：" + str(spec.content_dna[:1])},
        ],
        "recommended_methodology": "aida_advanced",
        "user_id": user_id,
        "platform": platform,
    }


async def analyze_traffic(
    metrics: Dict[str, Any],
    user_id: str,
    platform: str,
    time_range: str = "7d",
) -> Dict[str, Any]:
    _ = user_id, platform, time_range
    views = int(metrics.get("views") or metrics.get("impressions") or 0)
    likes = int(metrics.get("likes") or 0)
    shares = int(metrics.get("shares") or 0)
    ctr = (likes / views * 100) if views else 0.0
    return {
        "funnel_analysis": {
            "exposure": views,
            "engagement_rate": round(ctr, 2),
            "shares": shares,
        },
        "drop_off_points": ["互动率低于行业均值（占位）"] if ctr < 3 else [],
        "trend": "stable",
        "anomaly_detection": [],
        "actionable_insights": [f"当前样本曝光 {views}，优先优化封面与标题。"],
    }


async def detect_risk(
    content_text: str,
    platform: str,
    content_type: str = "post",
) -> Dict[str, Any]:
    _ = content_type
    spec = PlatformRegistry().load(platform)
    risks: List[Dict[str, Any]] = []
    flagged: List[Dict[str, Any]] = []
    text = content_text or ""
    for rule in spec.audit_rules:
        terms = rule.get("forbidden_terms") or []
        cat = rule.get("category") or "general"
        for t in terms:
            if t and t in text:
                risks.append({"category": cat, "term": t})
                flagged.append({"term": t, "category": cat})
    level = "low"
    if len(flagged) >= 3:
        level = "high"
    elif flagged:
        level = "medium"
    return {
        "risk_level": level,
        "risk_categories": list({r["category"] for r in risks}) or ["none"],
        "flagged_terms": flagged,
        "suggestions": ["删除或改写敏感词"] if flagged else ["未发现明显违规词（规则库占位）"],
        "alternative_phrases": {},
    }
