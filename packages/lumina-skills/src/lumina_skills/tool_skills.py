"""
工具类 Skills - 接入真实外部 API
"""

from __future__ import annotations

import os
import aiohttp
from typing import Any, Dict, List, Optional


async def fetch_industry_news(
    category: str,
    days: int = 3,
    sources: List[str] | None = None,
) -> Dict[str, Any]:
    """
    获取行业新闻
    
    尝试从多个真实新闻源获取数据
    """
    news_list = []
    
    # 尝试 NewsAPI (需要 API key)
    api_key = os.getenv("NEWSAPI_KEY")
    if api_key:
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": category,
                    "language": "zh",
                    "sortBy": "publishedAt",
                    "pageSize": 5,
                    "apiKey": api_key,
                }
                
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get("articles", [])
                        
                        for article in articles[:5]:
                            news_list.append({
                                "title": article.get("title", ""),
                                "summary": article.get("description", ""),
                                "url": article.get("url", ""),
                                "source": article.get("source", {}).get("name", "NewsAPI"),
                                "published_at": article.get("publishedAt", ""),
                                "heat_score": 0.75,
                            })
        except Exception as e:
            print(f"[fetch_industry_news] NewsAPI 失败: {e}")
    
    # 如果没有获取到新闻，尝试其他源或使用占位数据
    if not news_list:
        # 尝试 RSS 源（可以扩展）
        pass
    
    # 如果仍然没有，使用结构化占位数据但标注
    if not news_list:
        return {
            "news_list": [
                {
                    "title": f"{category} 行业最新动态",
                    "summary": "请配置 NEWSAPI_KEY 环境变量以获取真实新闻",
                    "url": "",
                    "heat_score": 0.62,
                    "source": "placeholder",
                    "note": "需要配置 NEWSAPI_KEY 获取真实数据"
                }
            ],
            "hot_keywords": [category, "增长", "内容", "营销"],
            "trend_prediction": "需要真实数据支持",
            "data_source": "placeholder"
        }
    
    # 提取热词
    hot_keywords = _extract_keywords([n["title"] for n in news_list[:3]])
    
    return {
        "news_list": news_list,
        "hot_keywords": hot_keywords if hot_keywords else [category, "增长", "内容"],
        "trend_prediction": f"{category}领域近期关注度{'较高' if len(news_list) > 3 else '平稳'}",
        "data_source": "newsapi" if api_key else "mixed"
    }


def _extract_keywords(titles: List[str]) -> List[str]:
    """从标题中提取关键词"""
    # 简单的关键词提取
    stop_words = {"的", "了", "是", "在", "和", "与", "对", "为", "有", "被", "将", "及"}
    word_freq = {}
    
    for title in titles:
        words = title.split()
        for word in words:
            word = word.strip("，。！？；：\"'").lower()
            if len(word) > 1 and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
    
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [w[0] for w in sorted_words[:5]]


async def monitor_competitor(
    account_id: str,
    platform: str,
    monitor_metrics: List[str] | None = None,
    user_id: str = "anonymous",
) -> Dict[str, Any]:
    """
    监控竞品
    
    使用 RPA 抓取竞品最新动态
    """
    try:
        from rpa.skill_utils import get_rpa_helper
        
        rpa = get_rpa_helper()
        
        # 构建竞品账号 URL
        platform_urls = {
            "douyin": f"https://www.douyin.com/user/{account_id}",
            "xiaohongshu": f"https://www.xiaohongshu.com/user/profile/{account_id}",
        }
        
        account_url = platform_urls.get(platform)
        if not account_url:
            return {
                "competitor_id": account_id,
                "platform": platform,
                "error": f"不支持的平台: {platform}",
                "latest_contents": [],
                "performance_comparison": {},
            }
        
        result = await rpa.crawl_account(
            account_url=account_url,
            platform=platform,
            account_id=account_id,
            user_id=user_id,
            max_contents=10,
        )
        
        if result.success:
            data = result.data
            recent_contents = data.get("recent_contents", [])
            
            return {
                "competitor_id": account_id,
                "platform": platform,
                "monitored_at": data.get("crawled_at"),
                "latest_contents": [
                    {
                        "title": c.get("title", "")[:50],
                        "likes": c.get("likes") or c.get("likes_text", 0),
                        "platform": c.get("platform", platform)
                    }
                    for c in recent_contents[:5]
                ],
                "performance_comparison": {
                    "competitor_followers": data.get("followers"),
                    "competitor_likes": data.get("likes"),
                    "competitor_content_count": data.get("content_count"),
                },
                "content_gap_analysis": f"竞品最新{len(recent_contents)}条内容已分析",
                "data_source": "rpa_crawler",
            }
        else:
            return {
                "competitor_id": account_id,
                "platform": platform,
                "error": result.error,
                "latest_contents": [],
                "note": "RPA 抓取失败，请检查账号是否可访问"
            }
            
    except Exception as e:
        return {
            "competitor_id": account_id,
            "platform": platform,
            "error": str(e),
            "latest_contents": [],
            "note": "需要配置 RPA 模块"
        }


