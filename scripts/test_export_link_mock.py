"""
Mock 测试：验证 system-chat v2 SSE 流在 AgentTeam 路径下能正确输出 export_link。
通过 patch MarketingOrchestra.process 来避免真实 LLM 调用。
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

# 必须先导入 app，再 patch
from api.main import app


MOCK_RESULT = {
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
                            "result": {
                                "title": "测试标题：高性价比好物推荐",
                                "content": "姐妹们！今天必须给你们安利一波...\n\n性价比真的绝了！",
                                "hashtags": ["性价比", "好物推荐"],
                                "hook_analysis": {"type": "curiosity", "position": "0-3s", "strength": 0.7},
                                "platform_optimization": {"tips": []},
                                "methodology_used": "aida_advanced",
                                "user_id": "debug-user",
                            },
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
                            "result": {
                                "risk_level": "low",
                                "risk_categories": ["none"],
                                "flagged_terms": [],
                                "suggestions": ["未发现明显违规词"],
                                "alternative_phrases": {},
                            },
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
                        "result": {
                            "title": "测试标题：高性价比好物推荐",
                            "content": "姐妹们！今天必须给你们安利一波...\n\n性价比真的绝了！",
                            "hashtags": ["性价比", "好物推荐"],
                            "hook_analysis": {"type": "curiosity", "position": "0-3s", "strength": 0.7},
                            "platform_optimization": {"tips": []},
                            "methodology_used": "aida_advanced",
                            "user_id": "debug-user",
                        },
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
                        "result": {
                            "risk_level": "low",
                            "risk_categories": ["none"],
                            "flagged_terms": [],
                            "suggestions": ["未发现明显违规词"],
                            "alternative_phrases": {},
                        },
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
        mock_process.return_value = MOCK_RESULT

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

    # 检查 export_link
    export_links = [e for e in events if e["type"] == "export_link"]
    if export_links:
        print("\n✅ export_link 事件存在:")
        for link in export_links:
            print(f"   platform={link.get('platform')}, url={link.get('url')}, title={link.get('title')}")
    else:
        print("\n❌ 未找到 export_link 事件")

    # 检查 compliance_report
    compliance_events = [e for e in events if e["type"] == "compliance_report"]
    if compliance_events:
        print("\n✅ compliance_report 事件存在:")
        for c in compliance_events:
            print(f"   risk_level={c.get('risk_level')}, suggestion={c.get('suggestion')}")
    else:
        print("\n❌ 未找到 compliance_report 事件")

    # 检查 done payload
    done_events = [e for e in events if e["type"] == "done"]
    if done_events:
        done = done_events[0]
        payload = done.get("payload", {})
        print(f"\n✅ done 事件存在")
        print(f"   has_content={payload.get('has_content')}")
        print(f"   content_urls={payload.get('content_urls')}")
        print(f"   compliance={payload.get('compliance')}")
    else:
        print("\n❌ 未找到 done 事件")

    # 打印所有事件（调试用）
    print("\n" + "=" * 60)
    print("完整 SSE 流:")
    for e in events:
        print(f"\n[{e['type']}]")
        if e["type"] == "assistant_delta":
            print(f"  text: {e.get('text', '')[:100]}...")
        elif e["type"] == "export_link":
            print(f"  url: {e.get('url')}")
        elif e["type"] == "done":
            print(f"  payload keys: {list(e.get('payload', {}).keys())}")


if __name__ == "__main__":
    main()
