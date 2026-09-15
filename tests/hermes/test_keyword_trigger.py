"""关键词直连触发测试（hermes_tools.KEYWORD_TOOL_TRIGGERS）。

约定：
- 命中关键词 → 跳过 planner 直接调用对应 skill，事件序列为
  start → tool_start → tool_complete → assistant_delta* → done；
- 用户原话/平台原样传入工具，回复照常写入记忆（不丢弃上下文）；
- 工具失败 → tool_complete(ok=False) + 自然语言致歉（护栏2）；
- mock 路径优先于关键词（测试构造不受影响）。
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.asyncio


async def _collect(adapter, message: str, platform: str | None = None):
    events = []
    async for line in adapter.chat_stream(
        user_message=message,
        user_id="u1",
        conversation_id="c1",
        session_history=[{"role": "user", "content": "之前的话"}],
        platform=platform,
        context={},
    ):
        for row in line.strip().split("\n"):
            if row.startswith("data: "):
                events.append(json.loads(row[6:]))
    return events


def _patch_tool(monkeypatch, payload: dict, capture: dict):
    async def fake_handle(tool_name, args, **kwargs):
        capture["tool_name"] = tool_name
        capture["args"] = args
        return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr("services.hermes_tools.handle_tool_call", fake_handle)


@pytest.mark.parametrize(
    "keyword,tool_name",
    [
        ("查爆款榜单", "lumina_content_ranking"),
        ("内容定位矩阵", "lumina_positioning_matrix"),
        ("生成本周快报", "lumina_weekly_snapshot"),
    ],
)
async def test_keyword_triggers_matching_tool(monkeypatch, keyword, tool_name):
    capture: dict = {}
    _patch_tool(monkeypatch, {"ok": True, "result": {"reply": "skill 结果"}}, capture)

    from services.hermes_adapter import HermesEngineAdapter

    appended: list[str] = []

    async def _append(text: str) -> None:
        appended.append(text)

    adapter = HermesEngineAdapter(append_assistant=_append)
    events = await _collect(adapter, f"帮我{keyword}看看", platform="douyin")

    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert "tool_start" in types and "tool_complete" in types
    assert types[-1] == "done"

    start_evt = next(e for e in events if e["type"] == "tool_start")
    assert start_evt["tool"] == tool_name
    # 上下文不丢弃：用户原话与平台原样传入
    assert capture["args"]["message"] == f"帮我{keyword}看看"
    assert capture["args"]["platform"] == "douyin"

    complete_evt = next(e for e in events if e["type"] == "tool_complete")
    assert complete_evt["ok"] is True

    reply = "".join(e["text"] for e in events if e["type"] == "assistant_delta")
    assert reply == "skill 结果"
    # 记忆照常写入
    assert appended == ["skill 结果"]


async def test_no_keyword_goes_planner_path(monkeypatch):
    capture: dict = {}
    _patch_tool(monkeypatch, {"ok": True, "result": {"reply": "x"}}, capture)

    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(mock_response="正常回复")
    events = await _collect(adapter, "你好")

    assert "tool_start" not in [e["type"] for e in events]
    assert "tool_name" not in capture
    reply = "".join(e["text"] for e in events if e["type"] == "assistant_delta")
    assert reply == "正常回复"


async def test_keyword_tool_failure_graceful(monkeypatch):
    capture: dict = {}
    _patch_tool(monkeypatch, {"ok": False, "error": "boom"}, capture)

    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter()
    events = await _collect(adapter, "查爆款榜单")

    complete_evt = next(e for e in events if e["type"] == "tool_complete")
    assert complete_evt["ok"] is False
    reply = "".join(e["text"] for e in events if e["type"] == "assistant_delta")
    assert "抱歉" in reply
    assert events[-1]["type"] == "done"


async def test_mock_response_takes_precedence_over_keyword(monkeypatch):
    capture: dict = {}
    _patch_tool(monkeypatch, {"ok": True, "result": {"reply": "x"}}, capture)

    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(mock_response="mock 回复")
    events = await _collect(adapter, "查爆款榜单")

    assert "tool_start" not in [e["type"] for e in events]
    assert "tool_name" not in capture
