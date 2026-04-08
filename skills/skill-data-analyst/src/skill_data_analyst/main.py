"""
数据分析师 Skill - MCP Server

提供账号诊断、流量分析、数据归因等能力
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

mcp = FastMCP("data_analyst")


class AccountDiagnosisInput(BaseModel):
    """账号诊断输入"""
    account_url: str
    platform: str
    metrics: Optional[Dict[str, Any]] = None
    user_id: str


class AccountDiagnosisOutput(BaseModel):
    """账号诊断输出"""
    overall_score: float  # 0-100
    health_status: str  # healthy, warning, critical
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[Dict[str, Any]]
    benchmarks: Dict[str, Any]


class TrafficAnalysisInput(BaseModel):
    """流量分析输入"""
    metrics: Dict[str, Any]  # 曝光、点击、互动等数据
    platform: str
    period: str  # 7d, 30d, 90d
    user_id: str


class TrafficAnalysisOutput(BaseModel):
    """流量分析输出"""
    traffic_sources: Dict[str, float]  # 流量来源分布
    funnel_analysis: Dict[str, Any]  # 漏斗分析
    trends: List[Dict[str, Any]]  # 趋势数据
    anomalies: List[Dict[str, Any]]  # 异常点
    recommendations: List[str]


@mcp.tool()
async def diagnose_account(input: AccountDiagnosisInput) -> AccountDiagnosisOutput:
    """
    诊断账号健康状况
    
    基于账号数据和平台表现给出综合诊断
    """
    # 模拟诊断逻辑
    metrics = input.metrics or {}
    
    # 计算综合得分
    follower_count = metrics.get("followers", 0)
    engagement_rate = metrics.get("engagement_rate", 0)
    content_count = metrics.get("content_count", 0)
    
    # 简单的评分逻辑
    score = min(100, max(0, 
        (follower_count / 10000) * 20 +  # 粉丝权重
        engagement_rate * 50 +  # 互动率权重
        min(content_count / 10, 30)  # 内容数量权重
    ))
    
    # 确定健康状态
    if score >= 80:
        status = "healthy"
    elif score >= 60:
        status = "warning"
    else:
        status = "critical"
    
    return AccountDiagnosisOutput(
        overall_score=round(score, 1),
        health_status=status,
        strengths=[
            "内容发布频率稳定" if content_count > 10 else "内容质量潜力大",
            "粉丝互动积极" if engagement_rate > 0.05 else "内容调性清晰",
        ],
        weaknesses=[
            "粉丝增长速度有待提升" if follower_count < 1000 else "内容多样性可优化",
            "互动率低于行业平均" if engagement_rate < 0.03 else "发布时间点可优化",
        ],
        recommendations=[
            {
                "priority": "high",
                "action": "优化发布时间",
                "expected_impact": "提升20-30%曝光量"
            },
            {
                "priority": "medium",
                "action": "增加互动引导",
                "expected_impact": "提升15%互动率"
            },
        ],
        benchmarks={
            "industry_avg_engagement": 0.045,
            "top_10_percent_engagement": 0.08,
            "your_engagement": engagement_rate
        }
    )


@mcp.tool()
async def analyze_traffic(input: TrafficAnalysisInput) -> TrafficAnalysisOutput:
    """
    分析流量结构和转化漏斗
    
    识别流量来源、转化瓶颈和优化机会
    """
    metrics = input.metrics
    
    # 模拟流量来源分析
    views = metrics.get("views", 0)
    likes = metrics.get("likes", 0)
    comments = metrics.get("comments", 0)
    shares = metrics.get("shares", 0)
    follows = metrics.get("follows", 0)
    
    # 计算漏斗转化率
    funnel = {
        "exposure": views,
        "click": int(views * 0.15),  # 假设15%点击率
        "engage": likes + comments + shares,
        "convert": follows,
        "rates": {
            "exposure_to_click": 0.15,
            "click_to_engage": (likes + comments + shares) / max(views * 0.15, 1),
            "engage_to_convert": follows / max(likes + comments + shares, 1)
        }
    }
    
    # 识别异常
    anomalies = []
    if funnel["rates"]["click_to_engage"] < 0.1:
        anomalies.append({
            "type": "low_engagement",
            "severity": "high",
            "description": "内容互动率异常低，可能是内容质量问题",
            "suggestion": "优化内容开头，增加钩子"
        })
    
    return TrafficAnalysisOutput(
        traffic_sources={
            "recommendation": 0.45,
            "search": 0.25,
            "profile": 0.15,
            "other": 0.15
        },
        funnel_analysis=funnel,
        trends=[
            {"date": "2024-01-01", "views": 1000, "engagement": 0.05},
            {"date": "2024-01-02", "views": 1200, "engagement": 0.06},
            {"date": "2024-01-03", "views": 1100, "engagement": 0.055},
        ],
        anomalies=anomalies,
        recommendations=[
            "优化内容开头3秒，提升完播率",
            "在内容中增加互动引导，如提问",
            "分析高互动内容，提取成功因素",
            "调整发布时间至用户活跃高峰"
        ]
    )


@mcp.tool()
async def generate_weekly_report(
    account_id: str,
    platform: str,
    week_start: str,
    user_id: str
) -> Dict[str, Any]:
    """
    生成周度数据报告
    """
    return {
        "period": f"{week_start} ~ (7 days)",
        "summary": {
            "total_views": 15000,
            "total_engagements": 1200,
            "new_followers": 150,
            "content_published": 7
        },
        "highlights": [
            "周三发布的内容获得最高互动率",
            "视频内容表现优于图文",
            "晚上8点发布的曝光量最高"
        ],
        "content_performance": [
            {"rank": 1, "title": "爆款内容标题", "views": 5000, "engagement_rate": 0.08},
            {"rank": 2, "title": "内容2", "views": 3000, "engagement_rate": 0.06},
        ],
        "next_week_goals": [
            "保持周三发布节奏",
            "增加2条视频内容",
            "测试新的标题风格"
        ]
    }


@mcp.tool()
async def detect_anomalies(
    metrics_history: List[Dict[str, Any]],
    metric_name: str,
    user_id: str
) -> Dict[str, Any]:
    """
    检测数据异常
    
    识别数据中的异常点和趋势变化
    """
    anomalies = []
    
    # 简单异常检测：检测数值突然下降
    for i in range(1, len(metrics_history)):
        prev = metrics_history[i-1].get(metric_name, 0)
        curr = metrics_history[i].get(metric_name, 0)
        
        if prev > 0 and curr / prev < 0.5:  # 下降超过50%
            anomalies.append({
                "date": metrics_history[i].get("date"),
                "metric": metric_name,
                "previous_value": prev,
                "current_value": curr,
                "change_percent": round((curr - prev) / prev * 100, 1),
                "severity": "high" if curr / prev < 0.3 else "medium"
            })
    
    return {
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies,
        "suggestions": [
            "检查异常日期是否有平台算法更新",
            "分析内容质量是否有变化",
            "确认账号是否有违规记录"
        ] if anomalies else ["数据表现正常，继续保持"]
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
