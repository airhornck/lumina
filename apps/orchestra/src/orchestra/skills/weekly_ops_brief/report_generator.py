"""3P 周报生成器。"""
from . import metrics_engine, trend_analyzer


def _fmt_number(n: int | float) -> str:
    if isinstance(n, float):
        return f"{n:.2%}"
    if n >= 10000:
        return f"{n / 10000:.1f}万"
    return str(n)


def _section_progress(data: dict) -> str:
    contents = data.get("contents", [])
    stats = data.get("stats", {})
    agg = metrics_engine.aggregate_metrics(contents, stats)
    lines = [
        "## 1. PROGRESS（本周表现）",
        f"- 发布量：{agg['total_contents']} 篇",
        f"- 总曝光：{_fmt_number(agg['total_views'])}",
        f"- 总互动：{_fmt_number(agg['total_interactions'])}",
        f"- 平均互动率：{agg['avg_engagement_rate']:.2%}",
        f"- 爆款率：{agg['viral_rate']:.0%}",
        f"- 粉丝净增：+{agg['new_followers']}",
        "",
        "### 内容类型表现矩阵",
        "| 内容类型 | 发布量 | 平均互动率 | 爆款数 |",
        "|----------|--------|------------|--------|",
    ]
    perf = trend_analyzer.content_type_performance(contents)
    for ctype, p in perf.items():
        lines.append(f"| {ctype} | {p['count']} | {p['avg_engagement_rate']:.2%} | {p['viral_count']} |")
    lines.append("")
    lines.append("### 本周 TOP3 爆款")
    for idx, item in enumerate(trend_analyzer.top_performers(contents, n=3), start=1):
        lines.append(f"{idx}. 《{item['title']}》 互动率 {item['engagement_rate']:.2%}")
    return "\n".join(lines)


def _section_problems(data: dict) -> str:
    contents = data.get("contents", [])
    problems = trend_analyzer.detect_problems(contents)
    lines = ["## 2. PROBLEMS（问题识别）"]
    for p in problems:
        lines.append(f"- {p}")
    return "\n".join(lines)


def _section_plans(data: dict) -> str:
    contents = data.get("contents", [])
    plans = trend_analyzer.generate_plans(contents)
    lines = ["## 3. PLANS（下周策略）"]
    for p in plans:
        lines.append(f"- {p}")
    return "\n".join(lines)


def render_3p_report(data: dict) -> str:
    header = "# 📊 每周决策快报\n\n"
    parts = [
        _section_progress(data),
        _section_problems(data),
        _section_plans(data),
    ]
    return header + "\n\n".join(parts)
