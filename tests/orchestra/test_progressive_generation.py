"""Phase 0 TDD Harness：渐进式内容生成 Red 状态测试。"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def test_missing_topic_returns_clarification():
    from orchestra.intent_guards import ProgressiveGenerationGuard
    from orchestra.required_fields import ContentGenerationIntent

    guard = ProgressiveGenerationGuard()
    intent = ContentGenerationIntent(kind="content", platform="xiaohongshu")
    result = await guard.check(
        user_input="帮我写文案",
        intent=intent,
        session_history=[],
    )
    assert result.is_complete is False
    assert "topic" in result.missing
    assert result.reply != ""


async def test_infer_platform_from_input():
    from orchestra.intent_guards import ProgressiveGenerationGuard
    from orchestra.required_fields import ContentGenerationIntent

    guard = ProgressiveGenerationGuard()
    intent = ContentGenerationIntent(kind="content")
    result = await guard.check(
        user_input="帮我写个小红书文案",
        intent=intent,
        session_history=[],
    )
    assert result.collected.get("platform") == "xiaohongshu"


async def test_infer_topic_from_input():
    from orchestra.intent_guards import ProgressiveGenerationGuard
    from orchestra.required_fields import ContentGenerationIntent

    guard = ProgressiveGenerationGuard()
    intent = ContentGenerationIntent(
        kind="content",
        platform="xiaohongshu",
        target_audience="student",
        content_goal="engagement",
    )
    result = await guard.check(
        user_input="帮我写个夏季防晒文案",
        intent=intent,
        session_history=[],
    )
    assert result.collected.get("topic") == "夏季防晒"
    assert result.collected.get("platform") == "xiaohongshu"
    assert result.missing == ["style"]


async def test_historical_info_reused():
    from orchestra.intent_guards import ProgressiveGenerationGuard
    from orchestra.required_fields import ContentGenerationIntent

    guard = ProgressiveGenerationGuard()
    intent = ContentGenerationIntent(kind="content")
    history = [
        {"role": "user", "content": "主题是夏季防晒"},
        {"role": "assistant", "content": "收到"},
    ]
    result = await guard.check(
        user_input="帮我写文案",
        intent=intent,
        session_history=history,
    )
    assert result.collected.get("topic") == "夏季防晒"


async def test_max_clarification_2_rounds():
    from orchestra.intent_guards import ProgressiveGenerationGuard
    from orchestra.required_fields import ContentGenerationIntent

    guard = ProgressiveGenerationGuard()
    intent = ContentGenerationIntent(kind="content")
    result = await guard.check(
        user_input="帮我写文案",
        intent=intent,
        session_history=[],
        clarification_count=2,
    )
    assert result.is_complete is True
    assert result.use_defaults is True


async def test_disabled_flag_allows_direct_generation():
    from orchestra.intent_guards import ProgressiveGenerationGuard
    from orchestra.required_fields import ContentGenerationIntent

    guard = ProgressiveGenerationGuard(enabled=False)
    intent = ContentGenerationIntent(kind="content")
    result = await guard.check(
        user_input="帮我写文案",
        intent=intent,
        session_history=[],
    )
    assert result.is_complete is True
    assert result.missing == []
