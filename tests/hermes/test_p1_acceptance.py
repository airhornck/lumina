"""Phase 4 P1 验收测试（真实 LLM，消耗 token）。

对应 docs/specs/phase4_unified_planner_deprecation_spec.md §六 P1 验收标准：
- 选题/风控/诊断/文案四类用例在 hermes 路径全部完成（四桩已接通）
- 用户明说"抖音"时工具实参 platform == "douyin"（上下文抽取，非硬编码）
- 内容生成用例产出 export_link 事件且 URL 文件可访问、done.payload.has_content=true
- compliance_report 事件字段与 §4.4 一致

运行方式：
    set -a && . ./.env && set +a
    LUMINA_RUN_REAL_LLM=1 python -m pytest tests/hermes/test_p1_acceptance.py -q
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


def _reply_text(events) -> str:
    return "".join(e.get("text", "") for e in events if e["type"] == "assistant_delta")


async def _chat(adapter, conv_id, history, message):
    stream = adapter.chat_stream(
        user_message=message,
        user_id="p1-user",
        conversation_id=conv_id,
        session_history=history,
    )
    events = await _collect(stream)
    reply = _reply_text(events)
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    return events, reply


def _tool_calls(events, tool_name):
    return [e for e in events if e["type"] == "tool_start" and e.get("tool") == tool_name]


async def test_p1_topics_platform_extracted_as_douyin():
    """明说抖音 → 一旦调用 lumina_recommend_topics，实参 platform 必为 'douyin'。

    planner 可能先 clarify（合规行为），最多推进 3 轮直至执行。
    """
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True)
    history = []
    await _chat(
        adapter, "p1-topics", history,
        "我是个人创作者，22岁，在抖音做职场干货账号，目标观众是年轻上班族",
    )

    calls = []
    reply = ""
    for attempt, msg in enumerate(
        [
            "直接帮我推荐几个近期值得做的选题方向吧",
            "背景信息都告诉你了，别再问了，直接用工具给我选题",
            "调用 lumina_recommend_topics 给我选题",
        ]
    ):
        events, reply = await _chat(adapter, "p1-topics", history, msg)
        calls = _tool_calls(events, "lumina_recommend_topics")
        if calls:
            break
    assert calls, f"3 轮内应调用一次 lumina_recommend_topics，最后回复: {reply[:150]}"
    platform = (calls[0].get("args") or {}).get("platform")
    brief = (calls[0].get("args") or {}).get("brief")
    print(f"\n[P1-topics] platform={platform} brief={brief}")
    assert platform == "douyin", f"platform 应从对话抽取为 douyin，实际: {platform}"
    assert reply.strip()


async def test_p1_detect_risk_emits_compliance_report():
    """违规文案检测 → lumina_detect_risk + compliance_report 事件（§4.4 字段）。"""
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True)
    events, reply = await _chat(
        adapter, "p1-risk", [],
        "帮我检测这段文案有没有违规风险：「全网最低价！最好的减肥产品，100%有效，错过再等一年」我要发在抖音上",
    )

    calls = _tool_calls(events, "lumina_detect_risk")
    assert calls, "应调用 lumina_detect_risk"
    platform = (calls[0].get("args") or {}).get("platform")
    assert platform == "douyin", f"platform 应抽取为 douyin，实际: {platform}"

    comp = [e for e in events if e["type"] == "compliance_report"]
    assert comp, "应产出 compliance_report 事件"
    ce = comp[0]
    for key in ("risk_level", "risk_categories", "violations", "suggestion", "format", "report_md"):
        assert key in ce, f"compliance_report 缺少字段 {key}"
    print(f"\n[P1-risk] risk_level={ce['risk_level']} violations={ce['violations']}")
    assert ce["risk_level"] in ("medium", "high"), f"该文案应被判为中高风险: {ce['risk_level']}"
    assert ce["violations"], "应检出违规词"


async def test_p1_generate_content_emits_export_link():
    """内容生成 → export_link 事件 + URL 文件可访问 + done.payload.has_content。"""
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True)
    events, reply = await _chat(
        adapter, "p1-content", [],
        "帮我写一篇小红书笔记，主题：平价奶茶推荐，风格轻松口语化",
    )

    calls = _tool_calls(events, "lumina_generate_content")
    assert calls, f"应调用 lumina_generate_content，实际: {[e.get('tool') for e in events if e['type']=='tool_start']}"

    exports = [e for e in events if e["type"] == "export_link"]
    assert exports, "应产出 export_link 事件"
    url = exports[0]["url"]
    assert exports[0]["format"] == "html"
    print(f"\n[P1-content] url={url}")

    # URL 可访问性：本地 /static/content/ 路径查文件存在；
    # 远程 http(s)（配置了对象存储上传）发真实请求验证可访问
    if url.startswith("/"):
        from services.content_engine.storage import FileSystemStorage

        path = FileSystemStorage().get_path(url)
        assert path is not None and path.exists(), f"导出文件不存在: {url}"
    else:
        assert url.startswith("http"), f"未知 URL 形态: {url}"
        import httpx

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
        assert resp.status_code < 400, f"URL 不可访问({resp.status_code}): {url}"

    done = events[-1]
    assert done["payload"].get("has_content") is True
    assert done["payload"]["content_urls"], "done.payload 应含 content_urls"


async def test_p1_diagnose_without_credentials_graceful():
    """无凭证诊断 → 不报错、不伪造数据（clarify 或结构化引导）。"""
    from services.hermes_adapter import HermesEngineAdapter

    adapter = HermesEngineAdapter(use_hermes=True)
    events, reply = await _chat(adapter, "p1-diag", [], "帮我诊断一下我的抖音账号")

    errors = [e for e in events if e["type"] == "error"]
    assert not errors, f"不应产生 error 事件: {errors}"
    assert reply.strip(), "应有自然语言回复（索要账号信息或说明需要授权）"
    calls = _tool_calls(events, "lumina_diagnose_account")
    if calls:
        # 若调用了诊断工具，platform 必须抽取正确
        platform = (calls[0].get("args") or {}).get("platform")
        assert platform == "douyin", f"platform 应为 douyin，实际: {platform}"
    print(f"\n[P1-diag] reply={reply[:150]}")
