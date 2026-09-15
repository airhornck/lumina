"""Phase 2 TDD Harness：Hermes Markdown Skill 测试。"""

from __future__ import annotations

import pytest


def test_skill_file_exists():
    from pathlib import Path

    skill_path = Path("data/hermes/skills/lumina-marketing/SKILL.md")
    assert skill_path.exists(), "Markdown Skill 文件必须存在"
    content = skill_path.read_text(encoding="utf-8")
    assert "---" in content, "必须包含 frontmatter"
    assert "name:" in content, "frontmatter 必须包含 name"


def test_methodology_list():
    from services.hermes_markdown_skill import list_methodologies

    methodologies = list_methodologies()
    names = [m["id"] for m in methodologies]
    for expected in ("positioning", "hook_story_offer", "aida", "pas"):
        assert expected in names, f"方法论 {expected} 必须在列表中"


def test_methodology_steps():
    from services.hermes_markdown_skill import get_methodology

    positioning = get_methodology("positioning")
    assert positioning is not None
    assert len(positioning.get("steps", [])) >= 1


def test_skill_tool_schema():
    from services.hermes_markdown_skill import get_methodology_tool_schema

    schema = get_methodology_tool_schema()
    props = schema["function"]["parameters"]["properties"]
    assert "methodology" in props
    assert "user_input" in props


@pytest.mark.asyncio
async def test_handler_mock():
    from services.hermes_markdown_skill import handle_lumina_execute_methodology

    result = await handle_lumina_execute_methodology(
        {"methodology": "positioning", "user_input": "帮我做品牌定位", "platform": "xiaohongshu"}
    )
    assert result["ok"] is True
    assert "positioning" in result["methodology"]
