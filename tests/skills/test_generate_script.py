"""
测试 lumina_skills.content.generate_script 的 LLM 生成与降级逻辑。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# 确保 packages 在路径中
for p in (
    Path(__file__).resolve().parents[2] / "packages" / "lumina-skills" / "src",
    Path(__file__).resolve().parents[2] / "packages" / "knowledge-base" / "src",
    Path(__file__).resolve().parents[2] / "packages" / "llm-hub" / "src",
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lumina_skills.content import generate_script


@pytest.fixture
def mock_llm_json():
    """返回一份合法的 LLM 脚本 JSON。"""
    return {
        "hook_script": "你真的知道怎么选防晒霜吗？90%的人都踩过这个坑！",
        "full_script": "（0-3s）你真的知道怎么选防晒霜吗？（3-15s）首先看SPF值...",
        "shot_list": [
            {
                "timestamp": "0-3s",
                "visual": "特写-主播惊讶表情",
                "audio": "语气停顿+轻快节奏入点",
                "text": "你真的知道？",
            },
            {
                "timestamp": "3-15s",
                "visual": "中景-主播手持产品展示",
                "audio": "解说+轻快BGM",
                "text": "SPF值不是越高越好",
            },
        ],
        "bgm_suggestion": "轻快电子，节奏明快，带一点悬疑感，适合种草反转类内容",
        "caption_highlights": ["防晒霜", "SPF值", "90%的人"],
    }


@pytest.fixture
def mock_client(mock_llm_json):
    """构造一个返回合法 JSON 的 mock LLMClient。"""
    client = Mock()
    client.config = Mock()
    client.config.api_key = "sk-test"
    client.complete = AsyncMock(return_value=json.dumps(mock_llm_json, ensure_ascii=False))
    return client


class TestGenerateScriptLLMPath:
    """LLM 正常返回路径的测试。"""

    async def test_returns_expected_fields(self, mock_client, mock_llm_json):
        with patch("lumina_skills.content.get_client", return_value=mock_client):
            result = await generate_script(
                topic="防晒霜选购指南",
                hook_type="curiosity",
                duration=60,
                platform="xiaohongshu",
                user_id="u_test",
                visual_elements=["产品特写"],
                methodology_hint="aida_advanced",
            )

        assert result["hook_script"] == mock_llm_json["hook_script"]
        assert result["full_script"] == mock_llm_json["full_script"]
        assert result["shot_list"] == mock_llm_json["shot_list"]
        assert result["bgm_suggestion"] == mock_llm_json["bgm_suggestion"]
        assert result["caption_highlights"] == mock_llm_json["caption_highlights"]
        assert result["methodology_used"] == "aida_advanced"
        assert result["user_id"] == "u_test"

    async def test_shot_list_parsed_from_string(self, mock_client):
        """当 LLM 把 shot_list 当成字符串返回时，应自动解析。"""
        payload = {
            "hook_script": "钩子",
            "full_script": "正文",
            "shot_list": json.dumps([{"timestamp": "0-3s", "visual": "特写", "audio": "钩子", "text": "文字"}]),
            "bgm_suggestion": "BGM",
            "caption_highlights": ["关键词"],
        }
        mock_client.complete = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False))

        with patch("lumina_skills.content.get_client", return_value=mock_client):
            result = await generate_script(
                topic="test",
                hook_type="test",
                duration=30,
                platform="xiaohongshu",
                user_id="u_test",
            )

        assert isinstance(result["shot_list"], list)
        assert result["shot_list"][0]["timestamp"] == "0-3s"

    async def test_prompt_contains_platform_and_audit_rules(self, mock_client):
        """验证传给 LLM 的 prompt 中包含了平台规范和审核规则。"""
        with patch("lumina_skills.content.get_client", return_value=mock_client):
            await generate_script(
                topic="防晒霜选购",
                hook_type="curiosity",
                duration=45,
                platform="xiaohongshu",
                user_id="u_test",
            )

        call_args = mock_client.complete.call_args
        prompt = call_args[0][0]

        assert "【平台规范】" in prompt
        assert "【平台内容 DNA】" in prompt
        assert "【审核合规】" in prompt
        assert "xiaohongshu" in prompt
        # 小红书的审核规则里有 medical / comparison
        assert "禁用词" in prompt

    async def test_prompt_contains_methodology(self, mock_client):
        """验证 prompt 中包含了方法论指引。"""
        with patch("lumina_skills.content.get_client", return_value=mock_client):
            await generate_script(
                topic="防晒霜选购",
                hook_type="curiosity",
                duration=45,
                platform="xiaohongshu",
                user_id="u_test",
                methodology_hint="aida_advanced",
            )

        prompt = mock_client.complete.call_args[0][0]
        assert "【方法论指引】" in prompt
        assert "aida_advanced" in prompt.lower() or "AIDA" in prompt

    async def test_prompt_estimated_words(self, mock_client):
        """验证 prompt 中按 duration*4 估算了字数。"""
        with patch("lumina_skills.content.get_client", return_value=mock_client):
            await generate_script(
                topic="test",
                hook_type="test",
                duration=60,
                platform="xiaohongshu",
                user_id="u_test",
            )

        prompt = mock_client.complete.call_args[0][0]
        assert "240 字左右" in prompt


class TestGenerateScriptFallbackPath:
    """LLM 失败或不可用时走 fallback 的测试。"""

    async def test_fallback_when_no_api_key(self):
        """当 client.api_key 为空时应走 fallback。"""
        client = Mock()
        client.config = Mock()
        client.config.api_key = None

        with patch("lumina_skills.content.get_client", return_value=client):
            result = await generate_script(
                topic="防晒霜选购",
                hook_type="curiosity",
                duration=60,
                platform="xiaohongshu",
                user_id="u_test",
                visual_elements=["产品特写"],
            )

        assert "系统提示" in result["full_script"]
        assert "脚本生成服务暂时不可用" in result["full_script"]
        assert result["shot_list"][0]["timestamp"] == "0-3s"
        assert result["caption_highlights"] == ["产品特写"]

    async def test_fallback_when_client_none(self):
        """当 get_client 返回 None 时应走 fallback。"""
        with patch("lumina_skills.content.get_client", return_value=None):
            result = await generate_script(
                topic="test",
                hook_type="test",
                duration=30,
                platform="xiaohongshu",
                user_id="u_test",
            )

        assert "系统提示" in result["hook_script"]
        assert "methodology_used" in result

    async def test_fallback_when_complete_raises(self):
        """当 LLM 调用抛异常时应走 fallback。"""
        client = Mock()
        client.config = Mock()
        client.config.api_key = "sk-test"
        client.complete = AsyncMock(side_effect=Exception("LLM timeout"))

        with patch("lumina_skills.content.get_client", return_value=client):
            result = await generate_script(
                topic="test",
                hook_type="test",
                duration=30,
                platform="xiaohongshu",
                user_id="u_test",
            )

        assert "系统提示" in result["full_script"]

    async def test_fallback_preserves_visual_elements(self):
        """fallback 时应保留用户传入的 visual_elements。"""
        with patch("lumina_skills.content.get_client", return_value=None):
            result = await generate_script(
                topic="test",
                hook_type="test",
                duration=30,
                platform="xiaohongshu",
                user_id="u_test",
                visual_elements=["对比图", "使用场景"],
            )

        assert result["caption_highlights"] == ["对比图", "使用场景"]
