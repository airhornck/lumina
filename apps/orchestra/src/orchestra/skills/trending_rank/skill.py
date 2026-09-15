"""TrendingRank Skill 主入口。"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from llm_hub import get_client, get_hub

from orchestra.skills.trending_rank import redfox_client
from orchestra.skills.trending_rank import keyword_expand
from orchestra.skills.trending_rank import rank_engine
from orchestra.skills.trending_rank import format_report

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return os.environ.get("LUMINA_ENABLE_TRENDING_RANK_SKILL", os.environ.get("LUMINA_ENABLE_CONTENT_RANKING_SKILL", "true")).lower() in ("true", "1", "yes")


def _parse_platform(message: str) -> str:
    if re.search(r"抖音|douyin", message, re.I):
        return "douyin"
    if re.search(r"小红书|xiaohongshu", message, re.I):
        return "xiaohongshu"
    if re.search(r"B站|bilibili|哔哩哔哩", message, re.I):
        return "bilibili"
    return "multi"


# 纯意图/求助表达，不含可被查询的具体赛道或关键词。
# 注意：较长/较具体的短语必须放在前面，避免被更短的前缀抢先匹配。
_CLARIFICATION_ONLY_PATTERNS = re.compile(
    r"^("
    r"帮我查一下|帮我查下|帮我排一下|帮我排下|帮我找一下|帮我找下|"
    r"帮我看看|帮我看一下|帮我查|帮我排|帮我找|"
    r"请查一下|请查下|请排一下|请排下|请找一下|请找下|"
    r"看一下|看看|查下|查一下|排下|排一下|找下|找一下|"
    r"我?想?(要|做|来个?)|"
    r"能帮我|可以帮我|能不能帮我|可不可以帮我|"
    r"麻烦你|麻烦帮我|"
    r"帮我|请帮我|给我|帮我做|帮我整|帮我搞|"
    r"给我个|给我来|给我做|"
    r"搞个|整个|来一下|来份|"
    r"请|帮|来|做|想|要|能|可以|能不能|可不可以"
    r")?\s*[：:，,\s]*",
    re.I,
)


def _parse_keyword(message: str) -> str:
    # 简单提取关键词：去掉常见触发词后的剩余内容
    cleaned = re.sub(
        r"查爆款榜单|查爆款|抖音热门|小红书爆款|B站trending|全网热点|热门内容|趋势榜单|"
        r"排行|TOP内容|热门视频|热门笔记|内容方向榜单|排一下方向|TOP.?方向|方向优先级|"
        r"内容方向怎么选|帮我排.*方向|方向.*排序|内容方向.*排名|的|一下",
        "",
        message,
        flags=re.I,
    ).strip()
    # 去掉末尾标点
    cleaned = re.sub(r"[？?。！!，,]$", "", cleaned).strip()
    return cleaned


def _has_meaningful_keyword(keyword: str) -> bool:
    """判断提取后的关键词是否包含可供查询的具体赛道/主题。"""
    if not keyword:
        return False
    # 反复去掉开头常见的纯求助/意图表达
    cleaned = keyword
    while True:
        new_cleaned = _CLARIFICATION_ONLY_PATTERNS.sub("", cleaned).strip()
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned
    # 过滤掉无意义的语气/量词残留
    if cleaned in {"一下", "一下下", "下", "的"}:
        return False
    # 至少剩下 2 个字符，才认为有具体主题
    return len(cleaned) >= 2


def _find_keyword_from_history(history: list[dict[str, str]]) -> str | None:
    """从历史对话中查找最近一条包含可查询关键词的用户消息。"""
    for row in reversed(history):
        if row.get("role") == "user":
            candidate = _parse_keyword(row.get("content", ""))
            if _has_meaningful_keyword(candidate):
                return candidate
    return None


def _find_keyword_from_context(context: dict[str, Any]) -> str | None:
    """从上下文字段中查找查询关键词。"""
    for key in ("keyword", "topic", "niche", "query", "theme"):
        value = context.get(key)
        if isinstance(value, str) and _has_meaningful_keyword(value):
            return _parse_keyword(value)
    return None


def _parse_time_window(message: str) -> str:
    if re.search(r"24小时|24h|今天|今日", message, re.I):
        return "24h"
    if re.search(r"30天|30d|一个月", message, re.I):
        return "30d"
    return "7d"


def _parse_sort_by(message: str) -> str:
    if re.search(r"按点赞|点赞最多|最多赞", message, re.I):
        return "likes"
    if re.search(r"按评论|评论最多", message, re.I):
        return "comments"
    if re.search(r"按收藏|收藏最多", message, re.I):
        return "collections"
    if re.search(r"按转发|转发最多", message, re.I):
        return "shares"
    return "engagement"


async def _fallback_llm_summary(keyword: str, platform: str, history: list[dict[str, str]]) -> str:
    """无真实数据时，使用 LLM 生成通用榜单摘要。"""
    hub = get_hub()
    if not hub:
        return f"暂无「{keyword}」的实时爆款数据，请配置 REDFOX_API_KEY 或 RPA 模块后重试。"

    client = get_client(skill_name="debug_chat")
    if not client or not client.config.api_key:
        return f"暂无「{keyword}」的实时爆款数据，请配置 REDFOX_API_KEY 或 RPA 模块后重试。"

    system = f"""你是 Lumina「爆款榜单」助手。当前无法获取「{keyword}」的实时数据，请基于行业通用趋势生成一份简要榜单框架，并明确告知用户数据为模拟示例。"""
    messages = [{"role": "system", "content": system}]
    for row in history[-5:]:
        if row.get("role") in ("user", "assistant") and isinstance(row.get("content"), str):
            messages.append({"role": row["role"], "content": row["content"]})
    messages.append({"role": "user", "content": f"请生成「{keyword}」在 {platform} 的爆款榜单框架"})

    pieces: list[str] = []
    async for piece in client.stream_completion(messages):
        pieces.append(piece)
    return "".join(pieces)


async def run(
    message: str,
    platform: str | None,
    context: dict[str, Any],
    history: list[dict[str, str]],
) -> str:
    """执行 TrendingRank Skill。"""
    if not is_enabled():
        return "爆款榜单功能暂时不可用，你可以先描述你的赛道和目标人群，我用通用对话方式帮你分析。"

    keyword = _parse_keyword(message)
    source_hint = ""

    if not _has_meaningful_keyword(keyword):
        historical = _find_keyword_from_history(history)
        contextual = _find_keyword_from_context(context)
        if historical:
            keyword = historical
            source_hint = f"我将基于你**之前提到的「{historical}」**查询爆款榜单。"
        elif contextual:
            keyword = contextual
            source_hint = f"我将基于**对话上下文中的「{contextual}」**查询爆款榜单。"
        else:
            return (
                "我可以帮你查爆款榜单或内容方向优先级。请告诉我你想查哪个赛道/关键词"
                "（例如：美妆、护肤、健身、职场、母婴等），以及目标平台"
                "（小红书/抖音/B站，可选）。"
            )

    target_platform = platform or _parse_platform(message)
    time_window = _parse_time_window(message)
    sort_by = _parse_sort_by(message)
    limit = min(int(context.get("limit", 10)), 50)

    # 关键词泛化
    expanded = await keyword_expand.expand_keywords(keyword)

    # 优先 Redfox
    client = redfox_client.RedfoxClient()
    all_items: list[dict[str, Any]] = []
    data_source = "llm_only"
    hot_keywords: list[str] = []

    if client.is_configured():
        primary_keyword = expanded[0] if expanded else keyword
        result = await client.fetch_trending(
            keyword=primary_keyword,
            platform=target_platform,
            time_window=time_window,
            limit=limit * 3,
        )
        if result.get("ok") and result.get("items"):
            all_items = result["items"]
            data_source = "redfox"
            hot_keywords = result.get("hot_keywords", [])

    # Redfox 失败且无数据：尝试 RPA fetch_trending_topics
    if not all_items:
        try:
            from lumina_skills.tool_skills import fetch_trending_topics

            platforms_to_fetch = [target_platform] if target_platform != "multi" else ["douyin", "xiaohongshu", "bilibili"]
            for pf in platforms_to_fetch:
                try:
                    rpa_result = await fetch_trending_topics(pf, category="general", limit=limit)
                    if rpa_result and rpa_result.get("topics"):
                        for t in rpa_result["topics"][:limit]:
                            all_items.append({
                                "title": t.get("title", ""),
                                "platform": pf,
                                "author": t.get("author", ""),
                                "url": t.get("url", ""),
                                "metrics": {
                                    "likes": t.get("likes", 0),
                                    "comments": t.get("comments", 0),
                                    "collections": t.get("collections", 0),
                                    "shares": t.get("shares", 0),
                                    "views": t.get("views", 0),
                                },
                            })
                        data_source = "rpa_crawler"
                except Exception as e:
                    logger.warning("RPA fetch_trending_topics failed for %s: %s", pf, e)
        except Exception as e:
            logger.warning("RPA module not available: %s", e)

    if not all_items:
        summary = await _fallback_llm_summary(keyword, target_platform, history)
        if source_hint:
            summary += f"\n\n> {source_hint} 如果你想查其他赛道/关键词，请告诉我。"
        return summary

    # 去重 + 排序
    unique_items = rank_engine.deduplicate_items(all_items)
    ranked_items = rank_engine.rank_items(unique_items, sort_by=sort_by)[:limit]

    # 若 Redfox 未返回热词，从标题中提取
    if not hot_keywords:
        hot_keywords = _extract_hot_keywords(ranked_items, expanded)

    report = format_report.format_ranking_report(
        items=ranked_items,
        keyword=keyword,
        platform=target_platform,
        hot_keywords=hot_keywords,
        expanded_keywords=expanded,
        data_source=data_source,
    )
    if source_hint:
        report += f"\n\n> {source_hint} 如果你想查其他赛道/关键词，请告诉我。"
    return report


def _extract_hot_keywords(items: list[dict[str, Any]], expanded: list[str]) -> list[str]:
    """简单热词提取：从标题中统计高频 2-4 字词。"""
    from collections import Counter

    text = " ".join(item.get("title", "") for item in items)
    words: list[str] = []
    for length in (4, 3, 2):
        for i in range(len(text) - length + 1):
            word = text[i : i + length]
            if any(kw in word for kw in expanded):
                words.append(word)
    counter = Counter(words)
    return [w for w, _ in counter.most_common(10)]
