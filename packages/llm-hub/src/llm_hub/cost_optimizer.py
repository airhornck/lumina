"""LLM 成本优化：响应缓存、模型降级、Token 监控、长历史摘要。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

CacheBackend = Dict[str, Any]
_CompletionFunc = Callable[..., Awaitable[str]]


def _cache_key(model: str, messages: List[Dict[str, str]], temperature: Optional[float]) -> str:
    """为请求生成确定性缓存键。"""
    normalized = json.dumps(messages, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(f"{model}:{temperature}:{normalized}".encode()).hexdigest()


class CostOptimizedCompletion:
    """带内存缓存的 LLM completion 包装器。"""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._cache: CacheBackend = {}
        self._ttl = ttl_seconds
        self._enabled = os.environ.get("LUMINA_ENABLE_RESPONSE_CACHE", "true").lower() in (
            "true",
            "1",
            "yes",
        )

    def cache_get(self, key: str) -> Optional[str]:
        if not self._enabled:
            return None
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.time() > entry["expires_at"]:
            self._cache.pop(key, None)
            return None
        return entry["value"]

    def cache_set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        if not self._enabled:
            return
        self._cache[key] = {
            "value": value,
            "expires_at": time.time() + (ttl or self._ttl),
        }

    async def complete(
        self,
        model: str,
        messages: List[Dict[str, str]],
        completion_func: _CompletionFunc,
        temperature: Optional[float] = None,
        cache_key: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """优先读缓存，未命中则调用 completion_func 并写入缓存。"""
        key = cache_key or _cache_key(model, messages, temperature)
        cached = self.cache_get(key)
        if cached is not None:
            return cached

        result = await completion_func(model=model, messages=messages, temperature=temperature, **kwargs)
        self.cache_set(key, result)
        return result


class ModelFallback:
    """主模型失败达到一定次数后降级到 cheaper 模型。"""

    def __init__(
        self,
        fallback_model: str,
        failure_threshold: int = 2,
    ) -> None:
        self.fallback_model = fallback_model
        self.failure_threshold = failure_threshold
        self._enabled = os.environ.get("LUMINA_ENABLE_MODEL_FALLBACK", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        self._failures: Dict[str, int] = {}

    async def call(
        self,
        model: str,
        main_func: Callable[..., Awaitable[str]],
        fallback_func: Callable[..., Awaitable[str]],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """调用主模型，失败次数达到阈值则使用 fallback。"""
        if not self._enabled:
            return await main_func(*args, **kwargs)

        failures = self._failures.get(model, 0)
        if failures >= self.failure_threshold:
            logger.info("Using fallback model %s for %s", self.fallback_model, model)
            return await fallback_func(*args, model=self.fallback_model, **kwargs)

        try:
            result = await main_func(*args, **kwargs)
            self._failures[model] = 0
            return result
        except Exception as e:
            self._failures[model] = failures + 1
            logger.warning("Model %s failed (%s/%s): %s", model, failures + 1, self.failure_threshold, e)
            if failures + 1 >= self.failure_threshold:
                logger.info("Switching to fallback model %s", self.fallback_model)
                return await fallback_func(*args, model=self.fallback_model, **kwargs)
            raise


class TokenMonitor:
    """按用户统计 LLM token 消耗并触发告警。"""

    def __init__(
        self,
        hourly_token_limit: int = 100_000,
    ) -> None:
        self.hourly_limit = hourly_token_limit
        self._enabled = os.environ.get("LUMINA_ENABLE_COST_MONITOR", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        self._usage: Dict[str, Dict[str, Any]] = {}

    def _bucket_key(self, user_id: str) -> str:
        now = time.strftime("%Y-%m-%d-%H", time.gmtime())
        return f"{user_id}:{now}"

    def check(
        self,
        user_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> bool:
        """返回是否触发告警。"""
        if not self._enabled:
            return False
        key = self._bucket_key(user_id)
        bucket = self._usage.setdefault(key, {"total_tokens": 0, "models": set()})
        bucket["total_tokens"] += prompt_tokens + completion_tokens
        bucket["models"].add(model)
        alert = bucket["total_tokens"] > self.hourly_limit
        if alert:
            logger.warning(
                "Token usage alert for user %s: %s / %s",
                user_id,
                bucket["total_tokens"],
                self.hourly_limit,
            )
        return alert


class HistorySummarizer:
    """对超长对话历史进行摘要，保留最近 N 条完整消息。"""

    def __init__(
        self,
        keep_recent: int = 6,
        token_threshold: int = 3000,
    ) -> None:
        self.keep_recent = keep_recent
        self.token_threshold = token_threshold
        self._enabled = os.environ.get("LUMINA_ENABLE_HISTORY_SUMMARY", "true").lower() in (
            "true",
            "1",
            "yes",
        )

    def estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """简易 token 估算（4 字符 ≈ 1 token）。"""
        total = 0
        for m in messages:
            total += len(m.get("content", "")) // 4
            total += len(m.get("role", "")) // 4
        return total

    async def summarize(
        self,
        messages: List[Dict[str, str]],
        summarizer_func: Callable[..., Awaitable[str]],
    ) -> List[Dict[str, str]]:
        """若历史超长，对早期消息生成摘要。"""
        if not self._enabled:
            return messages
        if len(messages) <= self.keep_recent + 1:
            return messages
        if self.estimate_tokens(messages) <= self.token_threshold:
            return messages

        to_summarize = messages[: -self.keep_recent]
        recent = messages[-self.keep_recent :]
        prompt = "请将以下对话历史摘要为一段话，保留关键事实、用户偏好和重要结论：\n\n"
        for m in to_summarize:
            prompt += f"{m.get('role', '')}: {m.get('content', '')}\n"
        summary = await summarizer_func(prompt)
        return [{"role": "system", "content": f"历史摘要：{summary}"}] + recent
