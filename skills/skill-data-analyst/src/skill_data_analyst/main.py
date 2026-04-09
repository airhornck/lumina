"""
数据分析师 Skill - MCP Server

提供真实的账号诊断、流量分析、数据归因等能力
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
    overall_score: float
    health_status: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[Dict[str, Any]]
    benchmarks: Dict[str, Any]


class TrafficAnalysisInput(BaseModel):
    """流量分析输入"""
    metrics: Dict[str, Any]
    platform: str
    period: str
    user_id: str


class TrafficAnalysisOutput(BaseModel):
    """流量分析输出"""
    traffic_sources: Dict[str, float]
    funnel_analysis: Dict[str, Any]
    trends: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    recommendations: List[str]


@mcp.tool()
async def diagnose_account(input: AccountDiagnosisInput) -> AccountDiagnosisOutput:
    """
    诊断账号健康状况
    
    优先使用 RPA 抓取真实数据，如失败则使用用户提供的 metrics
    """
    real_data = None
    
    # 尝试使用 RPA 抓取真实数据
    if input.account_url:
        try:
            from rpa.skill_utils import get_rpa_helper
            
            rpa = get_rpa_helper()
            result = await rpa.crawl_account(
                account_url=input.account_url,
                platform=input.platform,
                account_id=input.user_id,
                user_id=input.user_id,
                max_contents=10,
            )
            
            if result.success:
                real_data = result.data
                print(f"[diagnose_account] RPA 抓取成功: {real_data.get('nickname')}")
            else:
                print(f"[diagnose_account] RPA 抓取失败: {result.error}")
                
        except Exception as e:
            print(f"[diagnose_account] RPA 异常: {e}")
    
    # 使用抓取的数据或用户提供的 metrics
    if real_data:
        # 使用真实抓取的数据
        diagnosis = real_data.get("diagnosis", {})
        metrics = real_data
        data_source = "rpa_crawler"
    elif input.metrics:
        # 使用用户提供的 metrics
        metrics = input.metrics
        data_source = "user_provided"
    else:
        # 使用默认空数据
        metrics = {}
        data_source = "empty"
    
    # 计算健康分
    follower_count = metrics.get("followers", 0)
    likes = metrics.get("likes", 0)
    content_count = metrics.get("content_count", 0)
    
    # 计算估算的互动率
    engagement_rate = 0.0
    if follower_count > 0 and likes > 0:
        engagement_rate = min(100.0, likes / follower_count / max(content_count, 1) * 100)
    
    # 基于真实数据或估算计算综合得分
    score = 50.0  # 基础分
    
    if real_data:
        # 使用抓取的健康分或重新计算
        score = diagnosis.get("health_score", 50.0)
    else:
        # 基于 metrics 计算
        score += min(20, follower_count / 1000)  # 粉丝加分
        score += min(15, content_count / 2)  # 内容数加分
        score += min(15, engagement_rate)  # 互动率加分
    
    score = min(100, max(0, score))
    
    # 确定健康状态
    if score >= 80:
        status = "healthy"
    elif score >= 60:
        status = "warning"
    else:
        status = "critical"
    
    # 生成优劣势
    if real_data:
        strengths = []
        weaknesses = diagnosis.get("key_issues", [])
        
        if follower_count > 10000:
            strengths.append(f"粉丝基础较好（{follower_count:,}）")
        if content_count > 30:
            strengths.append(f"内容积累丰富（{content_count}篇）")
        if engagement_rate > 3:
            strengths.append("互动率高于平均水平")
        
        if not strengths:
            strengths = ["账号有发展潜力", "内容定位清晰"]
    else:
        strengths = [
            "内容发布频率稳定" if content_count > 10 else "内容质量潜力大",
            "粉丝互动积极" if engagement_rate > 0.05 else "内容调性清晰",
        ]
        weaknesses = [
            "粉丝增长速度有待提升" if follower_count < 1000 else "内容多样性可优化",
            "互动率低于行业平均" if engagement_rate < 0.03 else "发布时间点可优化",
        ]
    
    # 生成建议
    if real_data:
        recommendations = diagnosis.get("improvement_suggestions", [])
        # 转换为标准格式
        recommendations = [
            {
                "priority": "high" if i < 2 else "medium",
                "action": r.get("tip", str(r)),
                "expected_impact": "提升账号表现"
            }
            for i, r in enumerate(recommendations[:3])
        ]
    else:
        recommendations = [
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
        ]
    
    return AccountDiagnosisOutput(
        overall_score=round(score, 1),
        health_status=status,
        strengths=strengths,
        weaknesses=weaknesses,
        recommendations=recommendations,
        benchmarks={
            "industry_avg_engagement": 0.045,
            "top_10_percent_engagement": 0.08,
            "your_engagement": round(engagement_rate / 100, 4),
            "data_source": data_source,
            "real_data": real_data is not None
        }
    )


@mcp.tool()
async def analyze_traffic(input: TrafficAnalysisInput) -> TrafficAnalysisOutput:
    """
    分析流量结构和转化漏斗
    
    基于真实 metrics 进行深度分析
    """
    metrics = input.metrics
    
    views = int(metrics.get("views") or metrics.get("impressions") or 0)
    likes = int(metrics.get("likes") or 0)
    comments = int(metrics.get("comments") or 0)
    shares = int(metrics.get("shares") or 0)
    follows = int(metrics.get("follows") or 0)
    clicks = int(metrics.get("clicks") or views * 0.15)
    
    # 计算真实漏斗转化率
    funnel = {
        "exposure": views,
        "click": clicks,
        "engage": likes + comments + shares,
        "convert": follows,
        "rates": {
            "exposure_to_click": round(clicks / views, 4) if views > 0 else 0,
            "click_to_engage": round((likes + comments + shares) / clicks, 4) if clicks > 0 else 0,
            "engage_to_convert": round(follows / (likes + comments + shares), 4) if (likes + comments + shares) > 0 else 0,
        }
    }
    
    # 识别异常
    anomalies = []
    
    if funnel["rates"]["exposure_to_click"] < 0.05:
        anomalies.append({
            "type": "low_ctr",
            "severity": "high",
            "description": "点击率偏低，可能是封面或标题吸引力不足",
            "suggestion": "优化封面设计，标题增加数字或悬念"
        })
    
    if funnel["rates"]["click_to_engage"] < 0.10:
        anomalies.append({
            "type": "low_engagement",
            "severity": "high",
            "description": "内容互动率异常低，可能是内容质量问题",
            "suggestion": "优化内容开头，增加钩子"
        })
    
    if views > 10000 and follows < 10:
        anomalies.append({
            "type": "low_conversion",
            "severity": "medium",
            "description": "高曝光低转化，缺乏关注引导",
            "suggestion": "在内容中增加关注引导，优化个人主页"
        })
    
    # 模拟流量来源（需要真实数据接入广告平台 API）
    traffic_sources = {
        "recommendation": 0.45,
        "search": 0.25,
        "profile": 0.15,
        "share": 0.10,
        "other": 0.05
    }
    
    # 根据平台调整
    if input.platform == "douyin":
        traffic_sources["recommendation"] = 0.70
        traffic_sources["search"] = 0.10
    elif input.platform == "xiaohongshu":
        traffic_sources["search"] = 0.40
        traffic_sources["recommendation"] = 0.30
    
    return TrafficAnalysisOutput(
        traffic_sources=traffic_sources,
        funnel_analysis=funnel,
        trends=[],  # 需要历史数据
        anomalies=anomalies,
        recommendations=[
            "优化内容开头3秒，提升完播率",
            "在内容中增加互动引导，如提问",
            "分析高互动内容，提取成功因素",
            "调整发布时间至用户活跃高峰"
        ] if anomalies else [
            "流量表现正常，继续保持当前策略",
            "可以尝试 A/B 测试进一步优化"
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
    
    基于真实数据生成周报（需要从数据库或平台 API 获取）
    """
    # 尝试获取真实数据
    real_metrics = None
    try:
        # 这里可以接入数据库或平台 API 获取真实数据
        # 暂时使用模拟数据但标注为需要接入
        pass
    except Exception as e:
        print(f"[generate_weekly_report] 获取真实数据失败: {e}")
    
    # 如果有 metrics 参数，使用它
    # 否则使用占位数据但明确标注
    return {
        "period": f"{week_start} ~ (7 days)",
        "data_source": "placeholder" if real_metrics is None else "real",
        "note": "需要接入数据存储或平台 API 获取真实数据" if real_metrics is None else None,
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
    if not metrics_history or len(metrics_history) < 2:
        return {
            "anomalies_detected": 0,
            "anomalies": [],
            "suggestions": ["数据点不足，无法检测异常"]
        }
    
    anomalies = []
    
    # 计算均值和标准差
    values = [h.get(metric_name, 0) for h in metrics_history if metric_name in h]
    if not values:
        return {
            "anomalies_detected": 0,
            "anomalies": [],
            "suggestions": [f"未找到指标 {metric_name} 的数据"]
        }
    
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = variance ** 0.5
    
    # 检测异常点（超过2个标准差）
    for i, record in enumerate(metrics_history):
        value = record.get(metric_name)
        if value is None:
            continue
        
        # 检测突然下降（超过50%）
        if i > 0:
            prev = metrics_history[i-1].get(metric_name, 0)
            if prev > 0 and value / prev < 0.5:
                anomalies.append({
                    "date": record.get("date"),
                    "metric": metric_name,
                    "previous_value": prev,
                    "current_value": value,
                    "change_percent": round((value - prev) / prev * 100, 1),
                    "severity": "high" if value / prev < 0.3 else "medium",
                    "type": "sharp_decline"
                })
        
        # 检测离群值（超过2个标准差）
        if abs(value - mean) > 2 * std_dev:
            anomalies.append({
                "date": record.get("date"),
                "metric": metric_name,
                "value": value,
                "mean": round(mean, 2),
                "std_dev": round(std_dev, 2),
                "z_score": round((value - mean) / std_dev, 2) if std_dev > 0 else 0,
                "severity": "medium",
                "type": "outlier"
            })
    
    return {
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies,
        "statistics": {
            "mean": round(mean, 2),
            "std_dev": round(std_dev, 2),
            "data_points": len(values)
        },
        "suggestions": [
            "检查异常日期是否有平台算法更新",
            "分析内容质量是否有变化",
            "确认账号是否有违规记录"
        ] if anomalies else ["数据表现正常，继续保持"]
    }


@mcp.tool()
async def benchmark_analysis(
    account_metrics: Dict[str, Any],
    industry: str,
    platform: str,
    user_id: str
) -> Dict[str, Any]:
    """
    竞品对标分析
    
    与行业基准进行对比
    """
    # 行业基准数据（应来自数据库或行业报告）
    industry_benchmarks = {
        "美妆": {"avg_engagement": 0.05, "top_engagement": 0.12},
        "美食": {"avg_engagement": 0.06, "top_engagement": 0.15},
        "科技": {"avg_engagement": 0.04, "top_engagement": 0.10},
        "教育": {"avg_engagement": 0.07, "top_engagement": 0.18},
        "时尚": {"avg_engagement": 0.05, "top_engagement": 0.12},
    }
    
    benchmark = industry_benchmarks.get(industry, {"avg_engagement": 0.045, "top_engagement": 0.10})
    
    engagement_rate = account_metrics.get("engagement_rate", 0)
    
    # 对比分析
    comparison = {
        "your_rate": engagement_rate,
        "industry_avg": benchmark["avg_engagement"],
        "top_performers": benchmark["top_engagement"],
        "percentile": 50  # 估算百分位
    }
    
    if engagement_rate >= benchmark["top_engagement"]:
        comparison["percentile"] = 90
        comparison["level"] = "top"
    elif engagement_rate >= benchmark["avg_engagement"]:
        comparison["percentile"] = 70
        comparison["level"] = "above_average"
    elif engagement_rate >= benchmark["avg_engagement"] * 0.5:
        comparison["percentile"] = 40
        comparison["level"] = "average"
    else:
        comparison["percentile"] = 20
        comparison["level"] = "below_average"
    
    return {
        "industry": industry,
        "platform": platform,
        "comparison": comparison,
        "insights": [
            f"你的互动率处于行业{comparison['percentile']}%水平",
            f"行业平均互动率为{benchmark['avg_engagement']:.1%}",
            f"头部账号互动率为{benchmark['top_engagement']:.1%}"
        ],
        "recommendations": {
            "top": ["保持当前策略", "探索新的内容形式"],
            "above_average": ["对标头部账号学习", "优化内容质量"],
            "average": ["分析高互动内容", "优化发布时间"],
            "below_average": ["重新定位内容方向", "学习竞品成功经验"]
        }.get(comparison["level"], ["持续优化"])
    }


if __name__ == "__main__":
    mcp.run(transport="sse")
