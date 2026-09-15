"""ContentPositionMatrix Skill 主入口。"""

from __future__ import annotations

import os
import re
from typing import Any

from orchestra.skills.content_position_matrix import scoring_engine
from orchestra.skills.content_position_matrix import matrix_plotter


def is_enabled() -> bool:
    return os.environ.get("LUMINA_ENABLE_CONTENT_POSITION_MATRIX_SKILL", os.environ.get("LUMINA_ENABLE_POSITIONING_MATRIX_SKILL", "true")).lower() in ("true", "1", "yes")


# 纯意图/求助表达，不含可被分析的内容主题。
# 注意：较长/较具体的短语必须放在前面，避免被更短的前缀抢先匹配。
_CLARIFICATION_ONLY_PATTERNS = re.compile(
    r"^("
    r"帮我分析一下|帮我分析下|帮我看看|帮我看一下|帮我诊断一下|帮我诊断下|"
    r"帮我定位一下|帮我定位下|帮我梳理一下|帮我梳理下|"
    r"请分析一下|请分析下|请看一下|请看|看一下|看看|分析下|诊断下|定位下|梳理下|"
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


def _extract_content(message: str) -> str:
    """从用户输入中提取要分析的内容文本。"""
    # 去掉触发词（保留内容定位兼容直接调用场景）
    cleaned = re.sub(
        r"定位矩阵|矩阵.*定位|用矩阵帮我梳理|梳理.*定位|内容定位",
        "",
        message,
        flags=re.I,
    ).strip()
    # 去掉开头标点
    cleaned = re.sub(r"^[：:，,\s]+", "", cleaned).strip()
    return cleaned or message


def _has_meaningful_content(content: str) -> bool:
    """判断提取后的内容是否包含可供矩阵分析的具体文本。"""
    if not content:
        return False
    # 反复去掉开头常见的纯求助/意图表达
    cleaned = content
    while True:
        new_cleaned = _CLARIFICATION_ONLY_PATTERNS.sub("", cleaned).strip()
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned
    # 过滤掉无意义的语气/量词残留
    if cleaned in {"一下", "一下下", "下", "的"}:
        return False
    # 至少剩下 3 个字符，才认为有具体主题
    return len(cleaned) >= 3


def _find_content_from_history(history: list[dict[str, str]]) -> str | None:
    """从历史对话中查找最近一条包含可分析内容的用户消息。"""
    for row in reversed(history):
        if row.get("role") == "user":
            candidate = _extract_content(row.get("content", ""))
            if _has_meaningful_content(candidate):
                return candidate
    return None


def _find_content_from_context(context: dict[str, Any]) -> str | None:
    """从上下文字段中查找待分析内容。"""
    for key in ("content_text", "content", "note_text", "note", "text"):
        value = context.get(key)
        if isinstance(value, str) and _has_meaningful_content(value):
            return _extract_content(value)
    return None


def _generate_differentiation_tips(quadrant: str, professional: float, entertainment: float) -> list[str]:
    tips: list[str] = []
    if quadrant == "知识干货区":
        tips.append("专业度足够，但娱乐度偏低：尝试在标题和前3行加入情绪钩子或悬念。")
        tips.append("可参考 viral 爆款区内容，增加对比型封面和互动引导。")
    elif quadrant == "娱乐消遣区":
        tips.append("娱乐度高，但专业度不足：可增加实用信息密度，提升长期价值。")
        tips.append("尝试「轻科普」形式，把笑点/爽点与知识点结合。")
    elif quadrant == "日常分享区":
        tips.append("专业度和娱乐度都偏低：建议先明确一个核心差异化标签。")
        tips.append("可从「痛点+解决方案」或「真实对比」两个方向切入。")
    else:  # viral爆款区
        tips.append("已处于高专业+高娱乐的爆款区，重点保持更新频率和复制成功结构。")
        tips.append("建议建立内容 SOP，把爆款因子固化到后续选题中。")

    if professional < 5:
        tips.append("增加数据、案例或步骤化结构，提升专业可信度。")
    if entertainment < 5:
        tips.append("在标题和开头增加情绪词、数字或冲突感，提升娱乐度。")

    return tips[:3]


async def run(
    message: str,
    platform: str | None,
    context: dict[str, Any],
    history: list[dict[str, str]],
    mode: str | None = None,
) -> str:
    """执行 ContentPositionMatrix Skill。"""
    if not is_enabled():
        return "定位矩阵功能暂时不可用。"

    content = _extract_content(message)
    source_hint = ""

    if not content or not _has_meaningful_content(content):
        # 尝试从历史对话或上下文中补齐
        historical = _find_content_from_history(history)
        contextual = _find_content_from_context(context)
        if historical:
            content = historical
            source_hint = "我将基于你**之前提供的内容**进行矩阵分析。"
        elif contextual:
            content = contextual
            source_hint = "我将基于**对话上下文中的内容**进行矩阵分析。"
        else:
            return (
                "我可以帮你做两类分析：\n"
                "1. **定位矩阵**：请提供一段具体的内容文本（标题+正文、笔记文案、"
                "视频脚本或链接），我会分析它的专业度/娱乐度象限。\n"
                "2. **账号定位策划**：请告诉我你想做哪个平台、什么赛道、目标受众是谁，"
                "我可以帮你做账号定位分析。\n\n"
                "你想从哪一类开始？"
            )

    professional = scoring_engine.score_professional(content)
    entertainment = scoring_engine.score_entertainment(content)
    intensity = scoring_engine.predict_engagement_intensity(professional, entertainment)
    quadrant = matrix_plotter.classify_quadrant(professional, entertainment)
    intensity_level = scoring_engine.classify_intensity_level(intensity)
    tips = _generate_differentiation_tips(quadrant, professional, entertainment)

    chart = matrix_plotter.render_ascii_matrix(professional, entertainment, intensity)

    lines: list[str] = []
    lines.append("# 📍 定位矩阵分析")
    lines.append("")
    lines.append(f"**分析内容**：{content[:80]}{'...' if len(content) > 80 else ''}")
    lines.append("")
    lines.append(chart)
    lines.append("")
    lines.append("## 定位诊断")
    lines.append(f"- 专业度：{professional:.1f}/10")
    lines.append(f"- 娱乐度：{entertainment:.1f}/10")
    lines.append(f"- 互动强度：{intensity:.1%}（{intensity_level}）")
    lines.append(f"- 所在象限：**{quadrant}**")
    lines.append("")
    lines.append("## 差异化建议")
    for tip in tips:
        lines.append(f"- {tip}")

    if source_hint:
        lines.append("")
        lines.append(f"> {source_hint} 如果你想分析其他内容，请直接告诉我。")

    return "\n".join(lines)
