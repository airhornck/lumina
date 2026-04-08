from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, DefaultDict, Dict, List, Tuple

Key = Tuple[str, str]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatMemoryStore:
    """按 (user_id, conversation_id) 隔离的对话记忆（进程内，调试用）。"""

    def __init__(self, max_messages_per_conv: int = 200) -> None:
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

    async def list_messages(self, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        async with self._lock:
            return list(self._data.get((user_id, conversation_id), []))

    async def clear(self, user_id: str, conversation_id: str) -> None:
        async with self._lock:
            self._data.pop((user_id, conversation_id), None)


_store: ChatMemoryStore | None = None


def get_memory_store() -> ChatMemoryStore:
    global _store
    if _store is None:
        _store = ChatMemoryStore()
    return _store
