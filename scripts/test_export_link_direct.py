"""
直接测试 _run_agent_team 的 HTML 生成后置处理逻辑。
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

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class MockExecutionResult:
    success: bool = True
    results: Dict[str, Any] = field(default_factory=dict)
    errors: list = field(default_factory=list)
    execution_time_ms: int = 1000
    agent_outputs: Dict[str, Any] = field(default_factory=dict)


async def test_run_agent_team_postprocess():
    from orchestra.core import MarketingOrchestra

    orch = MarketingOrchestra()

    # 构造模拟的 AgentTeam 执行结果
    mock_result = MockExecutionResult(
        success=True,
        results={"agents_executed": ["creative_studio", "compliance_officer"]},
        agent_outputs={
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
    )

    # 直接调用 _run_agent_team 中的后置处理逻辑
    # 由于 _run_agent_team 需要 AgentOrchestrator，我们手动模拟后半段
    kind = "content"
    primary_result = {}
    for agent_id, output in mock_result.agent_outputs.items():
        if isinstance(output, dict) and "results" in output:
            for skill_id, skill_res in output["results"].items():
                if isinstance(skill_res, dict) and skill_res.get("ok") and skill_res.get("result"):
                    primary_result = dict(skill_res["result"])
                    break

    merged_result = dict(mock_result.results)
    if primary_result:
        for k, v in primary_result.items():
            if k not in merged_result:
                merged_result[k] = v

    print("Before HTML generation:")
    print("  has title:", "title" in merged_result)
    print("  has content:", "content" in merged_result)
    print("  has export_urls:", "export_urls" in merged_result)

    # 执行 HTML 生成后置处理（复制自 core.py）
    if kind in {"content", "script"} and primary_result.get("title"):
        from services.content_engine.html_renderer import HtmlRenderer
        from services.content_engine.storage import FileSystemStorage
        import uuid

        renderer = HtmlRenderer()
        storage = FileSystemStorage()
        req_id = str(uuid.uuid4())
        platform = "xiaohongshu"

        html = renderer.render(primary_result, {}, platform=platform)
        url = storage.save(request_id=req_id, platform=platform, html=html)

        export_urls = [
            {
                "platform": platform,
                "url": url,
                "variant": "platform_adapt",
                "title": primary_result.get("title", ""),
            }
        ]

        merged_result["export_urls"] = export_urls

        compliance_output = mock_result.agent_outputs.get("compliance_officer")
        if isinstance(compliance_output, dict) and "results" in compliance_output:
            for skill_id, skill_res in compliance_output["results"].items():
                if isinstance(skill_res, dict) and skill_res.get("ok"):
                    comp = skill_res.get("result", {})
                    if comp:
                        merged_result["compliance"] = {
                            "risk_level": comp.get("risk_level", "low"),
                            "risk_categories": comp.get("risk_categories", ["none"]),
                            "violations": [],
                            "suggestion": "; ".join(comp.get("suggestions", ["未发现明显违规词"])),
                            "format": "markdown",
                            "report_md": orch._build_compliance_md(comp),
                        }
                        merged_result["risk_level"] = comp.get("risk_level", "low")
                        merged_result["risk_categories"] = comp.get("risk_categories", ["none"])
                        merged_result["flagged_terms"] = comp.get("flagged_terms", [])
                        merged_result["suggestions"] = comp.get("suggestions", [])
                        merged_result["alternative_phrases"] = comp.get("alternative_phrases", {})
                        break

    print("\nAfter HTML generation:")
    print("  has export_urls:", "export_urls" in merged_result)
    print("  export_urls:", merged_result.get("export_urls"))
    print("  has compliance:", "compliance" in merged_result)
    print("  has risk_level:", "risk_level" in merged_result)
    print("  has title:", "title" in merged_result)
    print("  has content:", "content" in merged_result)

    # 验证 HTML 文件存在
    read_back = storage.get(url)
    print("\nHTML file readable:", read_back is not None)
    print("HTML length:", len(read_back) if read_back else 0)

    return merged_result


if __name__ == "__main__":
    result = asyncio.run(test_run_agent_team_postprocess())
    print("\nTest completed.")
