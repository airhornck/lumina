from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from llm_hub import get_client

logger = logging.getLogger(__name__)

SUMMARY_MAX_CHARS = 20


class ContentSummarizer:
    """为平台内容生成短摘要。

    摘要要求：
    - 严格控制在 20 个字符以内；
    - 不含标点符号；
    - 优先调用 LLM 生成，失败或不可用时使用兜底规则。
    """

    def __init__(self, max_chars: int = SUMMARY_MAX_CHARS) -> None:
        self.max_chars = max_chars

    async def summarize(
        self,
        content: Dict[str, Any],
        platform: Optional[str] = None,
    ) -> str:
        """根据内容字典生成摘要。

        Args:
            content: 包含 title / body / content / hashtags 等内容字段的字典。
            platform: 平台标识，仅用于日志或 prompt 上下文；master 可传 None。

        Returns:
            20 字符以内、不含标点的摘要字符串。
        """
        title = content.get("title", "")
        body = content.get("body", content.get("content", ""))

        client = get_client(skill_name="cross_platform_content")
        if not client:
            client = get_client()

        if not client or not client.config.api_key:
            logger.warning("No LLM client available for summary generation")
            return self._fallback(title, body)

        prompt = self._build_prompt(title, body, platform)
        try:
            response = await client.complete(
                prompt=prompt,
                temperature=0.3,
                max_tokens=120,
            )
            if not response or not response.strip():
                raise ValueError("Empty LLM response for summary")
            normalized = self._normalize(response)
            if normalized:
                return normalized
            raise ValueError("Normalized summary is empty")
        except Exception:
            logger.exception("Summary generation failed for platform=%s", platform)
            return self._fallback(title, body)

    def _build_prompt(
        self,
        title: str,
        body: str,
        platform: Optional[str] = None,
    ) -> str:
        platform_hint = f"面向平台：{platform}\n" if platform else ""
        return (
            "请为以下内容生成一段简短摘要。要求：\n"
            "1. 仅保留汉字、数字、英文字母；\n"
            f"2. 字数严格控制在 {self.max_chars} 字以内；\n"
            "3. 不要包含任何标点符号、表情、特殊字符；\n"
            "4. 突出内容核心卖点或价值点；\n"
            "5. 直接返回摘要文本，不要解释、不要加引号。\n\n"
            f"{platform_hint}"
            f"标题：{title}\n"
            f"正文：{body}\n"
        )

    def _fallback(self, title: str, body: str) -> str:
        """兜底：从标题+正文提取前 20 个非标点字符。"""
        combined = f"{title}{body}".strip()
        return self._normalize(combined)

    def _normalize(self, text: str) -> str:
        """去除所有标点与空白，截断到 max_chars。"""
        if not text:
            return ""
        # 移除所有非文字、非数字字符（含标点、空格、换行、制表符等）
        text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", text)
        return text[: self.max_chars]
