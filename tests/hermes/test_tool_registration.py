"""Phase 1 TDD Harness：Hermes 工具注册 Red 状态测试。"""

from __future__ import annotations

import json

import pytest


def test_lumina_generate_content_registered():
    from services.hermes_tools import get_lumina_tools

    tools = get_lumina_tools()
    names = [t["function"]["name"] for t in tools]
    assert "lumina_generate_content" in names


def test_generate_content_schema():
    from services.hermes_tools import get_lumina_tools

    tools = get_lumina_tools()
    tool = next(t for t in tools if t["function"]["name"] == "lumina_generate_content")
    params = tool["function"]["parameters"]["properties"]
    assert "topic" in params
    assert "platform" in params


@pytest.mark.asyncio
async def test_generate_content_handler_mock():
    from services.hermes_tools import handle_lumina_generate_content

    result = await handle_lumina_generate_content(
        {"topic": "夏季防晒", "platform": "xiaohongshu"}
    )
    data = json.loads(result)
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_tool_not_found():
    from services.hermes_tools import handle_tool_call

    result = await handle_tool_call("lumina_not_exist", {})
    data = json.loads(result)
    assert data["ok"] is False


@pytest.mark.asyncio
async def test_tool_exception_handled():
    from services.hermes_tools import handle_tool_call

    result = await handle_tool_call("lumina_generate_content", {})
    data = json.loads(result)
    # 缺少必要参数应该返回错误
    assert data["ok"] is False
