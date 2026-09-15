"""Phase 3 TDD Harness：定位矩阵 Skill 包装层测试。"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def test_positioning_matrix_skill_matrix_mode():
    from orchestra.skills import positioning_matrix_skill

    result = await positioning_matrix_skill.run(
        message="用矩阵帮我梳理一下内容定位：这个教程讲了 Python 爬虫技巧",
        platform="douyin",
        context={},
        history=[],
        mode="matrix",
    )

    assert isinstance(result, str)
    assert "定位矩阵" in result


async def test_positioning_matrix_skill_case_mode():
    from orchestra.skills import positioning_matrix_skill

    result = await positioning_matrix_skill.run(
        message="给我一个差异化的定位方案：护肤博主分享日常护肤心得",
        platform="xiaohongshu",
        context={},
        history=[],
        mode="case",
    )

    assert isinstance(result, str)
    assert "差异化建议" in result


async def test_positioning_matrix_skill_default_mode():
    from orchestra.skills import positioning_matrix_skill

    result = await positioning_matrix_skill.run(
        message="帮我定位：标题党短视频",
        platform="xiaohongshu",
        context={},
        history=[],
        mode=None,
    )

    assert isinstance(result, str)
    assert "所在象限" in result


async def test_positioning_matrix_skill_clarifies_when_no_content():
    """当用户只表达意图、没有提供可分析内容时，应澄清而不是强行评分。"""
    from orchestra.skills import positioning_matrix_skill

    result = await positioning_matrix_skill.run(
        message="我想做个内容定位",
        platform="xiaohongshu",
        context={},
        history=[],
        mode=None,
    )

    assert isinstance(result, str)
    assert "所在象限" not in result  # 不是矩阵评分输出
    assert "我可以帮你" in result   # 澄清话术开头
    assert "定位矩阵" in result
    assert "账号定位策划" in result
    assert "你想从哪一类开始" in result


async def test_positioning_matrix_skill_uses_content_from_history():
    """当前输入没有内容，但历史对话中有，应基于历史内容分析并提示用户。"""
    from orchestra.skills import positioning_matrix_skill

    result = await positioning_matrix_skill.run(
        message="帮我分析一下内容定位",
        platform="xiaohongshu",
        context={},
        history=[
            {"role": "user", "content": "这个教程讲了 Python 爬虫技巧"},
        ],
        mode=None,
    )

    assert isinstance(result, str)
    assert "定位矩阵" in result
    assert "所在象限" in result
    assert "之前提供的内容" in result
    assert "Python" in result


async def test_positioning_matrix_skill_uses_content_from_context():
    """当前输入没有内容，但上下文中有 content_text，应基于上下文分析并提示用户。"""
    from orchestra.skills import positioning_matrix_skill

    result = await positioning_matrix_skill.run(
        message="帮我做内容定位矩阵",
        platform="xiaohongshu",
        context={"content_text": "护肤博主分享日常护肤心得"},
        history=[],
        mode=None,
    )

    assert isinstance(result, str)
    assert "定位矩阵" in result
    assert "所在象限" in result
    assert "对话上下文中的内容" in result
