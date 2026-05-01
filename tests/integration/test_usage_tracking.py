"""Token 用量统计集成测试。"""

from __future__ import annotations

import pytest
from datetime import date, timedelta


class TestUsageService:
    """验证 usage_service 在有无 DB 时的行为。"""

    @pytest.mark.asyncio
    async def test_record_usage_without_pool_does_not_raise(self):
        """未配置 DB 时，record_usage 应静默跳过不抛异常。"""
        from services.usage_service import record_usage

        # 此处未初始化 DB pool，应友好降级
        await record_usage(
            user_id="00000000-0000-0000-0000-000000000001",
            model="deepseek-chat",
            prompt_tokens=100,
            completion_tokens=50,
            skill_name="test",
        )

    @pytest.mark.asyncio
    async def test_get_summary_without_pool_returns_zeros(self):
        """未配置 DB 时，get_summary 应返回零值结构。"""
        from services.usage_service import get_summary

        result = await get_summary("test-user")
        assert result["user_id"] == "test-user"
        assert result["total_prompt_tokens"] == 0
        assert result["total_completion_tokens"] == 0
        assert result["total_tokens"] == 0
        assert result["call_count"] == 0

    @pytest.mark.asyncio
    async def test_get_daily_stats_without_pool_returns_empty(self):
        """未配置 DB 时，get_daily_stats 应返回空 daily 列表。"""
        from services.usage_service import get_daily_stats

        result = await get_daily_stats(
            "test-user",
            date.today() - timedelta(days=7),
            date.today(),
        )
        assert result["daily"] == []


class TestUsageReporter:
    """验证 usage_reporter 注册与上报机制。"""

    @pytest.mark.asyncio
    async def test_report_usage_without_reporter_does_not_raise(self):
        """未注册 reporter 时，report_usage 应静默跳过。"""
        from llm_hub.usage_reporter import report_usage

        await report_usage("u1", "m1", 10, 5, 15, "skill")

    @pytest.mark.asyncio
    async def test_set_and_report_usage(self):
        """注册 reporter 后，report_usage 应正确触发回调。"""
        from llm_hub.usage_reporter import set_usage_reporter, report_usage

        calls = []

        async def mock_reporter(uid, model, pt, ct, tt, skill):
            calls.append({"user_id": uid, "model": model, "pt": pt, "ct": ct, "tt": tt, "skill": skill})

        set_usage_reporter(mock_reporter)
        await report_usage("u1", "gpt-4o", 100, 50, 150, "test_skill")

        assert len(calls) == 1
        assert calls[0]["user_id"] == "u1"
        assert calls[0]["model"] == "gpt-4o"
        assert calls[0]["pt"] == 100
        assert calls[0]["ct"] == 50
        assert calls[0]["tt"] == 150
        assert calls[0]["skill"] == "test_skill"

        # 清理，避免影响其他测试
        set_usage_reporter(None)


class TestLLMClientUsageMeta:
    """验证 LLMClient.complete 对 _usage_meta 的处理。"""

    @pytest.mark.asyncio
    async def test_complete_without_usage_meta_does_not_record(self):
        """不传 _usage_meta 时，complete 应正常返回字符串，不触发上报。"""
        from llm_hub.usage_reporter import set_usage_reporter
        from llm_hub.client import LLMClient
        from llm_hub.config_models import LLMConfig
        import asyncio

        calls = []

        async def mock_reporter(uid, model, pt, ct, tt, skill):
            calls.append({"user_id": uid})

        set_usage_reporter(mock_reporter)

        cfg = LLMConfig(
            name="test",
            provider="openai",
            model="gpt-4o-mini",
            api_key="sk-fake",
            timeout=1,
        )
        client = LLMClient(cfg)

        # 由于会真实调用 litellm，这里仅验证接口不会异常
        # 在 CI/无 API Key 环境中会走异常分支，但不应因 _usage_meta 而崩溃
        try:
            result = await asyncio.wait_for(client.complete("hello"), timeout=2)
            assert isinstance(result, str)
        except Exception:
            pass  # 无真实 API Key 时允许失败

        # 未传 _usage_meta，不应触发 reporter
        assert len(calls) == 0

        set_usage_reporter(None)
