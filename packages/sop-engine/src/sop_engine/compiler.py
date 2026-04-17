"""SOP 编排：方法论 + 平台规范 → 线性 DAG 节点列表（骨架，可扩展条件分支）。"""

from __future__ import annotations

from typing import Any, Dict, List

from knowledge_base.methodology_registry import MethodologyRegistry
from knowledge_base.platform_registry import PlatformRegistry


def compile_methodology_dag(
    methodology_id: str,
    platform_id: str,
    methodology_lib: MethodologyRegistry | None = None,
    platform_lib: PlatformRegistry | None = None,
) -> List[Dict[str, Any]]:
    mlib = methodology_lib or MethodologyRegistry()
    plib = platform_lib or PlatformRegistry()
    try:
        meth = mlib.load(methodology_id)
    except FileNotFoundError:
        return []
    _ = plib.load(platform_id)
    nodes: List[Dict[str, Any]] = []
    for i, step in enumerate(meth.steps):
        sc = step.get("skill_call") or {}
        params = dict(sc.get("params") or {})

        # 注入方法论的 prompt_templates（按 step_id 匹配）
        step_id = step.get("step_id") or f"step_{i}"
        if meth.prompt_templates and step_id in meth.prompt_templates:
            params["methodology_prompt_template"] = meth.prompt_templates[step_id]

        # 同时注入整体方法论名称与可用模板全集，供下游 Skill 使用
        params.setdefault("methodology_id", meth.methodology_id)
        if meth.prompt_templates:
            params.setdefault("methodology_prompt_templates", meth.prompt_templates)

        nodes.append(
            {
                "id": step_id,
                "agent_role": step.get("agent_role") or "strategy",
                "skill": sc.get("name"),
                "params": params,
                "theory": step.get("theory"),
                "methodology_name": meth.name,
            }
        )
    return nodes
