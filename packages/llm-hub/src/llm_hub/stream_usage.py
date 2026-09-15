"""按请求（如同一条 SSE）聚合多跳 LLM 的 token 用量。

通过 contextvars 在当前 asyncio Task 内累加，供 `system-chat` v2 的 `done.usage` 等出口读取。
走 `litellm` 直连、且未经过 `LLMClient.complete` 的路径应自行调用 `accumulate_completion_usage`。
"""

from __future__ import annotations

import contextvars
from contextvars import Token
from typing import Any, Dict, Optional

_stream_usage_bucket: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "llm_hub_stream_usage_bucket",
    default=None,
)


def attach_stream_usage_accumulator() -> tuple[Dict[str, Any], Token]:
    """挂载累加器；返回 (bucket, reset_token)。须在 `finally` 中调用 `reset_stream_usage_accumulator(token)`。"""
    bucket: Dict[str, Any] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "partial": False,
    }
    tok = _stream_usage_bucket.set(bucket)
    return bucket, tok


def reset_stream_usage_accumulator(token: Token) -> None:
    _stream_usage_bucket.reset(token)


def accumulate_completion_usage(usage: Any) -> None:
    """从 litellm / OpenAI 风格 usage 对象累加到当前 bucket（若已挂载）。"""
    bucket = _stream_usage_bucket.get()
    if bucket is None or usage is None:
        return
    pt = int(getattr(usage, "prompt_tokens", 0) or 0)
    ct = int(getattr(usage, "completion_tokens", 0) or 0)
    tt = int(getattr(usage, "total_tokens", 0) or 0)
    if tt <= 0:
        tt = pt + ct
    bucket["prompt_tokens"] = int(bucket.get("prompt_tokens", 0)) + pt
    bucket["completion_tokens"] = int(bucket.get("completion_tokens", 0)) + ct
    bucket["total_tokens"] = int(bucket.get("total_tokens", 0)) + tt


def mark_stream_usage_partial() -> None:
    """标记存在未计入的 LLM 路径（如直连 litellm 未接 accumulator）。"""
    bucket = _stream_usage_bucket.get()
    if bucket is not None:
        bucket["partial"] = True


def summarize_usage_for_done(bucket: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """转为 SSE `done.usage` 载荷；无用量且非 partial 时返回 None。"""
    if not bucket:
        return None
    pt = int(bucket.get("prompt_tokens", 0) or 0)
    ct = int(bucket.get("completion_tokens", 0) or 0)
    tt = int(bucket.get("total_tokens", 0) or 0)
    partial = bool(bucket.get("partial"))
    if pt == 0 and ct == 0 and tt == 0 and not partial:
        return None
    out: Dict[str, Any] = {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": tt,
    }
    if partial:
        out["partial"] = True
    return out
