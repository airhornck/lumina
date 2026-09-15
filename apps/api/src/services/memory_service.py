from __future__ import annotations

from typing import Any, Dict, List

from chat_debug.memory import ChatMemoryStore, get_memory_store


class ServiceMemoryStore:
    """基于现有 ChatMemoryStore 的服务级别记忆隔离封装。

    隔离维度：(user_id, conversation_id)
    注：不再按 service 拼接 conversation_id 后缀，统一使用 bare conversation_id
        存库/查询，避免 debug-chat 与 system-chat 两套接口数据隔离。
    """

    def __init__(self, backend: ChatMemoryStore | None = None) -> None:
        self._backend = backend or get_memory_store()

    async def append(
        self,
        user_id: str,
        conversation_id: str,
        service: str,
        role: str,
        content: str,
    ) -> None:
        # service 参数保留签名兼容，不再参与 conversation_id 构建
        await self._backend.append(user_id, conversation_id, role, content)

    async def list_messages(
        self,
        user_id: str,
        conversation_id: str,
        service: str,
        limit: int | None = None,
        offset: int = 0,
        order: str = "asc",
    ) -> List[Dict[str, Any]]:
        return await self._backend.list_messages(
            user_id, conversation_id, limit=limit, offset=offset, order=order
        )

    async def count_messages(self, user_id: str, conversation_id: str, service: str) -> int:
        return await self._backend.count_messages(user_id, conversation_id)

    async def clear(self, user_id: str, conversation_id: str, service: str) -> None:
        await self._backend.clear(user_id, conversation_id)


_mem_store: ServiceMemoryStore | None = None


def get_service_memory_store() -> ServiceMemoryStore:
    global _mem_store
    if _mem_store is None:
        _mem_store = ServiceMemoryStore()
    return _mem_store
