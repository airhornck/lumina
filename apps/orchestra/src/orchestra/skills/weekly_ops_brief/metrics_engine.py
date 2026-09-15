"""指标计算引擎：把原始内容指标聚合为周报可用数字。"""
from typing import Any


def engagement_rate(metrics: dict[str, int]) -> float:
    """互动率：加权互动 / 曝光。"""
    views = max(metrics.get("views", 1), 1)
    weighted = (
        metrics.get("likes", 0) * 1
        + metrics.get("comments", 0) * 2
        + metrics.get("collections", 0) * 1.5
        + metrics.get("shares", 0) * 3
    )
    return weighted / views


def avg_engagement_rate(contents: list[dict[str, Any]]) -> float:
    if not contents:
        return 0.0
    rates = [engagement_rate(item.get("metrics", {})) for item in contents]
    return sum(rates) / len(rates)


def viral_rate(contents: list[dict[str, Any]], threshold: float = 0.05) -> float:
    if not contents:
        return 0.0
    viral_count = sum(1 for item in contents if engagement_rate(item.get("metrics", {})) >= threshold)
    return viral_count / len(contents)


def fan_conversion_efficiency(stats: dict[str, int]) -> float:
    views = max(stats.get("total_views", 1), 1)
    return stats.get("new_followers", 0) / views


def aggregate_metrics(contents: list[dict[str, Any]], stats: dict[str, Any] | None = None) -> dict[str, Any]:
    stats = stats or {}
    total_views = stats.get("total_views", sum(item.get("metrics", {}).get("views", 0) for item in contents))
    total_interactions = sum(
        item.get("metrics", {}).get("likes", 0)
        + item.get("metrics", {}).get("comments", 0)
        + item.get("metrics", {}).get("collections", 0)
        + item.get("metrics", {}).get("shares", 0)
        for item in contents
    )
    return {
        "total_contents": len(contents),
        "total_views": total_views,
        "total_interactions": total_interactions,
        "avg_engagement_rate": avg_engagement_rate(contents),
        "viral_rate": viral_rate(contents),
        "fan_conversion_efficiency": fan_conversion_efficiency(stats),
        "new_followers": stats.get("new_followers", 0),
    }
