"""每周决策快照 Skill（WeeklyOpsBrief）入口包装。"""

from __future__ import annotations

from typing import Any

from orchestra.skills.weekly_ops_brief import skill as _weekly_ops_brief_skill


def is_enabled() -> bool:
    return _weekly_ops_brief_skill.is_enabled()


async def run(
    message: str,
    platform: str | None,
    context: dict[str, Any],
    history: list[dict[str, str]],
) -> str:
    """执行每周决策快照 Skill，委托给 WeeklyOpsBrief 3P 报告引擎。"""
    return await _weekly_ops_brief_skill.run(message, platform, context, history)
