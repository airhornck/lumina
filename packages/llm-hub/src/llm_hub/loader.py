"""YAML 加载与环境变量展开 ${VAR:-default}。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Union

import yaml

_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::(-?)([^}]*))?\}")


def expand_env_value(value: Union[str, Any]) -> Any:
    if not isinstance(value, str):
        return value

    def repl(m: re.Match[str]) -> str:
        key, has_dash, default = m.group(1), m.group(2), m.group(3)
        if key in os.environ and os.environ[key] != "":
            return os.environ[key]
        if default is not None:
            return default
        return os.environ.get(key, "")

    return _ENV_PATTERN.sub(repl, value)


def expand_env_tree(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: expand_env_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand_env_tree(x) for x in obj]
    return expand_env_value(obj)


def load_yaml_config(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return expand_env_tree(raw)


def build_llm_pool_from_raw(pool_raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, cfg in (pool_raw or {}).items():
        if not isinstance(cfg, dict):
            continue
        entry = dict(cfg)
        entry["name"] = name
        out[name] = entry
    return out
