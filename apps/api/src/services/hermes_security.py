"""Hermes 安全策略与校验。"""

from __future__ import annotations

import os
from typing import Any, Dict, List


LUMINA_DISABLED_HERMES_TOOLSETS = [
    "terminal",
    "browser",
    "code_execution",
    "delegation",
    "computer_use",
    "messaging",
    "cronjob",
    "homeassistant",
    "discord",
    "discord_admin",
]

LUMINA_ENABLED_HERMES_TOOLSETS = ["lumina_marketing"]


def build_safe_hermes_config(
    enabled_toolsets: List[str] | None = None,
    disabled_toolsets: List[str] | None = None,
    max_iterations: int = 10,
) -> Dict[str, Any]:
    """构建安全的 Hermes 配置。"""
    env_enabled = os.environ.get("LUMINA_HERMES_ENABLED_TOOLSETS", "")
    if env_enabled:
        enabled = [t.strip() for t in env_enabled.split(",") if t.strip()]
    else:
        enabled = list(enabled_toolsets or LUMINA_ENABLED_HERMES_TOOLSETS)

    env_disabled = os.environ.get("LUMINA_HERMES_DISABLED_TOOLS", "")
    if env_disabled:
        disabled = [t.strip() for t in env_disabled.split(",") if t.strip()]
    else:
        disabled = list(disabled_toolsets or LUMINA_DISABLED_HERMES_TOOLSETS)

    # 确保 lumina_marketing 在白名单中
    if "lumina_marketing" not in enabled:
        enabled.append("lumina_marketing")

    # 确保危险工具在黑名单中
    for dangerous in LUMINA_DISABLED_HERMES_TOOLSETS:
        if dangerous not in disabled:
            disabled.append(dangerous)

    return {
        "enabled_toolsets": enabled,
        "disabled_toolsets": disabled,
        "max_iterations": max_iterations,
        "skip_memory": False,
        "skip_context_files": True,
        "quiet_mode": True,
    }


def validate_hermes_tools(toolsets: List[str]) -> None:
    """校验工具集配置是否安全。"""
    for toolset in toolsets:
        if toolset in LUMINA_DISABLED_HERMES_TOOLSETS:
            raise ValueError(f"Dangerous toolset '{toolset}' is not allowed in Lumina")
