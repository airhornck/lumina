"""
流量互导员 Skill - MCP Server

提供矩阵内流量调度、导流策略、转化追踪等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import List, Dict, Any

mcp = FastMCP("traffic_broker")


class TrafficRouteInput(BaseModel):
    """流量路由输入"""
    source_account: str
    target_account: str
    content_id: str
    route_method: str  # comment, dm, profile, content_tag
    user_id: str


class TrafficRouteOutput(BaseModel):
    """流量路由输出"""
    route_id: str
    estimated_reach: int
    estimated_ctr: float
    execution_plan: Dict[str, Any]
    tracking_code: str


@mcp.tool()
async def design_traffic_route(input: TrafficRouteInput) -> TrafficRouteOutput:
    """
    设计流量导流路径
    
    规划从源账号到目标账号的最优导流路径
    """
    # 根据导流方式计算预估效果
    method_estimates = {
        "comment": {"reach_pct": 0.3, "ctr": 0.05, "risk": "low"},
        "dm": {"reach_pct": 0.1, "ctr": 0.15, "risk": "medium"},
        "profile": {"reach_pct": 0.05, "ctr": 0.10, "risk": "low"},
        "content_tag": {"reach_pct": 0.5, "ctr": 0.08, "risk": "low"}
    }
    
    estimate = method_estimates.get(input.route_method, method_estimates["comment"])
    
    # 假设基础曝光量
    base_reach = 1000
    estimated_reach = int(base_reach * estimate["reach_pct"])
    
    return TrafficRouteOutput(
        route_id=f"route_{input.source_account}_{input.target_account}",
        estimated_reach=estimated_reach,
        estimated_ctr=estimate["ctr"],
        execution_plan={
            "steps": [
                f"在{input.source_account}发布内容",
                f"使用{input.route_method}方式植入导流",
                f"指向{input.target_account}",
                "监控转化数据"
            ],
            "timing": "内容发布后30分钟内执行",
            "content_guidelines": get_content_guidelines(input.route_method)
        },
        tracking_code=f"track_{input.content_id[:8]}"
    )


def get_content_guidelines(method: str) -> List[str]:
    """获取内容指导原则"""
    guidelines = {
        "comment": [
            "评论自然融入，避免硬广",
            "@主号时提供明确价值承诺",
            "回复评论时引导关注"
        ],
        "dm": [
            "私信前确保有互动基础",
            "提供独家福利作为关注理由",
            "避免频繁发送"
        ],
        "profile": [
            "简介简洁明了",
            "突出主号价值",
            "定期更新"
        ],
        "content_tag": [
            "内容相关性要强",
            "@账号要有理由",
            "避免过度@"
        ]
    }
    return guidelines.get(method, ["保持自然", "提供价值"])


@mcp.tool()
async def calculate_traffic_value(
    matrix_data: Dict[str, Any],
    user_id: str
) -> Dict[str, Any]:
    """
    计算流量价值
    
    评估矩阵内流量的分布和价值
    """
    accounts = matrix_data.get("accounts", [])
    
    total_followers = sum(a.get("followers", 0) for a in accounts)
    total_engagement = sum(a.get("engagement", 0) for a in accounts)
    
    # 计算流量集中度
    if accounts:
        top_account_share = max(a.get("followers", 0) for a in accounts) / total_followers
    else:
        top_account_share = 0
    
    return {
        "total_followers": total_followers,
        "total_monthly_engagement": total_engagement,
        "traffic_concentration": top_account_share,
        "distribution_health": "健康" if top_account_share < 0.5 else "需优化",
        "inter_account_flow": {
            "monthly_referrals": 1500,
            "conversion_rate": 0.08,
            "value_per_referral": 2.5
        },
        "recommendations": [
            "加强卫星号内容质量，分散流量风险" if top_account_share > 0.5 else "保持当前流量分布",
            "优化主号转化漏斗",
            "增加账号间互动"
        ]
    }


@mcp.tool()
async def optimize_cross_promotion(
    source_contents: List[Dict[str, Any]],
    target_account: str,
    user_id: str
) -> Dict[str, Any]:
    """
    优化交叉推广
    
    选择最佳内容进行导流
    """
    # 按表现排序内容
    sorted_contents = sorted(
        source_contents,
        key=lambda x: x.get("engagement_rate", 0),
        reverse=True
    )
    
    # 选择Top内容进行导流
    top_contents = sorted_contents[:3]
    
    return {
        "selected_contents": [
            {
                "id": c.get("id"),
                "title": c.get("title"),
                "engagement_rate": c.get("engagement_rate"),
                "recommended_action": "评论区@主号导流"
            }
            for c in top_contents
        ],
        "expected_results": {
            "estimated_reach": sum(c.get("views", 0) for c in top_contents) * 0.3,
            "estimated_conversions": int(sum(c.get("views", 0) for c in top_contents) * 0.3 * 0.05),
            "best_timing": "内容发布后2小时内"
        },
        "content_optimization": [
            "在内容高潮处自然提及主号",
            "提供明确的关注理由",
            "置顶引导评论"
        ]
    }


@mcp.tool()
async def track_conversion(
    route_id: str,
    start_date: str,
    end_date: str,
    user_id: str
) -> Dict[str, Any]:
    """
    追踪转化数据
    """
    return {
        "route_id": route_id,
        "period": f"{start_date} to {end_date}",
        "metrics": {
            "impressions": 5000,
            "clicks": 400,
            "ctr": 0.08,
            "follows": 80,
            "conversion_rate": 0.20,
            "cost_per_follow": 0.5
        },
        "trend": "upward",
        "top_performing_content": ["content_001", "content_003"],
        "optimization_suggestions": [
            "在流量高峰时段加强导流",
            "优化引导文案",
            "增加互动回复"
        ]
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
