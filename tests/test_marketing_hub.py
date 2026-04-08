import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
for p in (
    ROOT / "apps" / "api" / "src",
    ROOT / "apps" / "orchestra" / "src",
    ROOT / "apps" / "skill-hub" / "src",
    ROOT / "packages" / "llm-hub" / "src",
    ROOT / "packages" / "knowledge-base" / "src",
    ROOT / "packages" / "lumina-skills" / "src",
    ROOT / "packages" / "skill-hub-client" / "src",
    ROOT / "packages" / "sop-engine" / "src",
    ROOT / "packages" / "agent-core" / "src",
):
    sys.path.insert(0, str(p))

from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "orchestra" in body.get("architecture", "")


def test_marketing_hub_greeting_has_top_level_reply():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "你好",
            "user_id": "u_greet2",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("reply"), str)
    assert len(data["reply"]) >= 8


def test_marketing_hub_greeting_is_conversation_not_methodology():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "你好",
            "user_id": "u_greet",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("intent", {}).get("kind") == "conversation"
    hub = data.get("hub") or {}
    assert hub.get("ok") is True
    res = hub.get("result") or {}
    assert res.get("type") == "conversation"
    assert isinstance(res.get("reply"), str)
    assert len(res["reply"]) >= 8


def test_marketing_hub_dynamic():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "帮我看看账号诊断",
            "user_id": "u1",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("layer") == "orchestra"
    assert isinstance(data.get("reply"), str)
    assert len(data["reply"]) > 20
    hub = data.get("hub") or {}
    assert hub.get("ok") is True
    assert "result" in hub
    assert data.get("intent", {}).get("kind") == "diagnosis"
    assert (hub.get("result") or {}).get("type") == "clarification"
    assert "主页链接" in data["reply"] or "账号" in data["reply"]


def test_marketing_hub_weather_is_conversation_not_methodology():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "今天天气怎么样",
            "user_id": "u_weather",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("intent", {}).get("kind") == "conversation"
    hub = data.get("hub") or {}
    assert hub.get("result", {}).get("type") == "conversation"
    reply = data.get("reply") or ""
    assert "天气" in reply or "营销" in reply or "内容" in reply


def test_marketing_hub_methodology_browse_still_general():
    # 含「方法论」会命中 SOP 行；此处用语义仅触发 _METHODOLOGY_BROWSE（general→retrieve）
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "\u589e\u957f\u9ed1\u5ba2\u9002\u5408\u4ec0\u4e48\u573a\u666f",
            "user_id": "u_meth",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("intent", {}).get("kind") == "general"
    assert (data.get("hub") or {}).get("result", {}).get("methodology_id")


def test_marketing_hub_traffic_over_account_when_both_mentioned():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "我有账号，但是不知道为什么流量不好",
            "user_id": "u_traffic",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("intent", {}).get("kind") == "traffic"
    assert isinstance(data.get("reply"), str)
    assert (data.get("hub") or {}).get("result", {}).get("type") == "clarification"
    assert "数据" in data["reply"] or "metrics" in data["reply"] or "流量" in data["reply"]


def test_marketing_hub_traffic_with_metrics_runs_analyze():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "流量很差帮我分析",
            "user_id": "u_traffic2",
            "platform": "xiaohongshu",
            "context": {"metrics": {"views": 8000, "likes": 120, "shares": 5}},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("intent", {}).get("kind") == "traffic"
    hub = data.get("hub") or {}
    assert hub.get("ok") is True
    res = hub.get("result") or {}
    assert res.get("funnel_analysis")
    assert "进度" in data["reply"] or "流量" in data["reply"]


def test_marketing_hub_capabilities_question_distinct_from_greeting():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "你能帮我做什么",
            "user_id": "u_caps",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("intent", {}).get("kind") == "conversation"
    rep = data.get("reply") or ""
    assert "起号" in rep or "流量" in rep
    assert "说明书腔" not in rep


def test_marketing_hub_stiffness_feedback_gets_ack_not_greeting():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "你这回答真僵硬",
            "user_id": "u_stiff",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("intent", {}).get("kind") == "conversation"
    rep = data.get("reply") or ""
    assert "说明书" in rep or "模板" in rep or "硬" in rep
    assert "直接说说你现在最想解决" not in rep


def test_marketing_hub_new_account_phrase_is_conversation_not_diagnosis():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "我想做个账号",
            "user_id": "u_newacct",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("intent", {}).get("kind") == "conversation"
    assert (data.get("hub") or {}).get("result", {}).get("type") == "conversation"
    rep = data.get("reply") or ""
    assert "主页链接" not in rep
    assert "平台" in rep or "赛道" in rep or "图文" in rep


def test_marketing_hub_user_complaint_triggers_clarify_not_fake_diagnosis():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "你都没问我的账号是什么？",
            "user_id": "u_meta",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("intent", {}).get("kind") == "clarify_feedback"
    assert (data.get("hub") or {}).get("result", {}).get("type") == "clarification"
    assert "主页链接" in data["reply"] or "数据" in data["reply"]
    assert "健康度" not in data["reply"]


def test_marketing_hub_sop():
    r = client.post(
        "/api/v1/marketing/hub",
        json={
            "user_input": "按 AIDA 方法论走一遍 SOP",
            "user_id": "u1",
            "platform": "xiaohongshu",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("mode") == "sop"
    assert "node_results" in (data.get("sop") or {})
    assert isinstance(data.get("reply"), str)
    assert "SOP" in data["reply"] or "节点" in data["reply"]


@pytest.mark.asyncio
async def test_skill_hub_client_direct():
    from skill_hub_client import SkillHubClient

    c = SkillHubClient()
    out = await c.call(
        "retrieve_methodology",
        {"query": "AIDA", "industry": "beauty", "user_id": "t"},
    )
    assert out["ok"] is True
    assert out["result"].get("methodology_id")
