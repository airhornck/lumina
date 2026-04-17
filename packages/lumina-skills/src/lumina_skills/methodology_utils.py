"""
方法论库统一工具：为所有 Skill 提供标准化的方法论查询与 Prompt 注入。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from knowledge_base.methodology_registry import MethodologyRegistry


def resolve_methodology(
    query: str,
    industry: str = "",
    goal: str = "",
    registry: MethodologyRegistry | None = None,
) -> Optional[Dict[str, Any]]:
    """
    根据查询词/行业/目标，从方法论库中匹配最合适的方法论。
    返回字典包含可直接注入 prompt 的字段。
    """
    reg = registry or MethodologyRegistry()
    m = reg.find_best_match(query, industry=industry, goal=goal)
    if not m:
        return None
    return {
        "methodology_id": m.methodology_id,
        "name": m.name,
        "steps": m.steps,
        "prompt_templates": m.prompt_templates,
        "applicable_scenarios": m.applicable_scenarios,
        "success_cases": m.case_studies,
    }


def build_methodology_prompt(methodology_id: str, registry: MethodologyRegistry | None = None) -> str:
    """
    构建可直接拼接到 LLM prompt 中的方法论指导文本。
    """
    reg = registry or MethodologyRegistry()
    try:
        m = reg.load(methodology_id)
    except Exception:
        return ""

    lines: List[str] = [f"方法论框架：{m.name}（{m.methodology_id}）"]

    if m.prompt_templates:
        lines.append("结构模板：")
        for key, tmpl in m.prompt_templates.items():
            lines.append(f"  - {key}: {tmpl}")

    if m.steps:
        lines.append("执行步骤：")
        for step in m.steps:
            sid = step.get("step_id", "")
            theory = step.get("theory", "")
            role = step.get("agent_role", "")
            line = f"  - {sid}"
            if theory:
                line += f"（理论：{theory}）"
            if role:
                line += f"[角色：{role}]"
            lines.append(line)

    if m.case_studies:
        lines.append(f"成功案例：{', '.join(m.case_studies)}")

    if m.applicable_scenarios:
        lines.append(f"适用场景：{', '.join(m.applicable_scenarios)}")

    return "\n".join(lines)


def list_available_methodologies(registry: MethodologyRegistry | None = None) -> List[str]:
    """返回当前可用的所有 methodology_id 列表。"""
    reg = registry or MethodologyRegistry()
    return reg.list_ids()


def match_methodology_for_content(topic: str, content_type: str = "post") -> Optional[str]:
    """
    根据内容主题和类型，快速匹配一个推荐的方法论 ID。
    这是规则 + 轻语义匹配的简化版，可被 LLM 替代或增强。
    """
    t = (topic or "").lower()

    # 故事/成长/经历 -> StoryArc
    if any(k in t for k in ["故事", "经历", "成长", "反转", "ip", "人设"]):
        return "story_arc"

    # 热点/节日/借势 -> TrendRide
    if any(k in t for k in ["热点", "节日", "借势", "挑战", "跟拍", "话题"]):
        return "trend_ride"

    # 转化/引流/产品/课程 -> HookStoryOffer 或 PAS
    if any(k in t for k in ["转化", "引流", "产品", "课程", "offer", "销售"]):
        return "hook_story_offer"

    # 痛点/避坑/解决 -> PAS
    if any(k in t for k in ["痛点", "避坑", "解决", "教程", "怎么做", "如何"]):
        return "pas_framework"

    # 品牌/定位/差异化/口号 -> BigIdea
    if any(k in t for k in ["品牌", "定位", "差异化", "口号", "包装", "slogan"]):
        return "big_idea"

    # 科普/知识/解释 -> WhatWhyHow
    if any(k in t for k in ["科普", "知识", "解释", "是什么", "为什么"]):
        return "what_why_how"

    # 默认 AIDA
    return "aida_advanced"
