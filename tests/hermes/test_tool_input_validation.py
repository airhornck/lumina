"""Hermes 工具入口参数校验测试：缺必填字段时 handler 必须返回 ok=False。

hermes registry.dispatch 不做 JSON Schema 校验（schema 仅注入 prompt），
handler 内的 pydantic Input 模型是唯一硬关卡——9 个工具必须全部对称覆盖。
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "tool_name,args",
    [
        # 三个 orchestra skill 工具：message 必填（本次补上的校验缺口）
        ("lumina_content_ranking", {}),
        ("lumina_content_ranking", {"platform": "douyin"}),
        ("lumina_positioning_matrix", {}),
        ("lumina_weekly_snapshot", {}),
        # 其余工具：原有 pydantic 校验的对照组
        ("lumina_generate_content", {"platform": "douyin"}),  # 缺 topic
        ("lumina_generate_content", {"topic": "防晒"}),  # 缺 platform
        ("lumina_recommend_topics", {"niche": "美妆"}),  # 缺 platform
        ("lumina_detect_risk", {"content_text": "最强防晒"}),  # 缺 platform
        ("lumina_analyze_traffic", {"metrics": {"views": 100}}),  # 缺 platform
        ("lumina_diagnose_account", {"account_name": "某账号"}),  # 缺 platform
    ],
)
async def test_missing_required_field_returns_ok_false(tool_name, args):
    from services.hermes_tools import handle_tool_call

    result = json.loads(await handle_tool_call(tool_name, args))
    assert result["ok"] is False
    assert result.get("error")
