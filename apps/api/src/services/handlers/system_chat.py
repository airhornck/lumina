from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List

from services.memory_service import ServiceMemoryStore

logger = logging.getLogger(__name__)

STREAM_CHUNK = 96


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _memory_rows_to_session(rows: List[dict[str, Any]], limit: int = 24) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        if r.get("role") not in ("user", "assistant"):
            continue
        c = r.get("content")
        if not isinstance(c, str):
            continue
        out.append({"role": r["role"], "content": c})
    return out[-limit:]


async def _stream_orchestra_result(text: str) -> AsyncIterator[str]:
    for i in range(0, len(text), STREAM_CHUNK):
        yield text[i : i + STREAM_CHUNK]
        await asyncio.sleep(0)


async def handle_system_chat_stream(
    user_id: str,
    conversation_id: str,
    message: str,
    platform: str | None,
    context: Dict[str, Any],
    store: ServiceMemoryStore,
) -> AsyncIterator[str]:
    service = "system-chat"
    history_before = await store.list_messages(user_id, conversation_id, service)
    await store.append(user_id, conversation_id, service, "user", message)

    hist_rows = [
        r
        for r in history_before
        if r.get("role") in ("user", "assistant") and isinstance(r.get("content"), str)
    ]
    session_history = _memory_rows_to_session(hist_rows)

    yield _sse({"type": "start", "service": service, "via": "marketing_orchestra"})

    try:
        from orchestra.core import MarketingOrchestra

        orch = MarketingOrchestra()
        result = await orch.process(
            message,
            user_id,
            session_history,
            platform,
            context,
        )
        payload = {"ok": True, **result}
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.exception("system_chat orchestra failed")
        yield _sse({"type": "error", "message": str(e)[:800]})
        return

    full_chunks: list[str] = []
    try:
        async for piece in _stream_orchestra_result(text):
            full_chunks.append(piece)
            yield _sse({"type": "delta", "text": piece})
    except Exception as e:
        logger.exception("system_chat stream chunk failed")
        yield _sse({"type": "error", "message": str(e)[:800]})
        return

    full = "".join(full_chunks)
    await store.append(user_id, conversation_id, service, "assistant", full)
    yield _sse({"type": "done", "full_length": len(full)})
