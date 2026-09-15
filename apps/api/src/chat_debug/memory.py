from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, DefaultDict, Dict, List, Tuple

Key = Tuple[str, str]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slice_latest(
    msgs: List[Dict[str, Any]],
    limit: int | None = None,
    offset: int = 0,
    order: str = "asc",
) -> List[Dict[str, Any]]:
    """最新优先语义切片：limit=取最新 N 条，offset=跳过最新 N 条（向更早翻页）。

    默认（limit=None）返回全部；返回默认按时间正序，order=\"desc\" 仅翻转返回顺序。
    """
    out = list(msgs)
    if limit is not None:
        end = max(0, len(out) - offset)
        start = max(0, end - limit)
        out = out[start:end]
    if order == "desc":
        out.reverse()
    return out


class ChatMemoryStore:
    """按 (user_id, conversation_id) 隔离的对话记忆（进程内，调试用）。"""

    def __init__(self, max_messages_per_conv: int = 10000) -> None:
        self._data: DefaultDict[Key, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._max = max_messages_per_conv

    async def append(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        *,
        capability: str | None = None,
    ) -> None:
        async with self._lock:
            key = (user_id, conversation_id)
            row: Dict[str, Any] = {
                "role": role,
                "content": content,
                "ts": _utc_iso(),
            }
            if capability:
                row["capability"] = capability
            self._data[key].append(row)
            if len(self._data[key]) > self._max:
                self._data[key] = self._data[key][-self._max :]

    async def list_messages(
        self,
        user_id: str,
        conversation_id: str,
        limit: int | None = None,
        offset: int = 0,
        order: str = "asc",
    ) -> List[Dict[str, Any]]:
        """读取消息。limit/offset 为“最新优先”语义，见 slice_latest。"""
        async with self._lock:
            msgs = list(self._data.get((user_id, conversation_id), []))
            return slice_latest(msgs, limit=limit, offset=offset, order=order)

    async def count_messages(self, user_id: str, conversation_id: str) -> int:
        async with self._lock:
            return len(self._data.get((user_id, conversation_id), []))

    async def clear(self, user_id: str, conversation_id: str) -> None:
        async with self._lock:
            self._data.pop((user_id, conversation_id), None)


_store: ChatMemoryStore | None = None


def get_memory_store() -> ChatMemoryStore:
    global _store
    if _store is not None:
        return _store

    import os

    backend = os.environ.get("CHAT_MEMORY_BACKEND", "postgres").lower()
    if backend == "postgres":
        try:
            from chat_debug.memory_postgres import PostgresChatMemoryStore

            _store = PostgresChatMemoryStore()
            return _store
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to initialize PostgresChatMemoryStore, falling back to memory"
            )

    _store = ChatMemoryStore()
    return _store
