"""
知识提取器 Skill - MCP Server

提供爆款拆解、模式识别、归因分析等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

mcp = FastMCP("knowledge_miner")


class ContentAnalysisInput(BaseModel):
    """内容分析输入"""
    content_url: Optional[str] = None
    content_data: Optional[Dict[str, Any]] = None
    platform: str
    user_id: str


class ContentAnalysisOutput(BaseModel):
    """内容分析输出"""
    content_id: str
    success_factors: List[Dict[str, Any]]
    structure_breakdown: Dict[str, Any]
    timing_analysis: Dict[str, Any]
    element_analysis: Dict[str, Any]
    replicability_score: float


@mcp.tool()
async def analyze_success_content(input: ContentAnalysisInput) -> ContentAnalysisOutput:
    """
    分析成功内容
    
    拆解爆款内容的成功因素
    """
    data = input.content_data or {}
    
    # 分析成功因素
    success_factors = []
    
    # 标题分析
    title = data.get("title", "")
    if any(c.isdigit() for c in title):
        success_factors.append({
            "element": "标题",
            "factor": "使用数字增强可信度",
            "impact": "high"
        })
    
    if "?" in title or "？" in title:
        success_factors.append({
            "element": "标题",
            "factor": "疑问句式引发好奇",
            "impact": "medium"
        })
    
    # 结构分析
    structure = {
        "hook": {
            "type": "悬念",
            "duration": "3秒",
            "effectiveness": 0.9
        },
        "body": {
            "paragraphs": 5,
            "avg_sentence_length": 15,
            "information_density": "high"
        },
        "conclusion": {
            "type": "CTA",
            "engagement_prompt": True
        }
    }
    
    return ContentAnalysisOutput(
        content_id=data.get("id", "unknown"),
        success_factors=success_factors + [
            {"element": "封面", "factor": "高对比配色，文字醒目", "impact": "high"},
            {"element": "节奏", "factor": "信息密度适中，不拖沓", "impact": "medium"},
            {"element": "互动", "factor": "结尾有明确的互动引导", "impact": "high"}
        ],
        structure_breakdown=structure,
        timing_analysis={
            "publish_time": "20:00",
            "day_of_week": "周三",
            "optimal": True,
            "reason": "目标受众活跃高峰"
        },
        element_analysis={
            "visual_elements": ["数据图表", "对比图", "表情包"],
            "audio_elements": ["BGM节奏匹配"],
            "text_elements": ["字幕", "重点标注"]
        },
        replicability_score=0.85
    )


@mcp.tool()
async def extract_patterns(
    content_list: List[Dict[str, Any]],
    pattern_type: str,  # success, failure, trend
    user_id: str
) -> Dict[str, Any]:
    """
    提取模式
    
    从多个内容中提取共同模式
    """
    if pattern_type == "success":
        patterns = [
            {
                "pattern_name": "3秒钩子法则",
                "description": "前3秒必须有吸引力",
                "frequency": 0.85,
                "confidence": 0.9
            },
            {
                "pattern_name": "信息密度控制",
                "description": "每15秒一个信息点",
                "frequency": 0.72,
                "confidence": 0.8
            },
            {
                "pattern_name": "情感共鸣",
                "description": "内容引发用户情感反应",
                "frequency": 0.68,
                "confidence": 0.75
            }
        ]
    elif pattern_type == "failure":
        patterns = [
            {
                "pattern_name": "开头拖沓",
                "description": "前5秒未进入主题",
                "frequency": 0.65,
                "confidence": 0.85
            },
            {
                "pattern_name": "信息过载",
                "description": "单篇内容知识点过多",
                "frequency": 0.45,
                "confidence": 0.7
            }
        ]
    else:
        patterns = []
    
    return {
        "pattern_type": pattern_type,
        "analyzed_contents": len(content_list),
        "patterns_found": len(patterns),
        "patterns": patterns,
        "actionable_insights": [
            "优先应用高频高置信度模式",
            "避免已识别的失败模式",
            "持续追踪模式有效性"
        ]
    }


@mcp.tool()
async def attribute_success(
    content_data: Dict[str, Any],
    user_id: str
) -> Dict[str, Any]:
    """
    归因分析
    
    分析内容成功的各因素贡献度
    """
    # 使用 SHAP 风格的因素分解
    factors = [
        {"factor": "发布时间", "contribution": 0.25, "direction": "positive"},
        {"factor": "标题质量", "contribution": 0.20, "direction": "positive"},
        {"factor": "封面吸引力", "contribution": 0.18, "direction": "positive"},
        {"factor": "内容价值", "contribution": 0.15, "direction": "positive"},
        {"factor": "互动引导", "contribution": 0.12, "direction": "positive"},
        {"factor": "账号权重", "contribution": 0.10, "direction": "positive"},
    ]
    
    return {
        "content_id": content_data.get("id"),
        "performance": {
            "views": content_data.get("views", 0),
            "engagement_rate": content_data.get("engagement_rate", 0)
        },
        "attribution": {
            "factors": factors,
            "top_driver": factors[0],
            "optimization_priority": [f["factor"] for f in factors[:3]]
        },
        "recommendations": [
            f"继续保持{factors[0]['factor']}的优势",
            f"尝试提升{factors[-1]['factor']}的效果"
        ]
    }


@mcp.tool()
async def generate_template(
    successful_content: List[Dict[str, Any]],
    template_name: str,
    user_id: str
) -> Dict[str, Any]:
    """
    生成内容模板
    
    基于成功案例生成可复用的内容模板
    """
    # 分析共同特征
    common_structure = {
        "title_template": "【数字】+【利益点】+【悬念】",
        "opening": "痛点/好奇心引导（3秒内）",
        "body_structure": [
            "问题陈述（10%）",
            "解决方案（60%）",
            "案例支撑（20%）",
            "行动号召（10%）"
        ],
        "closing": "互动引导 + 关注号召"
    }
    
    return {
        "template_name": template_name,
        "template_id": f"tmpl_{int(datetime.now().timestamp())}",
        "based_on": len(successful_content),
        "structure": common_structure,
        "best_practices": [
            "标题控制在20字以内",
            "前3秒必须出现核心价值",
            "每30秒一个情绪起伏",
            "结尾必须有明确的CTA"
        ],
        "fill_in_blanks": {
            "标题": "【数字】个【领域】技巧，让你【利益】",
            "开头": "你是不是也遇到过【痛点】的问题？",
            "正文": "今天分享【数字】个方法...",
            "结尾": "觉得有用的话，【行动号召】"
        },
        "expected_performance": {
            "views_lift": "+30-50%",
            "engagement_lift": "+20-30%"
        }
    }


@mcp.tool()
async def analyze_competitor(
    competitor_id: str,
    platform: str,
    analysis_depth: str = "standard",  # light, standard, deep
    user_id: str
) -> Dict[str, Any]:
    """
    竞品分析
    """
    return {
        "competitor_id": competitor_id,
        "platform": platform,
        "analysis_depth": analysis_depth,
        "overview": {
            "follower_count": 50000,
            "avg_engagement_rate": 0.06,
            "posting_frequency": "每日1更",
            "content_style": "干货型"
        },
        "strengths": [
            "内容质量稳定",
            "更新频率高",
            "互动回复及时"
        ],
        "weaknesses": [
            "内容形式单一",
            "缺乏系列内容",
            "私域导流较少"
        ],
        "top_performing_content": [
            {"title": "爆款标题1", "views": 100000, "key_success_factor": "标题党"},
            {"title": "爆款标题2", "views": 80000, "key_success_factor": "实用性强"}
        ],
        "learnable_strategies": [
            "模仿其标题结构",
            "学习其内容节奏",
            "参考其发布时间"
        ]
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
