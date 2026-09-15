"""PostgreSQL 持久化对话记忆实现。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from chat_debug.memory import ChatMemoryStore, slice_latest

logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    capability VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chat_messages_role_check CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_user_conv
    ON chat_messages (user_id, conversation_id, created_at);
"""


class PostgresChatMemoryStore(ChatMemoryStore):
    """按 (user_id, conversation_id) 隔离的 PostgreSQL 持久化对话记忆。"""

    def __init__(
        self,
        dsn: str | None = None,
        pool: Any | None = None,
        max_messages_per_conv: int = 10000,
    ) -> None:
        super().__init__(max_messages_per_conv=max_messages_per_conv)
        self._dsn = dsn
        self._pool = pool
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _get_pool(self) -> Any | None:
        if self._pool is not None:
            return self._pool
        from infra.db import get_pool

        pool = get_pool()
        if pool is not None:
            return pool

        # 如果提供了 dsn 但没有全局 pool，使用 dsn 创建独立 pool
        if self._dsn:
            try:
                import asyncpg

                self._pool = await asyncpg.create_pool(
                    self._dsn,
                    min_size=1,
                    max_size=5,
                    command_timeout=30,
                )
                return self._pool
            except Exception as e:
                logger.warning("Failed to create postgres pool from dsn: %s", e)
        return None

    async def _ensure_schema(self) -> bool:
        if self._initialized:
            return True
        pool = await self._get_pool()
        if pool is None:
            return False
        try:
            async with pool.acquire() as conn:
                await conn.execute(_CREATE_TABLE_SQL)
            self._initialized = True
            return True
        except Exception as e:
            logger.warning("Failed to ensure chat_messages schema: %s", e)
            return False

    async def _fallback_append(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        *,
        capability: str | None = None,
    ) -> None:
        logger.warning("Falling back to in-memory chat memory store")
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

    async def append(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        *,
        capability: str | None = None,
    ) -> None:
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {role}")

        async with self._lock:
            if not await self._ensure_schema():
                await self._fallback_append(
                    user_id, conversation_id, role, content, capability=capability
                )
                return

            pool = await self._get_pool()
            if pool is None:
                await self._fallback_append(
                    user_id, conversation_id, role, content, capability=capability
                )
                return

            try:
                async with pool.acquire() as conn:
                    # 历史全量保留（Phase 1 起取消滚动删除），仅追加
                    await conn.execute(
                        """
                        INSERT INTO chat_messages (user_id, conversation_id, role, content, capability)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        user_id,
                        conversation_id,
                        role,
                        content,
                        capability,
                    )
            except Exception as e:
                logger.warning("Failed to append chat message to postgres: %s", e)
                await self._fallback_append(
                    user_id, conversation_id, role, content, capability=capability
                )

    @staticmethod
    def _row_to_dict(row: Any) -> Dict[str, Any]:
        return {
            "role": row["role"],
            "content": row["content"],
            "ts": row["created_at"].isoformat()
            if row["created_at"]
            else _utc_iso(),
            **(
                {"capability": row["capability"]}
                if row["capability"]
                else {}
            ),
        }

    def _fallback_list(
        self,
        user_id: str,
        conversation_id: str,
        limit: int | None,
        offset: int,
        order: str,
    ) -> List[Dict[str, Any]]:
        # 注意：调用方已持有 self._lock，不能再走 super().list_messages（会同锁死锁）
        msgs = list(self._data.get((user_id, conversation_id), []))
        return slice_latest(msgs, limit=limit, offset=offset, order=order)

    async def list_messages(
        self,
        user_id: str,
        conversation_id: str,
        limit: int | None = None,
        offset: int = 0,
        order: str = "asc",
    ) -> List[Dict[str, Any]]:
        """读取消息。limit/offset 为“最新优先”语义：limit=取最新 N 条，offset=跳过最新 N 条。

        默认（limit=None）返回全部，按时间正序；order=\"desc\" 仅翻转返回顺序。
        """
        async with self._lock:
            if not await self._ensure_schema():
                return self._fallback_list(user_id, conversation_id, limit, offset, order)

            pool = await self._get_pool()
            if pool is None:
                return self._fallback_list(user_id, conversation_id, limit, offset, order)

            try:
                async with pool.acquire() as conn:
                    if limit is None:
                        rows = await conn.fetch(
                            """
                            SELECT role, content, capability, created_at
                            FROM chat_messages
                            WHERE user_id = $1 AND conversation_id = $2
                            ORDER BY created_at ASC, id ASC
                            """,
                            user_id,
                            conversation_id,
                        )
                        items = [self._row_to_dict(row) for row in rows]
                    else:
                        rows = await conn.fetch(
                            """
                            SELECT role, content, capability, created_at
                            FROM chat_messages
                            WHERE user_id = $1 AND conversation_id = $2
                            ORDER BY created_at DESC, id DESC
                            LIMIT $3 OFFSET $4
                            """,
                            user_id,
                            conversation_id,
                            limit,
                            offset,
                        )
                        items = [self._row_to_dict(row) for row in rows]
                        items.reverse()  # DB 取出为倒序，翻回正序
                    if order == "desc":
                        items.reverse()
                    return items
            except Exception as e:
                logger.warning("Failed to list chat messages from postgres: %s", e)
                return self._fallback_list(user_id, conversation_id, limit, offset, order)

    async def count_messages(self, user_id: str, conversation_id: str) -> int:
        async with self._lock:
            if not await self._ensure_schema():
                return len(self._data.get((user_id, conversation_id), []))

            pool = await self._get_pool()
            if pool is None:
                return len(self._data.get((user_id, conversation_id), []))

            try:
                async with pool.acquire() as conn:
                    val = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM chat_messages
                        WHERE user_id = $1 AND conversation_id = $2
                        """,
                        user_id,
                        conversation_id,
                    )
                    return int(val or 0)
            except Exception as e:
                logger.warning("Failed to count chat messages from postgres: %s", e)
                return len(self._data.get((user_id, conversation_id), []))

    async def clear(self, user_id: str, conversation_id: str) -> None:
        async with self._lock:
            pool = await self._get_pool()
            if pool is None or not await self._ensure_schema():
                self._data.pop((user_id, conversation_id), None)
                return

            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        DELETE FROM chat_messages
                        WHERE user_id = $1 AND conversation_id = $2
                        """,
                        user_id,
                        conversation_id,
                    )
            except Exception as e:
                logger.warning("Failed to clear chat messages from postgres: %s", e)
                self._data.pop((user_id, conversation_id), None)
