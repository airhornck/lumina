"""Phase 4 P1 单元测试：业务事件桥接（export_link / compliance_report）。

对应 docs/specs/phase4_unified_planner_deprecation_spec.md §4.4：
工具结果中的 export_urls/compliance 必须转换为 SSE 业务事件，
done.payload 按规则追加 has_content/content_urls/compliance。
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


_TOOL_RESULT = json.dumps(
    {
        "ok": True,
        "result": {},
        "export_urls": [
            {
                "url": "/static/content/2026-07-15/abc123/xiaohongshu.html",
                "platform": "xiaohongshu",
                "variant": "图文",
                "title": "平价奶茶推荐",
                "summary": "一篇小红书笔记",
                "platform_required_content": None,
            }
        ],
        "compliance": {
            "risk_level": "medium",
            "risk_categories": ["superlative"],
            "violations": [{"term": "最好", "category": "superlative"}],
            "suggestion": "删除或改写敏感词",
            "report_md": "",
        },
    },
    ensure_ascii=False,
)


def _make_agent_emitting_business_result() -> MagicMock:
    mock_agent = MagicMock()
    mock_agent._turn_lock = threading.Lock()
    mock_agent.session_prompt_tokens = 0
    mock_agent.session_completion_tokens = 0
    mock_agent.session_total_tokens = 0

    def _fake_run(message, system_message=None, conversation_history=None):
        mock_agent.tool_start_callback("c1", "lumina_generate_content", {"topic": "奶茶"})
        mock_agent.tool_complete_callback(
            "c1", "lumina_generate_content", {}, _TOOL_RESULT
        )
        return {"final_response": "已为你生成笔记"}

    mock_agent.run_conversation = MagicMock(side_effect=_fake_run)
    return mock_agent


async def test_export_link_and_compliance_report_events():
    from services.hermes_adapter import HermesEngineAdapter

    mock_agent = _make_agent_emitting_business_result()

    with patch.object(
        HermesEngineAdapter, "_get_or_create_agent", return_value=mock_agent
    ):
        adapter = HermesEngineAdapter(use_hermes=True)
        stream = adapter.chat_stream(
            user_message="帮我写一篇小红书笔记",
            user_id="u1",
            conversation_id="conv-biz-1",
            session_history=[],
        )
        events = await _collect_sse(stream)

    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert types[-1] == "done"

    # 事件顺序：export_link 与 compliance_report 出现在 done 之前、start 之后
    export_events = [e for e in events if e["type"] == "export_link"]
    assert len(export_events) == 1
    ev = export_events[0]
    assert ev["url"] == "/static/content/2026-07-15/abc123/xiaohongshu.html"
    assert ev["format"] == "html"
    assert ev["platform"] == "xiaohongshu"
    assert ev["title"] == "平价奶茶推荐"
    assert "platform_required_content" in ev

    comp_events = [e for e in events if e["type"] == "compliance_report"]
    assert len(comp_events) == 1
    ce = comp_events[0]
    assert ce["risk_level"] == "medium"
    assert ce["risk_categories"] == ["superlative"]
    assert ce["violations"] == [{"term": "最好", "category": "superlative"}]
    assert ce["suggestion"] == "删除或改写敏感词"
    assert ce["format"] == "markdown"
    assert "report_md" in ce

    # 顺序断言：assistant_delta* → export_link → compliance_report → done
    last_delta = max(i for i, t in enumerate(types) if t == "assistant_delta")
    assert types.index("export_link") > last_delta
    assert types.index("compliance_report") > types.index("export_link")

    # done.payload 追加规则
    done = events[-1]
    assert done["payload"]["has_content"] is True
    assert len(done["payload"]["content_urls"]) == 1
    assert done["payload"]["compliance"]["risk_level"] == "medium"


async def test_no_business_events_for_plain_chat():
    """纯对话无业务事件，done.payload 为空 dict（§4.4 追加规则不触发）。"""
    from services.hermes_adapter import HermesEngineAdapter

    mock_agent = MagicMock()
    mock_agent._turn_lock = threading.Lock()
    mock_agent.session_prompt_tokens = 0
    mock_agent.session_completion_tokens = 0
    mock_agent.session_total_tokens = 0
    mock_agent.run_conversation = MagicMock(return_value={"final_response": "你好"})

    with patch.object(
        HermesEngineAdapter, "_get_or_create_agent", return_value=mock_agent
    ):
        adapter = HermesEngineAdapter(use_hermes=True)
        stream = adapter.chat_stream(
            user_message="你好",
            user_id="u1",
            conversation_id="conv-biz-2",
            session_history=[],
        )
        events = await _collect_sse(stream)

    types = [e["type"] for e in events]
    assert "export_link" not in types
    assert "compliance_report" not in types
    assert events[-1]["payload"] == {}
