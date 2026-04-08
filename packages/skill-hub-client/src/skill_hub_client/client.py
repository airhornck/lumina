"""中枢层调用 Layer 3（MCP Skill Hub）— 默认同进程直连工具实现。"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

ToolFn = Callable[..., Awaitable[Dict[str, Any]]]


class SkillHubClient:
    def __init__(self, registry: Dict[str, ToolFn] | None = None) -> None:
        if registry is not None:
            self._registry = dict(registry)
        else:
            from lumina_skills.registry import TOOL_REGISTRY

            self._registry = dict(TOOL_REGISTRY)

    async def call(self, skill_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        fn = self._registry.get(skill_name)
        if not fn:
            return {"ok": False, "error": f"unknown_skill:{skill_name}"}
        try:
            out = await fn(**params)
            return {"ok": True, "result": out}
        except TypeError as e:
            return {"ok": False, "error": f"bad_arguments:{e}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:500]}
