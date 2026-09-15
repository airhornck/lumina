from __future__ import annotations

from typing import Any


def effective_stream_format(
    body_stream_format: int | None,
    headers: Any,
) -> int:
    """解析流式协议版本：请求体优先于 X-Lumina-Stream-Format；均未指定时默认 1。

    headers 可为 Starlette Headers 或任意带大小写不敏感 .get 的映射。
    """
    header_val: int | None = None
    if headers is not None and hasattr(headers, "get"):
        raw = headers.get("X-Lumina-Stream-Format")
        if raw is not None:
            s = str(raw).strip()
            if s == "2":
                header_val = 2
            elif s == "1":
                header_val = 1

    if body_stream_format is not None:
        return int(body_stream_format)
    if header_val is not None:
        return int(header_val)
    return 1
