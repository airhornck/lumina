"""Hermes Markdown Skill 加载器与方法论执行入口。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SKILL_DIR = Path(__file__).resolve().parents[4] / "data" / "hermes" / "skills" / "lumina-marketing"
_METHODOLOGY_DIR = Path(__file__).resolve().parents[4] / "data" / "methodologies"

# 白名单：允许执行的方法论
_METHODOLOGY_IDS = ("positioning", "hook_story_offer", "aida", "pas")


class ExecuteMethodologyInput(BaseModel):
    methodology: str = Field(..., description="方法论标识，如 positioning / hook_story_offer / aida / pas")
    user_input: str = Field(..., description="用户原始需求")
    platform: str | None = Field(default="xiaohongshu", description="目标平台")


def _load_methodology(methodology_id: str) -> Dict[str, Any] | None:
    """从 data/methodologies 加载方法论 YAML。"""
    path = _METHODOLOGY_DIR / f"{methodology_id}.yml"
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        data["id"] = methodology_id
        return data
    except Exception as e:
        logger.warning("Failed to load methodology %s: %s", methodology_id, e)
        return None


def list_methodologies() -> List[Dict[str, Any]]:
    """返回 Lumina 支持的方法论列表。"""
    results = []
    for mid in _METHODOLOGY_IDS:
        data = _load_methodology(mid)
        if data:
            results.append(
                {
                    "id": mid,
                    "name": data.get("name", mid),
                    "description": data.get("description", ""),
                    "category": data.get("category", ""),
                    "applicable_scenarios": data.get("applicable_scenarios", []),
                }
            )
    return results


def get_methodology(methodology_id: str) -> Dict[str, Any] | None:
    """获取指定方法论的完整定义。"""
    if methodology_id not in _METHODOLOGY_IDS:
        return None
    return _load_methodology(methodology_id)


def get_methodology_tool_schema() -> Dict[str, Any]:
    """返回 Hermes 工具 schema，用于 lumina_execute_methodology。"""
    return {
        "type": "function",
        "function": {
            "name": "lumina_execute_methodology",
            "description": "执行 Lumina 营销方法论（定位、钩子故事Offer、AIDA、PAS），按结构化流程生成营销内容或策略。",
            "parameters": ExecuteMethodologyInput.model_json_schema(),
        },
    }


async def handle_lumina_execute_methodology(
    args: Dict[str, Any],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> Dict[str, Any]:
    """处理 lumina_execute_methodology 工具调用。"""
    try:
        input_data = ExecuteMethodologyInput(**args)
    except Exception as e:
        return {"ok": False, "error": f"Invalid input: {e}"}

    methodology_id = input_data.methodology
    if methodology_id not in _METHODOLOGY_IDS:
        available = ", ".join(_METHODOLOGY_IDS)
        return {
            "ok": False,
            "error": f"Unknown methodology '{methodology_id}'. Available: {available}",
        }

    methodology = get_methodology(methodology_id)
    if methodology is None:
        return {"ok": False, "error": f"Methodology file for '{methodology_id}' not found"}

    steps = methodology.get("steps", [])
    steps_summary = [
        {"step_id": s.get("step_id", f"step-{i}"), "theory": s.get("theory", "")}
        for i, s in enumerate(steps)
    ]

    # 实际生产环境可在这里调用 lumina_generate_content 逐步生成；
    # 当前版本返回结构化执行计划，由 Hermes 按步骤继续调用其他 Lumina 工具。
    return {
        "ok": True,
        "methodology": methodology_id,
        "name": methodology.get("name", methodology_id),
        "user_input": input_data.user_input,
        "platform": input_data.platform,
        "steps_count": len(steps),
        "steps": steps_summary,
        "next_action": "按 steps 顺序调用 lumina_generate_content 生成每一步内容",
    }
