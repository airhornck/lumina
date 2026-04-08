"""LLM Hub 配置模型（与 DEVELOPMENT_PLAN 两步配置法一致）。"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    name: str
    provider: Literal["openai", "anthropic", "deepseek", "qwen", "custom"]
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 120
    tags: List[str] = Field(default_factory=list)


class LLMAssignment(BaseModel):
    llm: Optional[str] = None
    strategy: Optional[
        Literal["cost_aware", "quality_first", "latency_first", "round_robin"]
    ] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class LLMHubConfig(BaseModel):
    llm_pool: Dict[str, LLMConfig] = Field(default_factory=dict)
    default_llm: str = "default"
    default_strategy: Literal[
        "cost_aware", "quality_first", "latency_first", "round_robin"
    ] = "cost_aware"
    component_config: Dict[str, LLMAssignment] = Field(default_factory=dict)
    skill_config: Dict[str, LLMAssignment] = Field(default_factory=dict)
    fallback_enabled: bool = True
    fallback_order: List[str] = Field(default_factory=list)
