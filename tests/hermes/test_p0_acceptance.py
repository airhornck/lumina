"""Phase 4 P0 验收测试（真实 LLM，消耗 token）。

对应 docs/specs/phase4_unified_planner_deprecation_spec.md §六 P0 验收标准：
- E1 闲聊零工具调用，自然回复
- E3 明确执行请求触发工具调用且过程事件可见（thinking/tool_start/tool_complete）
- 多轮对话不失忆（G2 历史注入生效）
- SSE 事件契约符合 §4.4（start 首发、done 收尾、含 usage/reply_ms/payload）

运行方式：
    set -a && . ./.env && set +a
    LUMINA_RUN_REAL_LLM=1 python -m pytest tests/hermes/test_p0_acceptance.py -q
"""

from __future__ import annotations

import json
import os

import pytest

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.real_llm,
    pytest.mark.skipif(
        os.environ.get("LUMINA_RUN_REAL_LLM") != "1",
        reason="真实 LLM 验收需 LUMINA_RUN_REAL_LLM=1",
    ),
    pytest.mark.skipif(
        not os.environ.get("DEEPSEEK_API_KEY"),
        reason="缺少 DEEPSEEK_API_KEY",
    ),
]


async def _collect(stream):
    events = []
    async for line in stream:
        line = line.strip()
        if line.startswith("data: "):
            data = line[6:]
            if data:
                events.append(json.loads(data))
    return events


def _assert_contract(events):
    assert events[0]["type"] == "start", f"首事件应为 start: {events[0]}"
    assert events[0].get("stream_format") == 2
    assert events[-1]["type"] == "done", f"末事件应为 done: {events[-1]}"
    done = events[-1]
    for key in ("service", "request_id", "full_length", "conversation_id", "usage", "reply_ms", "payload"):
        assert key in done, f"done 缺少字段 {key}"
    # §4.4：新事件只允许出现在 start 与 done 之间
    for e in events[1:-1]:
        assert e["type"] in (
            "assistant_delta",
            "thinking_delta",
            "tool_start",
            "tool_complete",
            "export_link",
            "compliance_report",
            "error",
        ), f"未知事件类型: {e['type']}"


def _reply_text(events) -> str:
    return "".join(e.get("text", "") for e in events if e["type"] == "assistant_delta")


async def _chat(adapter, conv_id, user_id, history, message):
    stream = adapter.chat_stream(
        user_message=message,
        user_id=user_id,
        conversation_id=conv_id,
        session_history=history,
    )
    events = await _collect(stream)
    _assert_contract(events)
    reply = _reply_text(events)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    return events, reply


async def test_p0_e1_greeting_no_tool_call():
    """E1：闲聊 → 零工具调用，自然回复。"""
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True)
    events, reply = await _chat(adapter, "p0-e1", "p0-user", [], "你好")

    tool_events = [e for e in events if e["type"] in ("tool_start", "tool_complete")]
    assert not tool_events, f"闲聊不应触发工具: {tool_events}"
    assert reply.strip(), "应有自然语言回复"
    print(f"\n[E1] reply={reply[:120]}")


async def test_p0_e3_topic_request_triggers_tool():
    """E3：明确执行请求 → 可见工具调用过程。

    planner 可能先 clarify（合规行为），最多推进 3 轮直至执行。
    """
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True)
    history = []
    tool_starts = []
    reply = ""
    events = []
    for msg in (
        "我在抖音做职场干货账号，帮我推荐几个最近值得做的选题方向",
        "不用再确认了，直接调用工具给我选题",
        "调用 lumina_recommend_topics 给我选题",
    ):
        events, reply = await _chat(adapter, "p0-e3", "p0-user", history, msg)
        tool_starts = [e for e in events if e["type"] == "tool_start"]
        if tool_starts:
            break

    assert tool_starts, f"3 轮内应触发至少一次工具调用，最后回复: {reply[:150]}"
    called = [e["tool"] for e in tool_starts]
    print(f"\n[E3] tools={called} reply={reply[:120]}")
    completes = [e for e in events if e["type"] == "tool_complete"]
    assert len(completes) == len(tool_starts), "每个 tool_start 应有 tool_complete"
    assert reply.strip(), "工具执行后应有自然语言总结"


async def test_p0_multi_turn_memory():
    """多轮不失忆：第 3 轮能回忆起第 1 轮提供的信息（G2）。"""
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True)
    history = []
    conv = "p0-memory"

    await _chat(adapter, conv, "p0-user", history, "我叫阿豪，今年22岁，在抖音做个人账号")
    await _chat(adapter, conv, "p0-user", history, "我的目标观众是年轻人")
    events, reply = await _chat(
        adapter, conv, "p0-user", history, "我叫什么名字？我在哪个平台创作？"
    )

    print(f"\n[MEMORY] reply={reply[:200]}")
    assert "阿豪" in reply, f"未回忆起名字: {reply[:200]}"
    assert "抖音" in reply, f"未回忆起平台: {reply[:200]}"
