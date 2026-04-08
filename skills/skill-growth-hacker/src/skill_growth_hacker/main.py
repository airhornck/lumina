"""
投放优化师 Skill - MCP Server

提供投放策略、A/B测试、增长策略等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

mcp = FastMCP("growth_hacker")


class AdStrategyInput(BaseModel):
    """投放策略输入"""
    goal: str  # awareness, consideration, conversion
    budget: float
    duration_days: int
    platform: str
    target_audience: Optional[Dict[str, Any]] = None
    user_id: str


class AdStrategyOutput(BaseModel):
    """投放策略输出"""
    strategy_name: str
    budget_allocation: Dict[str, float]
    audience_targeting: Dict[str, Any]
    creative_recommendations: List[str]
    bidding_strategy: str
    expected_roi: float
    timeline: List[Dict[str, Any]]


class ABTestDesignInput(BaseModel):
    """A/B测试设计输入"""
    test_goal: str
    variables: List[str]  # 要测试的变量
    current_version: Dict[str, Any]
    user_id: str


class ABTestDesignOutput(BaseModel):
    """A/B测试设计输出"""
    test_hypothesis: str
    variants: List[Dict[str, Any]]
    sample_size: int
    duration_days: int
    success_metrics: List[str]
    stopping_criteria: Dict[str, Any]


@mcp.tool()
async def design_ad_strategy(input: AdStrategyInput) -> AdStrategyOutput:
    """
    设计投放策略
    
    基于目标、预算和受众制定投放计划
    """
    # 根据目标确定策略
    goal_strategies = {
        "awareness": {
            "name": "品牌曝光策略",
            "allocation": {"feeds": 0.6, "search": 0.2, "display": 0.2},
            "bidding": "CPM",
            "expected_roi": 1.5
        },
        "consideration": {
            "name": "互动引导策略",
            "allocation": {"feeds": 0.7, "search": 0.3},
            "bidding": "CPC",
            "expected_roi": 2.0
        },
        "conversion": {
            "name": "转化收割策略",
            "allocation": {"search": 0.5, "feeds": 0.4, "remarketing": 0.1},
            "bidding": "oCPM",
            "expected_roi": 3.0
        }
    }
    
    strategy = goal_strategies.get(input.goal, goal_strategies["awareness"])
    
    return AdStrategyOutput(
        strategy_name=strategy["name"],
        budget_allocation={
            k: round(v * input.budget, 2) 
            for k, v in strategy["allocation"].items()
        },
        audience_targeting={
            "age_range": "18-35",
            "gender": "all",
            "interests": input.target_audience.get("interests", []) if input.target_audience else [],
            "behaviors": ["engaged_shoppers", "frequent_travelers"]
        },
        creative_recommendations=[
            "使用真实场景图片，避免过度美化",
            "标题包含数字和利益点",
            "视频前3秒必须有吸引力",
            "添加明确的行动号召按钮"
        ],
        bidding_strategy=strategy["bidding"],
        expected_roi=strategy["expected_roi"],
        timeline=[
            {"phase": "测试期", "days": "1-3", "budget_pct": 0.2, "action": "小预算测试素材"},
            {"phase": "优化期", "days": "4-7", "budget_pct": 0.3, "action": "淘汰低效素材"},
            {"phase": "放量期", "days": "8+", "budget_pct": 0.5, "action": "加大高效素材投放"},
        ]
    )


@mcp.tool()
async def design_ab_test(input: ABTestDesignInput) -> ABTestDesignOutput:
    """
    设计 A/B 测试
    
    设计科学的 A/B 测试方案
    """
    # 生成测试变体
    variants = []
    
    for i, variable in enumerate(input.variables):
        variants.append({
            "name": f"Variant_{chr(65+i)}",  # A, B, C...
            "variable": variable,
            "description": f"测试 {variable} 的影响",
            "modification": f"修改 {variable} 的值"
        })
    
    # 添加对照组
    variants.insert(0, {
        "name": "Control",
        "variable": "baseline",
        "description": "当前版本，不做修改",
        "modification": "无"
    })
    
    return ABTestDesignOutput(
        test_hypothesis=f"修改 {', '.join(input.variables)} 将提升 {input.test_goal}",
        variants=variants,
        sample_size=1000,  # 每组最少样本
        duration_days=7,
        success_metrics=[
            "conversion_rate",
            "click_through_rate",
            "cost_per_acquisition"
        ],
        stopping_criteria={
            "min_confidence": 0.95,
            "min_improvement": 0.05,  # 至少5%提升
            "max_duration": 14  # 最长14天
        }
    )


@mcp.tool()
async def optimize_bidding(
    campaign_data: Dict[str, Any],
    goal: str,
    user_id: str
) -> Dict[str, Any]:
    """
    优化出价策略
    
    根据历史数据优化出价
    """
    current_cpa = campaign_data.get("cost_per_acquisition", 50)
    current_roas = campaign_data.get("roas", 2.0)
    
    recommendations = []
    
    if current_roas < 2.0:
        recommendations.append({
            "action": "降低出价",
            "current": current_cpa,
            "suggested": round(current_cpa * 0.9, 2),
            "reason": "ROAS 偏低，需降低成本"
        })
    elif current_roas > 4.0:
        recommendations.append({
            "action": "提高出价",
            "current": current_cpa,
            "suggested": round(current_cpa * 1.1, 2),
            "reason": "ROAS 优秀，可争取更多流量"
        })
    else:
        recommendations.append({
            "action": "保持当前出价",
            "current": current_cpa,
            "suggested": current_cpa,
            "reason": "ROAS 健康，维持现状"
        })
    
    return {
        "current_performance": {
            "cpa": current_cpa,
            "roas": current_roas,
            "spend": campaign_data.get("spend", 0)
        },
        "recommendations": recommendations,
        "expected_outcome": "预计 ROAS 提升 10-15%"
    }


@mcp.tool()
async def analyze_growth_opportunities(
    account_data: Dict[str, Any],
    platform: str,
    user_id: str
) -> Dict[str, Any]:
    """
    分析增长机会
    
    识别账号的增长机会和优化点
    """
    return {
        "opportunities": [
            {
                "area": "内容形式",
                "insight": "视频内容互动率比图文高 3x",
                "action": "增加视频内容比例至 60%",
                "expected_impact": "+25% 互动率"
            },
            {
                "area": "发布时间",
                "insight": "晚8点发布的平均曝光高 40%",
                "action": "重点内容安排在晚8点发布",
                "expected_impact": "+20% 曝光量"
            },
            {
                "area": "话题标签",
                "insight": "使用热门话题标签的内容更易传播",
                "action": "每篇内容添加 3-5 个热门标签",
                "expected_impact": "+15% 新粉丝获取"
            }
        ],
        "quick_wins": [
            "优化个人简介，添加明确的关注理由",
            "置顶表现最好的3条内容",
            "开启自动回复，提升互动响应速度"
        ],
        "long_term_strategies": [
            "建立内容系列，培养用户追更习惯",
            "与其他创作者联动，扩大影响力",
            "建立私域社群，提升粉丝粘性"
        ]
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
