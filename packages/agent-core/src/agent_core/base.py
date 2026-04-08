"""多 Agent 协作骨架（Blackboard 后续可扩展）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    user_id: str = "anonymous"
    platform: str = "xiaohongshu"
    session_history: List[Dict[str, Any]] = Field(default_factory=list)
    blackboard: Dict[str, Any] = Field(default_factory=dict)


class BaseAgent:
    role: str = "base"

    def __init__(self, skill_hub_client: Any) -> None:
        self.skill_hub = skill_hub_client

    async def run_skill(
        self,
        skill_name: Optional[str],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not skill_name:
            return {"skipped": True}
        return await self.skill_hub.call(skill_name, params)
