"""Lumina 记忆提供器，让 Hermes 使用 Lumina 的记忆层。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class LuminaMemoryProvider:
    """Hermes MemoryProvider 实现，使用 Lumina ChatMemoryStore。"""

    def __init__(self, sync_writes: bool = True) -> None:
        # sync_writes=False 时仅提供 lumina_search_memory 工具，
        # 不在 sync_turn 写库（由 router/adapter 负责写入，避免重复）。
        self._sync_writes = sync_writes

    @property
    def name(self) -> str:
        return "lumina"

    def is_available(self) -> bool:
        try:
            from chat_debug.memory import get_memory_store

            get_memory_store()
            return True
        except Exception:
            return False

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self.session_id = session_id
        self.user_id = kwargs.get("user_id", "anonymous")

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "lumina_search_memory",
                    "description": "搜索当前对话的历史记忆",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索关键词",
                            }
                        },
                        "required": ["query"],
                    },
                },
            }
        ]

    async def handle_tool_call(
        self, tool_name: str, args: Dict[str, Any], **kwargs: Any
    ) -> str:
        if tool_name != "lumina_search_memory":
            return json.dumps({"ok": False, "error": f"Unknown memory tool: {tool_name}"})

        query = args.get("query", "")
        session_id = kwargs.get("session_id") or getattr(self, "session_id", "")
        user_id = kwargs.get("user_id") or getattr(self, "user_id", "anonymous")

        try:
            from chat_debug.memory import get_memory_store

            store = get_memory_store()
            messages = await store.list_messages(user_id, session_id)
            # 简单过滤：包含关键词的消息
            filtered = [
                m
                for m in messages
                if query.lower() in str(m.get("content", "")).lower()
            ]
            return json.dumps({"ok": True, "result": filtered[:10]})
        except Exception as e:
            logger.warning("lumina_search_memory failed: %s", e)
            return json.dumps({"ok": True, "result": []})

    async def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        session_id: str = "",
        messages: List[Dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        if not self._sync_writes:
            return
        user_id = kwargs.get("user_id") or getattr(self, "user_id", "anonymous")
        conv_id = session_id or getattr(self, "session_id", "")
        if not conv_id:
            return

        try:
            from chat_debug.memory import get_memory_store

            store = get_memory_store()
            await store.append(
                user_id, conv_id, "user", user_content, capability="system_chat"
            )
            await store.append(
                user_id, conv_id, "assistant", assistant_content, capability="system_chat"
            )
        except Exception as e:
            logger.warning("Failed to sync turn to Lumina memory: %s", e)
