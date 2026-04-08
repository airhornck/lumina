"""LiteLLM 异步封装。"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional

from llm_hub.config_models import LLMConfig


def litellm_model_id(cfg: LLMConfig) -> str:
    if cfg.provider == "openai":
        return f"openai/{cfg.model}"
    if cfg.provider == "anthropic":
        return f"anthropic/{cfg.model}"
    if cfg.provider == "deepseek":
        return f"deepseek/{cfg.model}"
    if cfg.provider == "qwen":
        return f"dashscope/{cfg.model}"
    return cfg.model


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    async def complete(
        self,
        prompt: str,
        *,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        import litellm

        temp = self.config.temperature if temperature is None else temperature
        mt = self.config.max_tokens if max_tokens is None else max_tokens
        model = litellm_model_id(self.config)
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temp,
            "max_tokens": mt,
            "timeout": self.config.timeout,
        }
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        if response_format and self.config.provider == "openai":
            kwargs["response_format"] = response_format
        resp = await litellm.acompletion(**kwargs)
        choice = resp.choices[0]
        return (choice.message.content or "").strip()

    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """流式输出文本增量（SSE 层由调用方封装）。"""
        import litellm

        temp = self.config.temperature if temperature is None else temperature
        mt = self.config.max_tokens if max_tokens is None else max_tokens
        model = litellm_model_id(self.config)
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": mt,
            "timeout": self.config.timeout,
            "stream": True,
        }
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        stream = await litellm.acompletion(**kwargs)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            piece = getattr(delta, "content", None) or ""
            if piece:
                yield piece
