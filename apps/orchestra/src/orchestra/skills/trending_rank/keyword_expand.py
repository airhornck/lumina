"""关键词泛化引擎。"""

from __future__ import annotations

import json
import logging

from llm_hub import get_client, get_hub

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """你是关键词泛化专家。
请将用户输入的关键词扩展为同义词、近义词、行业黑话和相关搜索词。
只输出 JSON 数组，最多 10 个，不要任何额外说明。

示例输入：护肤
示例输出：["护肤","skincare","成分党","平价护肤","敏感肌","早C晚A","屏障修护","以油养肤","精简护肤","油皮护肤"]"""


async def expand_keywords(keyword: str) -> list[str]:
    """使用 LLM 扩展关键词。"""
    hub = get_hub()
    if not hub:
        return [keyword]

    client = get_client(skill_name="debug_chat")
    if not client or not client.config.api_key:
        return [keyword]

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": keyword},
    ]

    try:
        pieces: list[str] = []
        async for piece in client.stream_completion(messages):
            pieces.append(piece)
        text = "".join(pieces)

        # 尝试提取 JSON 数组
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            arr = json.loads(text[start : end + 1])
            if isinstance(arr, list) and arr:
                return [str(x).strip() for x in arr[:10]]
    except Exception as e:
        logger.warning("Keyword expansion failed: %s", e)

    return [keyword]
