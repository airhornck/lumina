"""多平台内容生成并发回归测试。

覆盖问题：
1. 并发调用 lumina_generate_content 时 threading.local() 上下文竞争导致非小红书平台失败。
2. 微信公众号等平台别名缺失。
3. _extract_json 对非对象 JSON 的防御。
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "apps" / "api" / "src"))
sys.path.insert(0, str(_repo_root / "packages" / "knowledge-base" / "src"))
sys.path.insert(0, str(_repo_root / "packages" / "llm-hub" / "src"))


@pytest.fixture
def mock_llm_client():
    """返回一个会按平台返回不同适配结果的 mock LLM client。"""

    async def _complete(prompt, **kwargs):
        # 平台适配 prompt
        if "平台 DNA" in prompt or "平台风格要求" in prompt:
            platform = (
                "xiaohongshu"
                if "小红书" in prompt
                else "douyin"
                if "抖音" in prompt
                else "bilibili"
                if "B站" in prompt
                else "wechat_official"
            )
            return json.dumps(
                {
                    "title": f"{platform} 适配标题",
                    "body": f"这是 {platform} 平台的适配正文。" * 5,
                    "hashtags": ["标签1", "标签2"],
                    "hook": "黄金3秒钩子",
                    "best_time": "18:00",
                },
                ensure_ascii=False,
            )
        # 母稿 prompt
        return json.dumps(
            {
                "title": "母稿标题",
                "content": "这是母稿正文内容。" * 10,
                "hashtags": ["标签A", "标签B"],
                "topic": "测试主题",
            },
            ensure_ascii=False,
        )

    client = MagicMock()
    client.config.api_key = "test-key"
    client.complete = _complete
    return client


@pytest.fixture
def patched_engine_deps(mock_llm_client):
    """mock CrossPlatformEngine 依赖的外部服务。"""
    stack = []
    stack.append(patch("services.content_engine.master_generator.get_client"))
    stack.append(patch("services.content_engine.platform_adaptor.get_client"))
    stack.append(patch("services.content_engine.summarizer.get_client"))
    stack.append(
        patch(
            "services.content_engine.cross_platform_engine.UserProfileService.resolve_positioning",
            new_callable=AsyncMock,
        )
    )
    stack.append(
        patch(
            "services.content_engine.cross_platform_engine.ResourceUploader.upload_batch",
            new_callable=AsyncMock,
        )
    )
    stack.append(
        patch(
            "services.content_engine.cross_platform_engine.ExportRecordService.save_exports",
            new_callable=AsyncMock,
        )
    )

    with ExitStack() as ctx:
        mocks = [ctx.enter_context(p) for p in stack]
        for m in mocks[:3]:
            m.return_value = mock_llm_client
        mocks[3].return_value = {"positioning_statement": "测试定位"}
        mocks[4].return_value = {}
        yield


class TestMultiPlatformContentGeneration:
    @pytest.mark.asyncio
    async def test_concurrent_generation_for_all_platforms(self, patched_engine_deps):
        """并发为小红书、B站、抖音、公众号生成内容均应成功。"""
        from services.hermes_tools import handle_tool_call

        platforms = ["xiaohongshu", "bilibili", "douyin", "wechat_official"]

        async def _call(platform: str):
            return await handle_tool_call(
                "lumina_generate_content",
                {
                    "topic": "10分钟居家无器械跟练",
                    "platform": platform,
                    "style": "轻松口语化",
                    "target_audience": "上班族",
                    "content_goal": "涨粉互动",
                },
                user_id="u-concurrent",
                conversation_id="c-concurrent",
                platform=platform,
                user_message=f"帮我生成一个可分享的{platform}文章",
            )

        results = await asyncio.gather(*(_call(p) for p in platforms))
        for platform, raw in zip(platforms, results):
            data = json.loads(raw)
            assert data["ok"] is True, f"{platform} 生成失败: {data.get('error')}"
            export_urls = data.get("export_urls", [])
            platforms_in_urls = [u["platform"] for u in export_urls]
            assert platform in platforms_in_urls, f"{platform} 缺少 export_link"

    @pytest.mark.asyncio
    async def test_single_wechat_official_via_alias(self, patched_engine_deps):
        """通过公众号别名调用也能命中 wechat_official 规范并生成内容。"""
        from services.hermes_tools import handle_tool_call

        result = await handle_tool_call(
            "lumina_generate_content",
            {
                "topic": "久坐族自救指南",
                "platform": "公众号",
            },
            user_id="u-wechat",
            conversation_id="c-wechat",
            platform="wechat_official",
            user_message="帮我生成一个可分享的微信公众号文章",
        )
        data = json.loads(result)
        assert data["ok"] is True, data.get("error")
        assert any(u["platform"] == "wechat_official" for u in data.get("export_urls", []))


class TestPlatformAlias:
    def test_wechat_official_aliases(self):
        from services.platform_utils import normalize_platform

        for alias in ["公众号", "微信公众号", "微信", "wechat", "wechat_official"]:
            assert normalize_platform(alias) == "wechat_official", f"{alias} 未正确归一化"


class TestExtractJsonDefense:
    def test_extract_json_rejects_non_object_json(self):
        from services.content_engine.master_generator import _extract_json

        assert _extract_json('"纯文本字符串"') is None
        assert _extract_json('"{"') is None
        assert _extract_json('["list"]') is None
        assert _extract_json('123') is None

    def test_extract_json_accepts_object(self):
        from services.content_engine.master_generator import _extract_json

        assert _extract_json('{"title": "t"}') == {"title": "t"}
        assert _extract_json('```json\n{"title": "t"}\n```') == {"title": "t"}


class TestPositioningNormalization:
    @pytest.mark.asyncio
    async def test_resolve_positioning_normalizes_string_target_persona_from_context(self):
        """P0 上下文传入字符串形式的 target_persona 时，应被解析/降级为字典，
        避免 master_generator 中 persona.get() 报错。"""
        from services.content_engine.user_profile_service import UserProfileService

        svc = UserProfileService()
        result = await svc.resolve_positioning(
            "u-test",
            "xiaohongshu",
            {
                "positioning_statement": "测试定位",
                "target_persona": '{"age": "25-40", "gender": "不限", "pain_points": ["久坐"], "needs": ["放松"]}',
                "content_pillars": ["居家健身"],
                "differentiation": "零器械",
            },
            [],
        )
        assert isinstance(result["target_persona"], dict)
        assert result["target_persona"]["age"] == "25-40"
        assert result["target_persona"].get("pain_points") == ["久坐"]

    def test_normalize_positioning_downgrades_plain_string_persona(self):
        """target_persona 为无法解析的字符串时，应降级为空字典。"""
        from services.content_engine.user_profile_service import UserProfileService

        result = UserProfileService._normalize_positioning(
            {"positioning_statement": "x", "target_persona": "unknown", "content_pillars": []}
        )
        assert isinstance(result["target_persona"], dict)
        assert result["target_persona"] == {}

    @pytest.mark.asyncio
    async def test_db_profile_with_string_target_persona_does_not_crash(self, mock_llm_client):
        """数据库里 target_persona 存的是 JSON 字符串时，生成流程应正常完成。"""
        from services.hermes_tools import handle_tool_call

        with ExitStack() as ctx:
            ctx.enter_context(patch("services.content_engine.master_generator.get_client", return_value=mock_llm_client))
            ctx.enter_context(patch("services.content_engine.platform_adaptor.get_client", return_value=mock_llm_client))
            ctx.enter_context(patch("services.content_engine.summarizer.get_client", return_value=mock_llm_client))
            ctx.enter_context(
                patch(
                    "services.content_engine.user_profile_service.UserProfileService._db_get",
                    new_callable=AsyncMock,
                    return_value={
                        "positioning_statement": "久坐族健身定位",
                        "target_persona": '{"age": "25-40", "gender": "不限", "pain_points": ["久坐腰痛"], "needs": ["快速放松"]}',
                        "content_pillars": ["居家健身", "碎片化运动"],
                        "differentiation": "零器械",
                    },
                )
            )
            ctx.enter_context(
                patch(
                    "services.content_engine.cross_platform_engine.ResourceUploader.upload_batch",
                    new_callable=AsyncMock,
                    return_value={},
                )
            )
            ctx.enter_context(
                patch(
                    "services.content_engine.cross_platform_engine.ExportRecordService.save_exports",
                    new_callable=AsyncMock,
                )
            )

            result = await handle_tool_call(
                "lumina_generate_content",
                {"topic": "10分钟居家无器械跟练", "platform": "bilibili"},
                user_id="u-malformed-persona",
                conversation_id="c-malformed-persona",
                platform="bilibili",
                user_message="帮我生成一个可分享的B站文章",
            )

        data = json.loads(result)
        assert data["ok"] is True, data.get("error")
        assert any(u["platform"] == "bilibili" for u in data.get("export_urls", []))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
