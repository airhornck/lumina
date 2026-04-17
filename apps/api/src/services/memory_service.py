from __future__ import annotations

from typing import Any, Dict, List

from chat_debug.memory import ChatMemoryStore, get_memory_store


class ServiceMemoryStore:
    """基于现有 ChatMemoryStore 的服务级别记忆隔离封装。

    隔离维度：(user_id, conversation_id, service)
    """

    def __init__(self, backend: ChatMemoryStore | None = None) -> None:
        self._backend = backend or get_memory_store()

    def _build_conv_id(self, conversation_id: str, service: str) -> str:
        return f"{conversation_id}::{service}"

    async def append(
        self,
        user_id: str,
        conversation_id: str,
        service: str,
        role: str,
        content: str,
    ) -> None:
        conv = self._build_conv_id(conversation_id, service)
        await self._backend.append(user_id, conv, role, content)

    async def list_messages(
        self, user_id: str, conversation_id: str, service: str
    ) -> List[Dict[str, Any]]:
        conv = self._build_conv_id(conversation_id, service)
        return await self._backend.list_messages(user_id, conv)

    async def clear(self, user_id: str, conversation_id: str, service: str) -> None:
        conv = self._build_conv_id(conversation_id, service)
        await self._backend.clear(user_id, conv)


_mem_store: ServiceMemoryStore | None = None


def get_service_memory_store() -> ServiceMemoryStore:
    global _mem_store
    if _mem_store is None:
        _mem_store = ServiceMemoryStore()
    return _mem_store
