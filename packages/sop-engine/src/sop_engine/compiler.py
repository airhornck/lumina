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
        nodes.append(
            {
                "id": step.get("step_id") or f"step_{i}",
                "agent_role": step.get("agent_role") or "strategy",
                "skill": sc.get("name"),
                "params": sc.get("params") or {},
                "theory": step.get("theory"),
            }
        )
    return nodes
