"""LLM Token 用量上报回调注册机制。

llm-hub 包本身不依赖任何数据库代码；
调用方（如 apps/api）在 lifespan 中注册具体的存储实现。
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

UsageCallback = Callable[
    [str, str, int, int, int, Optional[str]],
    Awaitable[None],
]
"""
签名: async def callback(
    user_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    skill_name: Optional[str],
) -> None
"""

_reporter: Optional[UsageCallback] = None


def set_usage_reporter(callback: UsageCallback) -> None:
    """注册全局用量上报回调。"""
    global _reporter
    _reporter = callback


def get_usage_reporter() -> Optional[UsageCallback]:
    """获取当前已注册的上报回调。"""
    return _reporter


async def report_usage(
    user_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    skill_name: Optional[str] = None,
) -> None:
    """触发上报（若已注册 reporter）。"""
    if _reporter is not None:
        await _reporter(
            user_id, model, prompt_tokens, completion_tokens, total_tokens, skill_name
        )
