"""Phase 3 TDD Harness：每周决策快照 Skill 包装层测试。"""

from __future__ import annotations

import pytest
from unittest.mock import patch


pytestmark = pytest.mark.asyncio


async def test_weekly_snapshot_skill_returns_text():
    from orchestra.skills import weekly_snapshot_skill

    result = await weekly_snapshot_skill.run(
        message="帮我整理本周的内容运营决策快照",
        platform="xiaohongshu",
        context={
            "metrics": {
                "contents": [
                    {
                        "title": "爆款笔记",
                        "content_type": "图文",
                        "platform": "xiaohongshu",
                        "published_at": "2026-07-01T12:00:00",
                        "metrics": {
                            "views": 10000,
                            "likes": 500,
                            "comments": 50,
                            "collections": 100,
                            "shares": 20,
                        },
                    },
                ],
                "stats": {"total_contents": 1, "total_views": 10000, "new_followers": 100},
            }
        },
        history=[],
    )

    assert isinstance(result, str)
    assert "每周决策快报" in result
    assert "PROGRESS" in result
    assert "已提供的运营数据" in result


async def test_weekly_snapshot_skill_clarifies_without_metrics():
    """当未提供真实运营数据时，应要求补充数据而不是生成空报告。"""
    from orchestra.skills import weekly_snapshot_skill

    result = await weekly_snapshot_skill.run(
        message="帮我整理本周决策",
        platform="xiaohongshu",
        context={},
        history=[],
    )

    assert isinstance(result, str)
    assert "PROGRESS" not in result
    assert "真实运营数据" in result
    assert "授权" in result


async def test_weekly_snapshot_skill_disabled_returns_fallback():
    from orchestra.skills import weekly_snapshot_skill

    with patch.object(weekly_snapshot_skill, "is_enabled", new=lambda: False):
        result = await weekly_snapshot_skill.run(
            message="帮我整理本周决策",
            platform="xiaohongshu",
            context={},
            history=[],
        )

    assert isinstance(result, str)
    assert result != ""
