"""格式化 TrendingRank 报告。"""

from __future__ import annotations

from typing import Any


def format_ranking_report(
    items: list[dict[str, Any]],
    keyword: str,
    platform: str,
    hot_keywords: list[str],
    expanded_keywords: list[str],
    data_source: str,
) -> str:
    """生成 Markdown 形式的爆款榜单报告。"""
    lines: list[str] = []
    lines.append(f"# 🔥 「{keyword}」爆款榜单")
    lines.append("")
    lines.append(f"**平台**：{platform} ｜ **数据来源**：{data_source}")
    lines.append("")

    if expanded_keywords:
        lines.append(f"**扩展关键词**：{', '.join(expanded_keywords)}")
        lines.append("")

    if not items:
        lines.append("暂无相关爆款数据，建议换个关键词或扩大时间窗口试试。")
        return "\n".join(lines)

    lines.append("| 排名 | 平台 | 标题 | 点赞 | 评论 | 收藏 | 转发 | 互动率 |")
    lines.append("|------|------|------|------|------|------|------|--------|")

    for idx, item in enumerate(items, start=1):
        metrics = item.get("metrics", {})
        title = item.get("title", "-")[:40]
        lines.append(
            f"| {idx} | {item.get('platform', '-')} | {title} | "
            f"{metrics.get('likes', 0)} | {metrics.get('comments', 0)} | "
            f"{metrics.get('collections', 0)} | {metrics.get('shares', 0)} | "
            f"{item.get('engagement_rate', 0):.2%} |"
        )

    lines.append("")
    if hot_keywords:
        lines.append(f"**趋势热词**：{', '.join(hot_keywords[:15])}")
        lines.append("")

    lines.append("**爆款特征摘要**：")
    lines.append("- 高互动内容通常具备强情绪钩子或实用价值；")
    lines.append("- 可结合扩展关键词进一步细化选题方向；")
    lines.append("- 建议优先参考互动率 > 5% 的内容结构。")

    return "\n".join(lines)