async def visualize_data(
    data: Dict[str, Any],
    chart_type: str,
    title: str,
    user_id: str = "anonymous",
) -> Dict[str, Any]:
    """
    可视化数据
    
    生成图表（可以接入图表库或生成 ECharts 配置）
    """
    # 生成 ECharts 配置
    echarts_config = _generate_echarts_config(data, chart_type, title)
    
    return {
        "chart_type": chart_type,
        "title": title,
        "echarts_config": echarts_config,
        "insights": _generate_chart_insights(data, chart_type),
        "recommendations": [
            "在支持 ECharts 的页面中渲染图表",
            "或使用配置生成图片"
        ]
    }


def _generate_echarts_config(data: Dict[str, Any], chart_type: str, title: str) -> Dict[str, Any]:
    """生成 ECharts 配置"""
    if chart_type == "line":
        return {
            "title": {"text": title},
            "xAxis": {"type": "category", "data": list(data.keys())},
            "yAxis": {"type": "value"},
            "series": [{"data": list(data.values()), "type": "line"}]
        }
    elif chart_type == "bar":
        return {
            "title": {"text": title},
            "xAxis": {"type": "category", "data": list(data.keys())},
            "yAxis": {"type": "value"},
            "series": [{"data": list(data.values()), "type": "bar"}]
        }
    elif chart_type == "pie":
        pie_data = [{"name": k, "value": v} for k, v in data.items()]
        return {
            "title": {"text": title},
            "series": [{"type": "pie", "data": pie_data}]
        }
    else:
        return {"title": {"text": title}, "series": []}


def _generate_chart_insights(data: Dict[str, Any], chart_type: str) -> List[str]:
    """生成图表洞察"""
    insights = []
    
    if not data:
        return ["数据为空，无法生成洞察"]
    
    values = list(data.values())
    if values and all(isinstance(v, (int, float)) for v in values):
        max_val = max(values)
        min_val = min(values)
        avg_val = sum(values) / len(values)
        
        insights.append(f"最大值: {max_val}")
        insights.append(f"最小值: {min_val}")
        insights.append(f"平均值: {avg_val:.2f}")
        
        # 趋势分析
        if len(values) > 1:
            if values[-1] > values[0]:
                insights.append("整体呈上升趋势")
            elif values[-1] < values[0]:
                insights.append("整体呈下降趋势")
            else:
                insights.append("趋势相对平稳")
    
    return insights


async def fetch_trending_topics(
    platform: str,
    category: str = "general",
    limit: int = 10,
) -> Dict[str, Any]:
    """
    获取热门话题
    
    使用 RPA 抓取平台热门
    """
    try:
        from rpa.skill_utils import get_rpa_helper
        
        rpa = get_rpa_helper()
        result = await rpa.fetch_platform_data(
            platform=platform,
            data_type="hot_topics",
            account_id="system",
        )
        
        if result.success:
            topics = result.data.get("hot_topics", [])[:limit]
            return {
                "platform": platform,
                "category": category,
                "topics": topics,
                "fetched_at": result.data.get("fetched_at"),
                "data_source": "rpa_crawler"
            }
        else:
            return {
                "platform": platform,
                "category": category,
                "topics": [],
                "error": result.error,
                "note": "抓取失败"
            }
            
    except Exception as e:
        return {
            "platform": platform,
            "category": category,
            "topics": [],
            "error": str(e),
            "note": "需要配置 RPA 模块"
        }
