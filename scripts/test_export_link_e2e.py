"""
端到端 mock 测试：patch MarketingOrchestra.process，验证 system-chat v2 SSE 流。
"""

import sys
sys.path.insert(0, "apps/api/src")
sys.path.insert(0, "packages/agent-core/src")
sys.path.insert(0, "packages/llm-hub/src")
sys.path.insert(0, "packages/sop-engine/src")
sys.path.insert(0, "packages/lumina-skills/src")
sys.path.insert(0, "packages/skill-hub-client/src")
sys.path.insert(0, "packages/knowledge-base/src")
sys.path.insert(0, "apps/orchestra/src")

import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from api.main import app


def build_mock_result():
    """构造模拟的 orchestra process 返回值，包含 AgentTeam 执行结果。"""
    creative_result = {
        "title": "测试标题：高性价比好物推荐",
        "content": "姐妹们！今天必须给你们安利一波...\n\n性价比真的绝了！",
        "hashtags": ["性价比", "好物推荐"],
        "hook_analysis": {"type": "curiosity", "position": "0-3s", "strength": 0.7},
        "platform_optimization": {"tips": []},
        "methodology_used": "aida_advanced",
        "user_id": "debug-user",
    }
    compliance_result = {
        "risk_level": "low",
        "risk_categories": ["none"],
        "flagged_terms": [],
        "suggestions": ["未发现明显违规词"],
        "alternative_phrases": {},
    }
    return {
        "layer": "orchestra",
        "mode": "agent_team",
        "intent": {"kind": "content", "sop_id": None},
        "hub": {
            "ok": True,
            "result": {
                "agents_executed": ["creative_studio", "compliance_officer"],
                "outputs": {
                    "creative_studio": {
                        "agent_id": "creative_studio",
                        "agent_name": "创意工厂",
                        "skills_executed": ["skill-creative-studio"],
                        "results": {
                            "skill-creative-studio": {
                                "ok": True,
                                "result": creative_result,
                            }
                        },
                    },
                    "compliance_officer": {
                        "agent_id": "compliance_officer",
                        "agent_name": "合规审查员",
                        "skills_executed": ["skill-compliance-officer"],
                        "results": {
                            "skill-compliance-officer": {
                                "ok": True,
                                "result": compliance_result,
                            }
                        },
                    },
                },
            },
            "agent_outputs": {
                "creative_studio": {
                    "agent_id": "creative_studio",
                    "agent_name": "创意工厂",
                    "skills_executed": ["skill-creative-studio"],
                    "results": {
                        "skill-creative-studio": {
                            "ok": True,
                            "result": creative_result,
                        }
                    },
                },
                "compliance_officer": {
                    "agent_id": "compliance_officer",
                    "agent_name": "合规审查员",
                    "skills_executed": ["skill-compliance-officer"],
                    "results": {
                        "skill-compliance-officer": {
                            "ok": True,
                            "result": compliance_result,
                        }
                    },
                },
            },
            "errors": [],
            "execution_time_ms": 10271,
            "agent_team": {"mode": "serial", "agents": ["creative_studio", "compliance_officer"]},
        },
        "reply": "好的，我已经为你完成了这篇小红书种草笔记，并同步通过了合规审查。",
        "agent_team": {"mode": "serial", "agents": ["creative_studio", "compliance_officer"]},
    }


def parse_sse(response_text: str):
    lines = [l.strip() for l in response_text.strip().split("\n") if l.strip()]
    events = []
    for line in lines:
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def main():
    with patch("services.handlers.system_chat.marketing_orchestra_process") as mock_process:
        mock_process.return_value = build_mock_result()

        client = TestClient(app)
        resp = client.post(
            "/api/v1/services/system-chat/stream",
            json={
                "user_id": "debug-user",
                "conversation_id": "debug-conv-001",
                "message": "帮我写1篇小红书种草笔记，主打性价比",
                "platform": "xiaohongshu",
                "context": {},
                "stream_format": 2,
            },
        )

    assert resp.status_code == 200, resp.text
    events = parse_sse(resp.text)

    print("=" * 60)
    print("SSE Event Types:", [e["type"] for e in events])
    print("=" * 60)

    export_links = [e for e in events if e["type"] == "export_link"]
    compliance_events = [e for e in events if e["type"] == "compliance_report"]
    done_events = [e for e in events if e["type"] == "done"]

    print("\n[export_link] count:", len(export_links))
    for link in export_links:
        print(f"  platform={link.get('platform')}, url={link.get('url')}")

    print("\n[compliance_report] count:", len(compliance_events))
    for c in compliance_events:
        print(f"  risk_level={c.get('risk_level')}, suggestion={c.get('suggestion')}")

    if done_events:
        done = done_events[0]
        payload = done.get("payload", {})
        print(f"\n[done] has_content={payload.get('has_content')}")
        print(f"[done] content_urls={payload.get('content_urls')}")

    # 断言验证
    assert len(export_links) > 0, "Missing export_link event!"
    assert export_links[0]["url"].startswith("/static/content/"), "URL format wrong!"
    assert len(compliance_events) > 0, "Missing compliance_report event!"
    assert done_events[0]["payload"].get("has_content") is True, "has_content should be True!"
    print("\nAll assertions PASSED!")


if __name__ == "__main__":
    main()
