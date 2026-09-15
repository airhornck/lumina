"""Phase 1 TDD Harness：Hermes 记忆提供器 Red 状态测试。"""

from __future__ import annotations

import json

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def provider():
    from services.hermes_memory_provider import LuminaMemoryProvider

    return LuminaMemoryProvider()


async def test_provider_name(provider):
    assert provider.name == "lumina"


async def test_provider_is_available(provider):
    assert provider.is_available() is True


async def test_tool_schemas(provider):
    schemas = provider.get_tool_schemas()
    assert any(s["function"]["name"] == "lumina_search_memory" for s in schemas)


async def test_handle_search_memory(provider):
    # 先通过 sync_turn 写入记忆
    await provider.sync_turn(
        user_content="夏季防晒",
        assistant_content="收到",
        session_id="test-conv",
        messages=[],
        user_id="test-user",
    )

    result = await provider.handle_tool_call(
        "lumina_search_memory",
        {"query": "防晒"},
        session_id="test-conv",
        user_id="test-user",
    )
    data = json.loads(result)
    assert data["ok"] is True
    assert "防晒" in str(data["result"])


async def test_sync_turn_writes_memory(provider):
    await provider.sync_turn(
        user_content="你好",
        assistant_content="有什么可以帮你？",
        session_id="test-conv-2",
        messages=[],
        user_id="test-user",
    )

    result = await provider.handle_tool_call(
        "lumina_search_memory",
        {"query": "你好"},
        session_id="test-conv-2",
        user_id="test-user",
    )
    data = json.loads(result)
    assert any("你好" in str(m) for m in data["result"])


async def test_session_isolation(provider):
    await provider.sync_turn(
        user_content="会话 A",
        assistant_content="收到",
        session_id="conv-a",
        messages=[],
        user_id="test-user",
    )

    result = await provider.handle_tool_call(
        "lumina_search_memory",
        {"query": "会话 A"},
        session_id="conv-b",
        user_id="test-user",
    )
    data = json.loads(result)
    assert not any("会话 A" in str(m) for m in data["result"])
