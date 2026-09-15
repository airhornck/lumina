from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.content_engine.cross_platform_engine import CrossPlatformEngine
from services.content_engine.summarizer import ContentSummarizer


class TestContentSummarizer:
    def test_normalize_removes_punctuation_and_truncates(self) -> None:
        summarizer = ContentSummarizer()
        # 含标点、空格、换行，应被清理并截断到 20 字符
        text = "你好，世界！这是一个很长的句子，需要被截断。"
        result = summarizer._normalize(text)
        assert len(result) <= 20
        assert "，" not in result
        assert "。" not in result
        assert " " not in result
        assert result == "你好世界这是一个很长的句子需要被截断"

    def test_normalize_keeps_alphanumeric(self) -> None:
        summarizer = ContentSummarizer()
        text = "Lumina v2.0 发布，支持 AI 营销！"
        result = summarizer._normalize(text)
        assert "Lumina" in result
        assert "v20" in result
        assert "发布" in result
        assert "支持" in result
        assert "AI" in result
        assert "." not in result

    def test_fallback_returns_normalized_text(self) -> None:
        summarizer = ContentSummarizer()
        result = summarizer._fallback("标题内容", "正文正文正文")
        assert len(result) <= 20
        assert result == "标题内容正文正文正文"

    @pytest.mark.asyncio
    async def test_summarize_uses_llm_and_normalizes(self) -> None:
        summarizer = ContentSummarizer()
        mock_client = MagicMock()
        mock_client.config.api_key = "test-key"
        mock_client.complete = AsyncMock(return_value="这是 LLM 生成的，摘要！")

        with patch("services.content_engine.summarizer.get_client", return_value=mock_client):
            result = await summarizer.summarize(
                {"title": "标题", "content": "正文内容"}, platform="xiaohongshu"
            )

        assert len(result) <= 20
        assert result == "这是LLM生成的摘要"
        mock_client.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_summarize_fallback_when_llm_fails(self) -> None:
        summarizer = ContentSummarizer()
        mock_client = MagicMock()
        mock_client.config.api_key = "test-key"
        mock_client.complete = AsyncMock(side_effect=RuntimeError("LLM error"))

        with patch("services.content_engine.summarizer.get_client", return_value=mock_client):
            result = await summarizer.summarize(
                {"title": "标题", "content": "正文内容"}, platform="xiaohongshu"
            )

        assert len(result) <= 20
        assert result == "标题正文内容"

    @pytest.mark.asyncio
    async def test_summarize_fallback_when_no_client(self) -> None:
        summarizer = ContentSummarizer()

        with patch("services.content_engine.summarizer.get_client", return_value=None):
            result = await summarizer.summarize(
                {"title": "标题", "content": "正文内容"}, platform="xiaohongshu"
            )

        assert len(result) <= 20
        assert result == "标题正文内容"


class TestCrossPlatformEngineFieldExtraction:
    def test_extract_required_content_filters_required_fields(self) -> None:
        engine = CrossPlatformEngine()
        spec = MagicMock()
        spec.content_formats = {
            "图文": {
                "title": {"max_chars": 20, "required": True},
                "content": {"max_chars": 1000, "required": True},
                "tags": {"max_count": 10, "required": False},
                "pic_size": {"max": "32MB"},  # 没有 required 字段
            }
        }

        result = engine._extract_required_content(spec, "图文")

        assert set(result.keys()) == {"title", "content"}
        assert result["title"]["max_chars"] == 20
        assert result["content"]["max_chars"] == 1000

    def test_extract_required_content_empty_for_unknown_content_type(self) -> None:
        engine = CrossPlatformEngine()
        spec = MagicMock()
        spec.content_formats = {"图文": {"title": {"required": True}}}

        result = engine._extract_required_content(spec, "不存在类型")

        assert result == {}

    def test_extract_required_content_empty_for_none_spec(self) -> None:
        engine = CrossPlatformEngine()
        result = engine._extract_required_content(None, "图文")
        assert result == {}
