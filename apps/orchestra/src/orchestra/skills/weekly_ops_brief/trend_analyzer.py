"""趋势分析引擎：识别问题与策略。"""
from collections import defaultdict
from . import metrics_engine


def content_type_performance(contents: list[dict]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in contents:
        ctype = item.get("content_type", "其他") or "其他"
        grouped[ctype].append(item)
    return {
        ctype: {
            "count": len(items),
            "avg_engagement_rate": metrics_engine.avg_engagement_rate(items),
            "viral_count": sum(1 for item in items if metrics_engine.engagement_rate(item.get("metrics", {})) >= 0.05),
        }
        for ctype, items in grouped.items()
    }


def top_performers(contents: list[dict], n: int = 3) -> list[dict]:
    scored = [
        {"title": item.get("title", "无标题"), "engagement_rate": metrics_engine.engagement_rate(item.get("metrics", {}))}
        for item in contents
    ]
    scored.sort(key=lambda x: x["engagement_rate"], reverse=True)
    return scored[:n]


def detect_problems(contents: list[dict]) -> list[str]:
    if not contents:
        return ["本周暂无数据，无法识别问题。"]
    problems = []
    overall_avg = metrics_engine.avg_engagement_rate(contents)
    perf = content_type_performance(contents)
    for ctype, data in perf.items():
        if overall_avg > 0 and data["avg_engagement_rate"] < overall_avg * 0.7:
            problems.append(f"{ctype} 类内容平均互动率低于整体水平，建议减少或优化。")
    if overall_avg < 0.03:
        problems.append("整体互动率偏低，建议复盘选题与封面吸引力。")
    if not problems:
        problems.append("本周未发现明显问题，继续保持。")
    return problems


def generate_plans(contents: list[dict]) -> list[str]:
    if not contents:
        return ["建议先接入数据源，再生成真实周报。"]
    perf = content_type_performance(contents)
    if not perf:
        return ["建议补充内容数据后制定下周策略。"]
    best_type = max(perf.items(), key=lambda x: x[1]["avg_engagement_rate"])
    worst_type = min(perf.items(), key=lambda x: x[1]["avg_engagement_rate"])
    plans = [
        f"选题：继续加码「{best_type[0]}」类内容，复制爆款公式。",
        f"暂停/减少「{worst_type[0]}」类低效内容，测试新的表达形式。",
    ]
    high_collection_items = [
        item for item in contents
        if item.get("metrics", {}).get("collections", 0) / max(item.get("metrics", {}).get("views", 1), 1) >= 0.10
    ]
    if high_collection_items:
        plans.append(f"对 {len(high_collection_items)} 条高收藏内容追加加热，提升曝光。")
    tops = top_performers(contents, n=1)
    if tops:
        plans.append(f"围绕本周 TOP1 爆款「{tops[0]['title']}」做系列化/切片二次传播。")
    return plans
