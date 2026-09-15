"""Phase 1 TDD Harness：Hermes 安全加固 Red 状态测试。"""

from __future__ import annotations

import pytest


def test_disabled_toolsets_include_terminal():
    from services.hermes_security import LUMINA_DISABLED_HERMES_TOOLSETS

    assert "terminal" in LUMINA_DISABLED_HERMES_TOOLSETS


def test_disabled_toolsets_include_browser():
    from services.hermes_security import LUMINA_DISABLED_HERMES_TOOLSETS

    assert "browser" in LUMINA_DISABLED_HERMES_TOOLSETS


def test_disabled_toolsets_include_code_execution():
    from services.hermes_security import LUMINA_DISABLED_HERMES_TOOLSETS

    assert "code_execution" in LUMINA_DISABLED_HERMES_TOOLSETS


def test_safe_hermes_config():
    from services.hermes_security import build_safe_hermes_config

    config = build_safe_hermes_config()
    assert "terminal" not in config["enabled_toolsets"]
    assert "browser" not in config["enabled_toolsets"]
    assert "code_execution" not in config["enabled_toolsets"]
    assert "lumina_marketing" in config["enabled_toolsets"]
    assert config["max_iterations"] <= 10


def test_validate_hermes_tools_rejects_dangerous():
    from services.hermes_security import validate_hermes_tools

    with pytest.raises(ValueError):
        validate_hermes_tools(["terminal", "lumina_marketing"])


def test_validate_hermes_tools_accepts_safe():
    from services.hermes_security import validate_hermes_tools

    # 不应抛错
    validate_hermes_tools(["lumina_marketing", "web", "clarify"])
