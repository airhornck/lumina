"""Phase 1/4 TDD Harness：Hermes 适配器 Hermes 调用路径 mock 测试。

Phase 4 P0 适配器重写后，mock 锚点从 ``_load_agent``/``agent.chat`` 迁移到
``_get_or_create_agent``/``agent.run_conversation``（spec §五 G2/G3）。
"""

from __future__ import annotations

import json
import threading
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.asyncio


async def _collect_sse(stream):
    events = []
    async for line in stream:
        line = line.strip()
        if line.startswith("data: "):
            data = line[6:]
            if data:
                events.append(json.loads(data))
    return events


def _make_mock_agent(final_response: str = "你好，我是 Lumina") -> MagicMock:
    mock_agent = MagicMock()
    mock_agent._turn_lock = threading.Lock()
    mock_agent.session_prompt_tokens = 0
    mock_agent.session_completion_tokens = 0
    mock_agent.session_total_tokens = 0
    mock_agent.run_conversation = MagicMock(
        return_value={"final_response": final_response}
    )
    return mock_agent


async def test_hermes_chat_with_real_agent_mock():
    from services.hermes_adapter import HermesEngineAdapter

    mock_agent = _make_mock_agent("你好，我是 Lumina")

    with patch.object(
        HermesEngineAdapter, "_get_or_create_agent", return_value=mock_agent
    ):
        adapter = HermesEngineAdapter(use_hermes=True)
        stream = adapter.chat_stream(
            user_message="你好",
            user_id="test-user",
            conversation_id="test-conv-mock-1",
            session_history=[],
        )
        events = await _collect_sse(stream)

    assert events[0]["type"] == "start"
    assert any(e["type"] == "assistant_delta" for e in events)
    assert events[-1]["type"] == "done"
    # run_conversation 被调用且携带 system/history 参数（G2/G4）
    _, kwargs = mock_agent.run_conversation.call_args
    assert "conversation_history" in kwargs
    assert "system_message" in kwargs


async def test_hermes_chat_with_history():
    from services.hermes_adapter import HermesEngineAdapter

    mock_agent = _make_mock_agent("收到")

    with patch.object(
        HermesEngineAdapter, "_get_or_create_agent", return_value=mock_agent
    ):
        adapter = HermesEngineAdapter(use_hermes=True)
        stream = adapter.chat_stream(
            user_message="继续",
            user_id="test-user",
            conversation_id="test-conv-mock-2",
            session_history=[
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "有什么可以帮你？"},
            ],
        )
        events = await _collect_sse(stream)

    assert events[-1]["type"] == "done"
    # 多轮历史真实注入 run_conversation（G2）
    _, kwargs = mock_agent.run_conversation.call_args
    history = kwargs["conversation_history"]
    assert history == [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "有什么可以帮你？"},
    ]


async def test_hermes_tool_registration_mock():
    from services.hermes_adapter import HermesEngineAdapter

    # 该测试依赖 hermes-agent 仓库的 tools.registry 模块，
    # 在缺少 hermes-agent 的环境中跳过。
    try:
        import tools.registry  # noqa: F401
    except ImportError:
        pytest.skip("hermes-agent tools.registry not available")

    mock_registry = MagicMock()

    with patch("tools.registry.registry", mock_registry):
        HermesEngineAdapter._tools_registered = False
        try:
            HermesEngineAdapter._register_lumina_tools()
        finally:
            HermesEngineAdapter._tools_registered = True
        # 验证 Lumina 工具被注册
        assert mock_registry.register.called


async def test_hermes_import_error_handled():
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True, mock_import_error=True)
    stream = adapter.chat_stream(
        user_message="你好",
        user_id="test-user",
        conversation_id="test-conv",
        session_history=[],
    )
    events = await _collect_sse(stream)

    assert any(e.get("type") == "error" for e in events)
