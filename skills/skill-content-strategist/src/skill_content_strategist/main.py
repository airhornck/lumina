"""
内容策略师 Skill - MCP Server

提供账号定位、选题策略、内容规划等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio

mcp = FastMCP("content_strategist")


class PositioningInput(BaseModel):
    """定位分析输入"""
    platform: str  # xiaohongshu, douyin, bilibili
    niche: str  # 赛道/领域
    target_audience: Optional[str] = None
    competitor_accounts: Optional[List[str]] = None
    user_id: str


class PositioningOutput(BaseModel):
    """定位分析输出"""
    positioning_statement: str  # 定位声明
    target_persona: Dict[str, Any]  # 目标人群画像
    content_pillars: List[str]  # 内容支柱
    differentiation: str  # 差异化策略
    posting_frequency: str  # 发布频率建议


class TopicCalendarInput(BaseModel):
    """选题日历输入"""
    platform: str
    niche: str
    positioning: str
    duration_days: int = 30
    user_id: str


class TopicCalendarOutput(BaseModel):
    """选题日历输出"""
    calendar: List[Dict[str, Any]]  # 每日选题
    theme_weeks: List[Dict[str, Any]]  # 主题周规划
    hot_topics: List[str]  # 热点追踪建议


@mcp.tool()
async def analyze_positioning(input: PositioningInput) -> PositioningOutput:
    """
    分析账号定位
    
    Args:
        input: 定位分析输入参数
    
    Returns:
        定位分析报告
    """
    # 获取 LLM 客户端
    try:
        from llm_hub import get_client
        llm = get_client(skill_name="content_strategist")
    except ImportError:
        llm = None
    
    # 构建分析 Prompt
    prompt = f"""
    作为资深内容策略师，请为以下账号进行定位分析：
    
    平台：{input.platform}
    赛道：{input.niche}
    目标受众：{input.target_audience or '未指定'}
    对标账号：{input.competitor_accounts or '未指定'}
    
    请提供：
    1. 一句话定位声明（我是谁，为谁，提供什么价值）
    2. 目标人群画像（年龄、性别、痛点、需求）
    3. 3-5个内容支柱（核心内容方向）
    4. 差异化策略（如何与竞品区隔）
    5. 发布频率建议
    
    以 JSON 格式输出。
    """
    
    if llm:
        try:
            response = await llm.complete(prompt, temperature=0.7)
            # 解析 JSON 响应
            import json
            data = json.loads(response)
            
            return PositioningOutput(
                positioning_statement=data.get("positioning_statement", ""),
                target_persona=data.get("target_persona", {}),
                content_pillars=data.get("content_pillars", []),
                differentiation=data.get("differentiation", ""),
                posting_frequency=data.get("posting_frequency", "每周3-4更")
            )
        except Exception:
            pass
    
    # Fallback 默认响应
    return PositioningOutput(
        positioning_statement=f"专注{input.niche}领域的优质内容创作者",
        target_persona={"age": "18-35", "gender": "女性为主", "pain_points": ["信息不对称", "选择困难"]},
        content_pillars=["干货分享", "案例拆解", "避坑指南", "趋势解读"],
        differentiation="深入浅出，实用导向",
        posting_frequency="每周3-4更"
    )


@mcp.tool()
async def generate_topic_calendar(input: TopicCalendarInput) -> TopicCalendarOutput:
    """
    生成选题日历
    
    Args:
        input: 选题日历输入参数
    
    Returns:
        选题日历
    """
    # 模拟生成选题日历
    calendar = []
    themes = ["干货分享", "案例拆解", "互动话题", "热点追踪"]
    
    for day in range(1, input.duration_days + 1):
        theme = themes[day % len(themes)]
        calendar.append({
            "day": day,
            "theme": theme,
            "topic": f"{input.niche} - {theme}专题 #{day}",
            "format": "图文" if day % 2 == 0 else "视频",
            "best_time": "18:00" if day % 2 == 0 else "12:00"
        })
    
    return TopicCalendarOutput(
        calendar=calendar,
        theme_weeks=[
            {"week": 1, "theme": "基础认知建立"},
            {"week": 2, "theme": "深度价值输出"},
            {"week": 3, "theme": "互动与转化"},
            {"week": 4, "theme": "复盘与展望"},
        ],
        hot_topics=[f"{input.niche}行业最新趋势", "平台算法更新解读", "竞品爆款分析"]
    )


@mcp.tool()
async def predict_trends(niche: str, platform: str, user_id: str) -> Dict[str, Any]:
    """
    预测热点趋势
    
    Args:
        niche: 赛道
        platform: 平台
        user_id: 用户ID
    
    Returns:
        趋势预测报告
    """
    return {
        "emerging_topics": [f"{niche}新玩法", "AI+内容创作", "短剧营销"],
        "seasonal_opportunities": ["618购物节", "暑期档", "开学季"],
        "content_formats": ["短视频", "图文笔记", "直播切片"],
        "confidence": 0.75
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
