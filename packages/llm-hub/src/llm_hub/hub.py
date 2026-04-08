"""LLMHub：池加载、按 skill/component 解析客户端。"""

from __future__ import annotations

from typing import Optional

from llm_hub.client import LLMClient
from llm_hub.config_models import LLMAssignment, LLMConfig, LLMHubConfig
from llm_hub.loader import build_llm_pool_from_raw, load_yaml_config


class LLMHub:
    def __init__(self, config: LLMHubConfig):
        self.config = config

    @classmethod
    def from_config_file(cls, path: str) -> "LLMHub":
        data = load_yaml_config(path)
        pool_raw = data.get("llm_pool") or {}
        built = build_llm_pool_from_raw(pool_raw)
        pool = {k: LLMConfig(**v) for k, v in built.items()}
        data["llm_pool"] = pool
        allowed = set(LLMHubConfig.model_fields.keys())
        filtered = {k: v for k, v in data.items() if k in allowed}
        return cls(LLMHubConfig(**filtered))

    def _resolve_assignment(
        self, component: Optional[str], skill_name: Optional[str]
    ) -> LLMAssignment:
        if skill_name and skill_name in self.config.skill_config:
            return self.config.skill_config[skill_name]
        if component and component in self.config.component_config:
            return self.config.component_config[component]
        return LLMAssignment(llm=self.config.default_llm)

    def _resolve_config(self, assignment: LLMAssignment) -> LLMConfig:
        if assignment.llm:
            if assignment.llm not in self.config.llm_pool:
                raise ValueError(f"Unknown llm '{assignment.llm}'")
            base = self.config.llm_pool[assignment.llm]
        elif self.config.default_llm in self.config.llm_pool:
            base = self.config.llm_pool[self.config.default_llm]
        else:
            raise ValueError("No default_llm in pool")
        if assignment.temperature is None and assignment.max_tokens is None:
            return base
        data = base.model_dump()
        if assignment.temperature is not None:
            data["temperature"] = assignment.temperature
        if assignment.max_tokens is not None:
            data["max_tokens"] = assignment.max_tokens
        return LLMConfig(**data)

    def get_client(
        self,
        *,
        component: Optional[str] = None,
        skill_name: Optional[str] = None,
        llm_name: Optional[str] = None,
    ) -> LLMClient:
        if llm_name:
            if llm_name not in self.config.llm_pool:
                raise ValueError(f"Unknown llm '{llm_name}'")
            cfg = self.config.llm_pool[llm_name]
        else:
            assignment = self._resolve_assignment(component, skill_name)
            cfg = self._resolve_config(assignment)
        return LLMClient(cfg)


_default_hub: Optional[LLMHub] = None


def init_default_hub(config_path: str) -> LLMHub:
    global _default_hub
    _default_hub = LLMHub.from_config_file(config_path)
    return _default_hub


def get_hub() -> Optional[LLMHub]:
    return _default_hub


def get_client(
    skill_name: Optional[str] = None,
    *,
    component: Optional[str] = None,
    llm_name: Optional[str] = None,
) -> Optional[LLMClient]:
    hub = get_hub()
    if not hub:
        return None
    return hub.get_client(
        skill_name=skill_name, component=component, llm_name=llm_name
    )
