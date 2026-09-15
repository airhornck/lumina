"""WeeklyOpsBrief Skill：多源数据聚合 + 3P 周报生成。"""
import asyncio
import os
from typing import Any
from . import report_generator

def is_enabled() -> bool:
    return os.environ.get("LUMINA_ENABLE_WEEKLY_SNAPSHOT_SKILL", "true").lower() in ("true", "1", "yes")


def _collect_data(context: dict[str, Any]) -> dict[str, Any]:
    """收集周报数据：优先 context.metrics，其次空数据。"""
    metrics = context.get("metrics")
    if _has_usable_metrics(metrics):
        return metrics
    return {"contents": [], "stats": {}}


def _has_usable_metrics(metrics: Any) -> bool:
    """判断 context.metrics 中是否包含可生成周报的真实运营数据。"""
    if not isinstance(metrics, dict):
        return False
    contents = metrics.get("contents")
    if isinstance(contents, list) and len(contents) > 0:
        return True
    stats = metrics.get("stats")
    if isinstance(stats, dict) and stats:
        return True
    return False


def _build_prompt(report: str) -> str:
    return (
        "你是一名资深内容运营顾问。请基于以下 3P 周报数据，生成一份面向决策者的中文周报。"
        "保持结构完整、结论清晰、可执行。不要编造数据中不存在的数字。\n\n"
        f"{report}"
    )


def _call_llm_sync(prompt: str, report: str) -> str:
    """同步调用 LLM；若 llm_hub 不可用则返回原始报告。"""
    try:
        from llm_hub import get_client  # type: ignore[import-not-found]
        client = get_client()
        if client is None:
            return report
        return client.chat.completions.create(
            model=os.environ.get("DEFAULT_LLM_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        ).choices[0].message.content
    except Exception:
        return report


async def run(message: str, platform: str | None, context: dict[str, Any], history: list[dict[str, str]]) -> str:
    if not is_enabled():
        return "每周决策快报功能已临时关闭。"
    if not _has_usable_metrics(context.get("metrics")):
        return (
            "生成每周决策快报需要你的真实运营数据（至少包括本周发布的内容列表和基础指标，"
            "如阅读量、点赞、评论、收藏、涨粉数等）。\n"
            "请提供以下任一方式：\n"
            "1. 授权我读取你的账号后台数据；\n"
            "2. 上传包含内容数据和指标的文件/截图；\n"
            "3. 提供具体的账号主页链接，让我先进行数据采集。\n\n"
            "你方便用哪种方式？"
        )
    data = _collect_data(context)
    report = report_generator.render_3p_report(data)
    prompt = _build_prompt(report)
    result = await asyncio.to_thread(_call_llm_sync, prompt, report)
    source_hint = (
        "> 本次周报基于你**已提供的运营数据**生成。"
        "如果你想基于其他账号或时间段的数据生成周报，请重新提供或授权。"
    )
    return result + "\n\n" + source_hint


def run_sync(message: str, platform: str | None, context: dict[str, Any], history: list[dict[str, str]]) -> str:
    return asyncio.run(run(message, platform, context, history))
