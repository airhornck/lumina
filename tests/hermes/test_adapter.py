"""Phase 1 TDD Harness：Hermes 引擎适配器 Red 状态测试。"""

from __future__ import annotations

import json

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


async def test_hermes_to_sse_start():
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True, mock_response="你好")
    stream = adapter.chat_stream(
        user_message="你好",
        user_id="test-user",
        conversation_id="test-conv",
        session_history=[],
    )
    events = await _collect_sse(stream)
    assert events[0]["type"] == "start"


async def test_hermes_to_sse_delta():
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True, mock_response="你好")
    stream = adapter.chat_stream(
        user_message="你好",
        user_id="test-user",
        conversation_id="test-conv",
        session_history=[],
    )
    events = await _collect_sse(stream)
    delta_events = [e for e in events if e["type"] == "assistant_delta"]
    assert len(delta_events) > 0


async def test_hermes_to_sse_done():
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True, mock_response="你好")
    stream = adapter.chat_stream(
        user_message="你好",
        user_id="test-user",
        conversation_id="test-conv",
        session_history=[],
    )
    events = await _collect_sse(stream)
    assert events[-1]["type"] == "done"


async def test_hermes_disabled_raises():
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=False)
    with pytest.raises(RuntimeError):
        async for _ in adapter.chat_stream(
            user_message="你好",
            user_id="test-user",
            conversation_id="test-conv",
            session_history=[],
        ):
            pass


async def test_hermes_not_installed_returns_error():
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True, mock_import_error=True)
    stream = adapter.chat_stream(
        user_message="你好",
        user_id="test-user",
        conversation_id="test-conv",
        session_history=[],
    )
    events = await _collect_sse(stream)
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) > 0


async def test_hermes_exception_returns_error():
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True, mock_exception=True)
    stream = adapter.chat_stream(
        user_message="你好",
        user_id="test-user",
        conversation_id="test-conv",
        session_history=[],
    )
    events = await _collect_sse(stream)
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) > 0
