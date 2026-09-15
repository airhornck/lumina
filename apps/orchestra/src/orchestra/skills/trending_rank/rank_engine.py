"""排序与去重引擎。"""

from __future__ import annotations

import difflib
from typing import Any


def calculate_engagement_rate(item: dict[str, Any]) -> float:
    """计算综合互动率。"""
    metrics = item.get("metrics", {})
    likes = int(metrics.get("likes", 0) or 0)
    comments = int(metrics.get("comments", 0) or 0)
    collections = int(metrics.get("collections", 0) or 0)
    shares = int(metrics.get("shares", 0) or 0)
    views = int(metrics.get("views", 0) or 0)

    if views <= 0:
        # 无 views 时估算：likes × 10
        views = max(likes * 10, 1)

    return (likes * 1 + comments * 3 + collections * 2 + shares * 4) / views


def _title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a or "", b or "").ratio()


def deduplicate_items(items: list[dict[str, Any]], threshold: float = 0.85) -> list[dict[str, Any]]:
    """基于标题相似度去重，保留互动率最高的一条。"""
    if not items:
        return []

    # 先计算互动率
    for item in items:
        item["engagement_rate"] = calculate_engagement_rate(item)

    # 按互动率降序排序
    sorted_items = sorted(items, key=lambda x: x.get("engagement_rate", 0), reverse=True)

    result: list[dict[str, Any]] = []
    for item in sorted_items:
        title = item.get("title", "")
        is_duplicate = any(_title_similarity(title, existing.get("title", "")) >= threshold for existing in result)
        if not is_duplicate:
            result.append(item)

    return result


def rank_items(items: list[dict[str, Any]], sort_by: str = "engagement") -> list[dict[str, Any]]:
    """按指定维度排序。"""
    for item in items:
        if "engagement_rate" not in item:
            item["engagement_rate"] = calculate_engagement_rate(item)

    if sort_by == "likes":
        def key(x):
            return x.get("metrics", {}).get("likes", 0)
    elif sort_by == "comments":
        def key(x):
            return x.get("metrics", {}).get("comments", 0)
    elif sort_by == "collections":
        def key(x):
            return x.get("metrics", {}).get("collections", 0)
    elif sort_by == "shares":
        def key(x):
            return x.get("metrics", {}).get("shares", 0)
    else:
        def key(x):
            return x.get("engagement_rate", 0)

    return sorted(items, key=key, reverse=True)
