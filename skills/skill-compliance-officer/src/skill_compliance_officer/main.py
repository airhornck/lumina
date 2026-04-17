"""
合规审查员 Skill - MCP Server

提供内容风险检测、敏感词过滤、合规建议等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import List, Dict, Any

try:
    from knowledge_base.platform_registry import PlatformRegistry
except ImportError:
    import sys
    from pathlib import Path
    _kb_path = Path(__file__).resolve().parents[3] / "packages" / "knowledge-base" / "src"
    if str(_kb_path) not in sys.path:
        sys.path.insert(0, str(_kb_path))
    from knowledge_base.platform_registry import PlatformRegistry

mcp = FastMCP("compliance_officer")


# 基础敏感词库（作为 fallback，平台规范库优先）
SENSITIVE_WORDS = {
    "extreme": ["最", "第一", "顶级", "绝对"],  # 极限词
    "medical": ["治疗", "疗效", "治愈", "药方"],  # 医疗相关
    "financial": ["稳赚", "保本", "高收益", "零风险"],  # 金融违规
    "discrimination": ["歧视", "地域黑"],  # 歧视性内容
    "illegal": ["赌博", "毒品", "枪支"],  # 违法内容
}

# 程序级 fallback 平台规则（当平台规范库不可用时使用）
PLATFORM_RULES_FALLBACK = {
    "xiaohongshu": {
        "forbidden": ["站外引流", "虚假宣传", "抄袭"],
        "restricted": ["医疗", "金融", "保健品"],
    },
    "douyin": {
        "forbidden": ["诱导点赞", "低俗", "危险行为"],
        "restricted": ["未授权音乐", "未成年人"],
    }
}


class RiskCheckInput(BaseModel):
    """风险检测输入"""
    content_text: str
    platform: str
    content_type: str = "post"  # post, comment, bio
    user_id: str


class RiskCheckOutput(BaseModel):
    """风险检测输出"""
    risk_level: str  # low, medium, high, critical
    risk_score: float  # 0-100
    violations: List[Dict[str, Any]]
    suggestions: List[str]
    auto_fixable: bool


@mcp.tool()
async def check_content_risk(input: RiskCheckInput) -> RiskCheckOutput:
    """
    检查内容风险
    
    检测内容中的违规风险点
    """
    text = input.content_text
    violations = []

    # 1. 检查基础敏感词
    for category, words in SENSITIVE_WORDS.items():
        for word in words:
            if word in text:
                violations.append({
                    "type": "sensitive_word",
                    "category": category,
                    "word": word,
                    "severity": "high" if category in ["illegal", "medical"] else "medium",
                    "position": text.find(word),
                    "source": "builtin"
                })

    # 2. 优先从平台规范库读取审核规则
    platform_forbidden = []
    platform_restricted = []
    audit_rules_source = "builtin"
    try:
        spec = PlatformRegistry().load(input.platform)
        if spec.audit_rules:
            audit_rules_source = "platform_registry"
            for rule in spec.audit_rules:
                category = rule.get("category", "general")
                terms = rule.get("forbidden_terms", [])
                for term in terms:
                    platform_forbidden.append((term, category))
                    if term in text:
                        violations.append({
                            "type": "platform_audit_rule",
                            "rule": term,
                            "category": category,
                            "severity": "critical" if category in ["medical", "illegal", "sensitive"] else "high",
                            "source": "platform_registry"
                        })
    except Exception:
        pass

    # 3. fallback：检查内置平台规则
    if audit_rules_source == "builtin":
        platform_rules = PLATFORM_RULES_FALLBACK.get(input.platform, {})
        for forbidden in platform_rules.get("forbidden", []):
            platform_forbidden.append((forbidden, "general"))
            if forbidden in text:
                violations.append({
                    "type": "platform_violation",
                    "rule": forbidden,
                    "severity": "critical",
                    "source": "builtin"
                })
        for restricted in platform_rules.get("restricted", []):
            platform_restricted.append((restricted, "general"))
            if restricted in text:
                violations.append({
                    "type": "platform_restriction",
                    "rule": restricted,
                    "severity": "medium",
                    "source": "builtin"
                })

    # 计算风险分数（平台规范库命中权重更高）
    score = 0
    for v in violations:
        if v.get("source") == "platform_registry":
            score += 25
        elif v["type"] in ["platform_violation", "platform_audit_rule"]:
            score += 20
        elif v["type"] == "sensitive_word" and v.get("category") in ["illegal", "medical"]:
            score += 15
        else:
            score += 10
    score = min(100, score)

    # 确定风险等级
    if score >= 80:
        level = "critical"
    elif score >= 60:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"

    # 生成建议
    suggestions = []
    for v in violations:
        if v["type"] == "sensitive_word":
            suggestions.append(f"建议替换极限词'{v['word']}'，使用更客观的描述")
        elif v["type"] in ["platform_violation", "platform_audit_rule"]:
            src_label = "平台规范库" if v.get("source") == "platform_registry" else "内置规则"
            suggestions.append(f"[{src_label}] 删除违规内容'{v['rule']}'，避免账号处罚")
        elif v["type"] == "platform_restriction":
            suggestions.append(f"谨慎使用受限内容'{v['rule']}'，建议补充资质或调整表述")

    return RiskCheckOutput(
        risk_level=level,
        risk_score=score,
        violations=violations,
        suggestions=suggestions or ["内容合规，可以发布"],
        auto_fixable=score < 60,  # 中等风险以下可自动修复
    )


@mcp.tool()
async def suggest_safe_alternatives(
    text: str,
    violations: List[Dict[str, Any]],
    user_id: str
) -> Dict[str, Any]:
    """
    提供安全替代方案
    
    将违规内容改写为合规版本
    """
    alternatives = text
    changes = []
    
    for v in violations:
        if v["type"] == "sensitive_word":
            word = v["word"]
            if v["category"] == "extreme":
                # 极限词替换
                replacements = {
                    "最": "非常",
                    "第一": "优秀",
                    "顶级": "优质",
                    "绝对": "确实"
                }
                if word in replacements:
                    alternatives = alternatives.replace(word, replacements[word])
                    changes.append({"from": word, "to": replacements[word]})
    
    return {
        "original": text,
        "alternative": alternatives,
        "changes": changes,
        "compliance_score": max(0, 100 - len(changes) * 15),
        "notes": "已自动替换敏感词，建议人工复核"
    }


@mcp.tool()
async def check_account_health(
    account_data: Dict[str, Any],
    platform: str,
    user_id: str
) -> Dict[str, Any]:
    """
    检查账号健康度

    评估账号的合规风险状态，结合平台规范库中的审核规则
    """
    violations_history = account_data.get("violations_history", [])
    recent_violations = [v for v in violations_history if v.get("days_ago", 999) < 30]

    risk_factors = []

    if len(recent_violations) > 3:
        risk_factors.append({
            "factor": "近期违规频繁",
            "level": "high",
            "suggestion": "暂停发布30天，整改内容"
        })
    elif len(recent_violations) > 0:
        risk_factors.append({
            "factor": "有违规记录",
            "level": "medium",
            "suggestion": "加强内容审核"
        })

    if account_data.get("shadow_banned", False):
        risk_factors.append({
            "factor": "疑似被限流",
            "level": "high",
            "suggestion": "检查近期内容，申诉解限"
        })

    # 加载平台规范库审核规则作为推荐依据
    platform_audit_categories = []
    try:
        spec = PlatformRegistry().load(platform)
        for rule in spec.audit_rules:
            platform_audit_categories.append(rule.get("category", "general"))
    except Exception:
        pass

    recommendations = [
        "使用内容预审功能",
        "定期学习平台规则更新",
        "建立内容审核SOP",
    ]
    if platform_audit_categories:
        recommendations.append(
            f"重点关注 {platform} 平台的 {', '.join(platform_audit_categories)} 类审核规则"
        )

    return {
        "health_score": max(0, 100 - len(recent_violations) * 20),
        "risk_level": "high" if len(risk_factors) > 1 else "medium" if risk_factors else "low",
        "risk_factors": risk_factors,
        "platform_audit_categories": platform_audit_categories,
        "recommendations": recommendations,
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
