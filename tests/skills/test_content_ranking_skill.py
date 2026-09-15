"""Phase 3 TDD Harness：内容方向榜单 Skill 包装层测试。"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


pytestmark = pytest.mark.asyncio


async def _async_iter(pieces):
    for piece in pieces:
        yield piece


def _mock_llm_client(pieces):
    mock_client = AsyncMock()
    mock_client.stream_completion = MagicMock(return_value=_async_iter(pieces))
    mock_client.config.api_key = "test-key"
    return mock_client


async def test_content_ranking_skill_returns_text():
    with patch("orchestra.skills.trending_rank.skill.get_client", return_value=_mock_llm_client(["美妆", "方向"])):
        with patch("orchestra.skills.trending_rank.skill.get_hub", return_value=AsyncMock()):
            from orchestra.skills import content_ranking_skill
            result = await content_ranking_skill.run(
                message="帮我排一下美妆赛道的内容方向优先级",
                platform="xiaohongshu",
                context={},
                history=[],
            )

    assert isinstance(result, str)
    assert "美妆" in result


async def test_content_ranking_skill_includes_platform_context():
    with patch("orchestra.skills.trending_rank.skill.get_client", return_value=_mock_llm_client(["抖音"])):
        with patch("orchestra.skills.trending_rank.skill.get_hub", return_value=AsyncMock()):
            from orchestra.skills import content_ranking_skill
            result = await content_ranking_skill.run(
                message="帮我排一下美妆赛道的内容方向优先级",
                platform="douyin",
                context={},
                history=[],
            )

    assert "抖音" in result


async def test_content_ranking_skill_clarifies_without_topic():
    """当用户只表达查榜单意图、没有提供赛道/关键词时，应澄清。"""
    from orchestra.skills import content_ranking_skill

    result = await content_ranking_skill.run(
        message="帮我排方向",
        platform="xiaohongshu",
        context={},
        history=[],
    )

    assert isinstance(result, str)
    assert "赛道/关键词" in result


async def test_content_ranking_skill_uses_keyword_from_history():
    """当前输入没有关键词，但历史对话中有，应基于历史关键词查询并提示用户。"""
    with patch("orchestra.skills.trending_rank.skill.get_client", return_value=_mock_llm_client(["美妆"])):
        with patch("orchestra.skills.trending_rank.skill.get_hub", return_value=AsyncMock()):
            from orchestra.skills import content_ranking_skill
            result = await content_ranking_skill.run(
                message="帮我查一下",
                platform="xiaohongshu",
                context={},
                history=[
                    {"role": "user", "content": "我想了解美妆赛道的热门内容"},
                ],
            )

    assert isinstance(result, str)
    assert "之前提到的" in result
    assert "美妆" in result


async def test_content_ranking_skill_uses_keyword_from_context():
    """当前输入没有关键词，但上下文中有 topic，应基于上下文查询并提示用户。"""
    with patch("orchestra.skills.trending_rank.skill.get_client", return_value=_mock_llm_client(["护肤"])):
        with patch("orchestra.skills.trending_rank.skill.get_hub", return_value=AsyncMock()):
            from orchestra.skills import content_ranking_skill
            result = await content_ranking_skill.run(
                message="帮我查爆款",
                platform="xiaohongshu",
                context={"topic": "护肤"},
                history=[],
            )

    assert isinstance(result, str)
    assert "对话上下文中的" in result
    assert "护肤" in result


async def test_content_ranking_skill_disabled_returns_fallback():
    from orchestra.skills import content_ranking_skill

    with patch.object(content_ranking_skill, "is_enabled", new=lambda: False):
        result = await content_ranking_skill.run(
            message="帮我排方向",
            platform="xiaohongshu",
            context={},
            history=[],
        )

    assert isinstance(result, str)
    assert result != ""
