"""Phase 0 TDD Harness：持久化记忆 PostgreSQL 路径 mock 测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


class _FakeRow:
    def __init__(self, **kwargs):
        self._data = kwargs

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key):
        return self._data.get(key)


def _make_pool(rows=None):
    """构造一个 mock asyncpg pool。"""
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=rows or [])
    conn.fetchrow = AsyncMock(return_value=None)

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


async def test_postgres_append_and_list():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool()
    store = PostgresChatMemoryStore(pool=pool, max_messages_per_conv=200)

    await store.append("u1", "c1", "user", "hello")
    assert conn.execute.called

    conn.fetch = AsyncMock(
        return_value=[
            _FakeRow(role="user", content="hello", capability=None, created_at=None),
        ]
    )
    messages = await store.list_messages("u1", "c1")
    assert len(messages) == 1
    assert messages[0]["content"] == "hello"


async def test_postgres_clear():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool()
    store = PostgresChatMemoryStore(pool=pool)

    await store.clear("u1", "c1")
    assert conn.execute.called


async def test_postgres_append_no_cleanup_delete():
    """Phase 1：历史全量保留，append 不再触发滚动删除。"""
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool()
    store = PostgresChatMemoryStore(pool=pool, max_messages_per_conv=10)

    for i in range(15):
        await store.append("u1", "c1", "user", f"msg-{i}")

    # 验证不再发出任何 DELETE（INSERT 后无裁剪）
    delete_calls = [
        call for call in conn.execute.call_args_list if "DELETE" in str(call)
    ]
    assert len(delete_calls) == 0


async def test_postgres_capability_preserved():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool()
    store = PostgresChatMemoryStore(pool=pool)

    await store.append("u1", "c1", "user", "hello", capability="system_chat")
    # 第一个调用是 schema ensure，第二个才是 INSERT
    insert_call = conn.execute.call_args_list[1]
    assert "system_chat" in str(insert_call)


async def test_postgres_schema_ensure_idempotent():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool()
    store = PostgresChatMemoryStore(pool=pool)

    # 第一次调用会执行 schema
    await store._ensure_schema()
    assert conn.execute.called

    # 第二次调用不应该再执行 schema
    conn.execute.reset_mock()
    store._initialized = True
    await store._ensure_schema()
    assert not conn.execute.called


async def test_postgres_append_exception_fallback():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool()
    # 模拟 INSERT 异常
    conn.execute = AsyncMock(side_effect=Exception("connection lost"))
    store = PostgresChatMemoryStore(pool=pool)

    await store.append("u1", "c1", "user", "hello")
    # fallback 到内存后应能读取
    messages = await store.list_messages("u1", "c1")
    assert len(messages) == 1
    assert messages[0]["content"] == "hello"


async def test_postgres_list_exception_fallback():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool()
    # 第一次 append 成功，第二次 list 失败
    store = PostgresChatMemoryStore(pool=pool)
    await store.append("u1", "c1", "user", "hello")

    conn.fetch = AsyncMock(side_effect=Exception("connection lost"))
    # 此时内存 fallback 中没有数据，因为 append 走的是 pg
    messages = await store.list_messages("u1", "c1")
    # 至少验证异常被捕获，不会抛错
    assert messages == []
