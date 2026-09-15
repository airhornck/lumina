"""对话日志测试：写入/查询 roundtrip + adapter 链路落日志。"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.asyncio


def test_log_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMINA_CHAT_LOG_DIR", str(tmp_path))
    from services.conversation_log import log_turn, query_logs

    log_turn({"user_id": "u1", "conversation_id": "c1", "path": "planner", "reply": "你好"})
    log_turn({"user_id": "u2", "conversation_id": "c1", "path": "keyword", "reply": "榜单"})
    log_turn({"user_id": "u1", "conversation_id": "c2", "path": "planner", "reply": "嗯"})

    assert len(query_logs()) == 3
    assert len(query_logs(user_id="u1")) == 2
    by_conv = query_logs(user_id="u1", conversation_id="c2")
    assert len(by_conv) == 1 and by_conv[0]["reply"] == "嗯"
    assert query_logs(date="1999-01-01") == []


async def test_adapter_mock_turn_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMINA_CHAT_LOG_DIR", str(tmp_path))
    from services.hermes_adapter import HermesEngineAdapter
    from services.conversation_log import query_logs

    adapter = HermesEngineAdapter(mock_response="测试回复")
    events = []
    async for line in adapter.chat_stream(
        user_message="你好",
        user_id="log-u",
        conversation_id="log-c",
        session_history=[{"role": "user", "content": "之前"}],
    ):
        events.append(line)

    logs = query_logs(user_id="log-u")
    assert len(logs) == 1
    rec = logs[0]
    assert rec["path"] == "mock"
    assert rec["user_message"] == "你好"
    assert rec["reply"] == "测试回复"
    assert rec["history_len"] == 1
    assert rec["conversation_id"] == "log-c"
    assert "reply_ms" in rec and "request_id" in rec


async def test_adapter_keyword_turn_logged_with_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMINA_CHAT_LOG_DIR", str(tmp_path))

    async def fake_handle(tool_name, args, **kwargs):
        return json.dumps({"ok": True, "result": {"reply": "榜单结果"}}, ensure_ascii=False)

    monkeypatch.setattr("services.hermes_tools.handle_tool_call", fake_handle)

    from services.hermes_adapter import HermesEngineAdapter
    from services.conversation_log import query_logs

    adapter = HermesEngineAdapter()
    async for _ in adapter.chat_stream(
        user_message="查爆款榜单",
        user_id="log-u2",
        conversation_id="log-c2",
        session_history=[],
        platform="douyin",
    ):
        pass

    logs = query_logs(user_id="log-u2")
    assert len(logs) == 1
    rec = logs[0]
    assert rec["path"] == "keyword"
    assert rec["platform"] == "douyin"
    assert len(rec["tools"]) == 1
    assert rec["tools"][0]["name"] == "lumina_content_ranking"
    assert rec["tools"][0]["ok"] is True
    assert rec["tools"][0]["args"]["platform"] == "douyin"
    assert rec["reply"] == "榜单结果"


async def test_adapter_error_turn_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("LUMINA_CHAT_LOG_DIR", str(tmp_path))
    from services.hermes_adapter import HermesEngineAdapter
    from services.conversation_log import query_logs

    adapter = HermesEngineAdapter(mock_exception=True)
    async for _ in adapter.chat_stream(
        user_message="你好", user_id="log-u3", conversation_id="log-c3", session_history=[]
    ):
        pass

    logs = query_logs(user_id="log-u3")
    assert len(logs) == 1
    assert "error" in logs[0]
