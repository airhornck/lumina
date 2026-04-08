"""
合规审查员 Skill - MCP Server

提供内容风险检测、敏感词过滤、合规建议等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

mcp = FastMCP("compliance_officer")


# 敏感词库（简化版）
SENSITIVE_WORDS = {
    "extreme": ["最", "第一", "顶级", "绝对"],  # 极限词
    "medical": ["治疗", "疗效", "治愈", "药方"],  # 医疗相关
    "financial": ["稳赚", "保本", "高收益", "零风险"],  # 金融违规
    "discrimination": ["歧视", "地域黑"],  # 歧视性内容
    "illegal": ["赌博", "毒品", "枪支"],  # 违法内容
}

PLATFORM_RULES = {
    "xiaohongshu": {
        "forbidden": ["站外引流", "虚假宣传", "抄袭"],
        "restricted": ["医疗", "金融", "保健品"],
        "limits": {
            "max_daily_posts": 10,
            "max_hashtags": 8
        }
    },
    "douyin": {
        "forbidden": ["诱导点赞", "低俗", "危险行为"],
        "restricted": ["未授权音乐", "未成年人"],
        "limits": {
            "max_daily_posts": 20,
            "max_hashtags": 5
        }
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
    
    # 检查敏感词
    for category, words in SENSITIVE_WORDS.items():
        for word in words:
            if word in text:
                violations.append({
                    "type": "sensitive_word",
                    "category": category,
                    "word": word,
                    "severity": "high" if category in ["illegal", "medical"] else "medium",
                    "position": text.find(word)
                })
    
    # 检查平台规则
    platform_rules = PLATFORM_RULES.get(input.platform, {})
    for forbidden in platform_rules.get("forbidden", []):
        if forbidden in text:
            violations.append({
                "type": "platform_violation",
                "rule": forbidden,
                "severity": "critical"
            })
    
    # 计算风险分数
    score = min(100, len(violations) * 20)
    
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
        elif v["type"] == "platform_violation":
            suggestions.append(f"删除违规内容'{v['rule']}'，避免账号处罚")
    
    return RiskCheckOutput(
        risk_level=level,
        risk_score=score,
        violations=violations,
        suggestions=suggestions or ["内容合规，可以发布"],
        auto_fixable=score < 60  # 中等风险以下可自动修复
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
    
    评估账号的合规风险状态
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
    
    return {
        "health_score": max(0, 100 - len(recent_violations) * 20),
        "risk_level": "high" if len(risk_factors) > 1 else "medium" if risk_factors else "low",
        "risk_factors": risk_factors,
        "recommendations": [
            "使用内容预审功能",
            "定期学习平台规则更新",
            "建立内容审核SOP"
        ]
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
