from __future__ import annotations

from typing import Any, Dict, List


async def fetch_industry_news(
    category: str,
    days: int = 3,
    sources: List[str] | None = None,
) -> Dict[str, Any]:
    _ = days, sources
    return {
        "news_list": [
            {
                "title": f"{category} 行业周报（占位）",
                "summary": "热点与趋势为示例数据，后续接 RSS/API。",
                "heat_score": 0.62,
                "source": "placeholder",
                "url": "",
            }
        ],
        "hot_keywords": [category, "增长", "内容"],
        "trend_prediction": "短期热度平稳（占位）",
    }


async def monitor_competitor(
    account_id: str,
    platform: str,
    monitor_metrics: List[str] | None = None,
    user_id: str = "anonymous",
) -> Dict[str, Any]:
    _ = monitor_metrics
    return {
        "latest_contents": [],
        "performance_comparison": {"self": "n/a", "competitor": account_id},
        "content_gap_analysis": f"平台 {platform} 竞品监测占位，user={user_id}",
        "threat_level": "low",
    }


async def visualize_data(
    data: Dict[str, Any],
    chart_type: str,
    title: str,
    user_id: str = "anonymous",
) -> Dict[str, Any]:
    _ = data, chart_type
    return {
        "chart_url": "",
        "insights": [f"{title}：占位图表，类型={chart_type}"],
        "recommendations": ["接入图表服务后返回可访问 URL"],
        "user_id": user_id,
    }
