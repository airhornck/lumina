from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class Methodology:
    methodology_id: str
    name: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    prompt_templates: Dict[str, str] = field(default_factory=dict)
    case_studies: List[str] = field(default_factory=list)
    applicable_scenarios: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> Methodology:
        mid = str(config.get("methodology_id") or config.get("id") or "")
        return cls(
            methodology_id=mid,
            name=str(config.get("name") or mid),
            steps=list(config.get("steps") or []),
            prompt_templates=dict(config.get("prompt_templates") or {}),
            case_studies=list(config.get("success_cases") or config.get("case_studies") or []),
            applicable_scenarios=list(config.get("applicable_scenarios") or []),
            raw=config,
        )


@dataclass
class PlatformSpec:
    platform_id: str
    content_dna: List[Dict[str, Any]] = field(default_factory=list)
    audit_rules: List[Dict[str, Any]] = field(default_factory=list)
    content_formats: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> PlatformSpec:
        pid = str(config.get("platform_id") or config.get("id") or "")
        return cls(
            platform_id=pid,
            content_dna=list(config.get("content_dna") or []),
            audit_rules=list(config.get("audit_rules") or []),
            content_formats=dict(config.get("content_formats") or {}),
            raw=config,
        )


def repo_root_from_here(depth: int = 4) -> Path:
    return Path(__file__).resolve().parents[depth]
