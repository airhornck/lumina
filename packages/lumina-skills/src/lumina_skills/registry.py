"""MCP Skill Hub 工具注册表 — 名称与 FastMCP / SkillHubClient 一致。"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from lumina_skills.assets import match_cases, qa_knowledge, retrieve_methodology
from lumina_skills.content import generate_script, generate_text, select_topic
from lumina_skills.diagnosis import analyze_traffic, detect_risk, diagnose_account
from lumina_skills.tool_skills import fetch_industry_news, monitor_competitor, visualize_data, fetch_trending_topics

# 导出工具函数
from lumina_skills.llm_utils import call_llm, stream_llm, build_prompt, get_prompt_template

TOOL_REGISTRY: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
    "diagnose_account": diagnose_account,
    "analyze_traffic": analyze_traffic,
    "detect_risk": detect_risk,
    "generate_text": generate_text,
    "generate_script": generate_script,
    "select_topic": select_topic,
    "retrieve_methodology": retrieve_methodology,
    "match_cases": match_cases,
    "qa_knowledge": qa_knowledge,
    "fetch_industry_news": fetch_industry_news,
    "monitor_competitor": monitor_competitor,
    "visualize_data": visualize_data,
}


def register_all_tools(mcp: Any) -> None:
    for fn in TOOL_REGISTRY.values():
        mcp.add_tool(fn)
