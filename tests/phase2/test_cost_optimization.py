"""Phase 2 TDD Harness：LLM 成本优化测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from llm_hub.cost_optimizer import _cache_key


def test_cache_key_deterministic():
    """相同输入产生相同缓存键。"""
    key1 = _cache_key("deepseek-chat", [{"role": "user", "content": "hi"}], temperature=0.7)
    key2 = _cache_key("deepseek-chat", [{"role": "user", "content": "hi"}], temperature=0.7)
    assert key1 == key2


@pytest.mark.asyncio
async def test_cache_hit_returns_cached():
    """缓存命中时直接返回，不调用 LLM。"""
    from llm_hub.cost_optimizer import CostOptimizedCompletion

    optimizer = CostOptimizedCompletion()
    optimizer.cache_set("k1", "cached-value", ttl=60)

    mock_complete = AsyncMock(return_value="should-not-be-called")
    result = await optimizer.complete(
        "deepseek-chat", [{"role": "user", "content": "hi"}], mock_complete, cache_key="k1"
    )
    assert result == "cached-value"
    assert not mock_complete.called


@pytest.mark.asyncio
async def test_cache_miss_and_store():
    """缓存未命中时调用 LLM 并写入缓存。"""
    from llm_hub.cost_optimizer import CostOptimizedCompletion

    optimizer = CostOptimizedCompletion()
    mock_complete = AsyncMock(return_value="fresh-value")
    result = await optimizer.complete(
        "deepseek-chat",
        [{"role": "user", "content": "unique-prompt"}],
        mock_complete,
    )
    assert result == "fresh-value"
    assert mock_complete.called
    assert (
        optimizer.cache_get(
            _cache_key("deepseek-chat", [{"role": "user", "content": "unique-prompt"}], temperature=None)
        )
        == "fresh-value"
    )


@pytest.mark.asyncio
async def test_model_fallback():
    """主模型失败 2 次后使用 fallback 模型。"""
    from llm_hub.cost_optimizer import ModelFallback

    fallback = ModelFallback(fallback_model="cheap-model", failure_threshold=2)
    main = AsyncMock(side_effect=[Exception("fail"), Exception("fail"), "success-after-fallback"])
    cheap = AsyncMock(return_value="cheap-result")

    # 第一次主模型失败
    with pytest.raises(Exception):
        await fallback.call("main-model", main, cheap)
    # 第二次主模型失败，触发 fallback
    result = await fallback.call("main-model", main, cheap)
    assert result == "cheap-result"
    assert cheap.called


def test_token_monitor_alert():
    """Token 超过阈值时返回告警。"""
    from llm_hub.cost_optimizer import TokenMonitor

    monitor = TokenMonitor(hourly_token_limit=100)
    alert = monitor.check("u1", "deepseek-chat", prompt_tokens=60, completion_tokens=50)
    assert alert is True
