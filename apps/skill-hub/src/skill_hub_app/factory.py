"""Layer 3：MCP Skill Hub（FastMCP）— 与 lumina_skills 共用工具表。"""

from __future__ import annotations

from fastmcp import FastMCP

from lumina_skills.registry import register_all_tools


def build_skill_hub_mcp() -> FastMCP:
    mcp = FastMCP(
        "marketing_skill_hub",
        instructions="Lumina 营销原子能力：诊断 / 内容 / 资产 / 工具四类 Skill。",
    )
    register_all_tools(mcp)
    return mcp
