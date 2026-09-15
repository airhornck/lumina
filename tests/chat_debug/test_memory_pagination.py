"""Phase 1：对话历史分页（limit/offset/order + count_messages）测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from chat_debug.memory import ChatMemoryStore, slice_latest


async def _seed(store, n, user="u1", conv="c1"):
    for i in range(n):
        await store.append(user, conv, "user", f"msg-{i}")


# ---------- slice_latest 纯函数 ----------


def test_slice_latest_default_returns_all_asc():
    msgs = [{"content": f"m{i}"} for i in range(5)]
    assert [m["content"] for m in slice_latest(msgs)] == [f"m{i}" for i in range(5)]


def test_slice_latest_limit_and_offset():
    msgs = [{"content": f"m{i}"} for i in range(10)]
    assert [m["content"] for m in slice_latest(msgs, limit=3)] == ["m7", "m8", "m9"]
    assert [m["content"] for m in slice_latest(msgs, limit=3, offset=3)] == ["m4", "m5", "m6"]
    assert slice_latest(msgs, limit=3, offset=20) == []


def test_slice_latest_order_desc():
    msgs = [{"content": f"m{i}"} for i in range(5)]
    assert [m["content"] for m in slice_latest(msgs, limit=2, order="desc")] == ["m4", "m3"]
    assert [m["content"] for m in slice_latest(msgs, order="desc")] == [
        f"m{i}" for i in range(4, -1, -1)
    ]


# ---------- 内存实现 ----------


async def test_memory_list_limit_returns_latest_n_asc():
    store = ChatMemoryStore()
    await _seed(store, 10)
    msgs = await store.list_messages("u1", "c1", limit=3)
    assert [m["content"] for m in msgs] == ["msg-7", "msg-8", "msg-9"]


async def test_memory_list_offset_pages_earlier():
    store = ChatMemoryStore()
    await _seed(store, 10)
    msgs = await store.list_messages("u1", "c1", limit=3, offset=3)
    assert [m["content"] for m in msgs] == ["msg-4", "msg-5", "msg-6"]


async def test_memory_list_offset_beyond_range_returns_empty():
    store = ChatMemoryStore()
    await _seed(store, 5)
    assert await store.list_messages("u1", "c1", limit=3, offset=10) == []


async def test_memory_list_order_desc():
    store = ChatMemoryStore()
    await _seed(store, 5)
    msgs = await store.list_messages("u1", "c1", limit=2, order="desc")
    assert [m["content"] for m in msgs] == ["msg-4", "msg-3"]


async def test_memory_count_messages():
    store = ChatMemoryStore()
    await _seed(store, 7)
    assert await store.count_messages("u1", "c1") == 7
    assert await store.count_messages("u1", "nope") == 0


# ---------- PG 实现（mock pool） ----------


class _FakeRow:
    def __init__(self, **kwargs):
        self._data = kwargs

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key):
        return self._data.get(key)


def _make_pool(rows=None):
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=rows or [])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=0)

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


async def test_pg_list_with_limit_uses_desc_limit_offset():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool(
        rows=[
            _FakeRow(role="user", content="b", capability=None, created_at=None),
            _FakeRow(role="user", content="a", capability=None, created_at=None),
        ]
    )
    store = PostgresChatMemoryStore(pool=pool)

    msgs = await store.list_messages("u1", "c1", limit=2, offset=1)

    sql = str(conn.fetch.call_args_list[0])
    assert "DESC" in sql and "LIMIT" in sql and "OFFSET" in sql
    # DB 取出为倒序 [b, a]，应翻回正序
    assert [m["content"] for m in msgs] == ["a", "b"]


async def test_pg_list_with_limit_order_desc():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool(
        rows=[
            _FakeRow(role="user", content="b", capability=None, created_at=None),
            _FakeRow(role="user", content="a", capability=None, created_at=None),
        ]
    )
    store = PostgresChatMemoryStore(pool=pool)

    msgs = await store.list_messages("u1", "c1", limit=2, order="desc")
    assert [m["content"] for m in msgs] == ["b", "a"]


async def test_pg_list_without_limit_keeps_asc_query():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool(
        rows=[_FakeRow(role="user", content="a", capability=None, created_at=None)]
    )
    store = PostgresChatMemoryStore(pool=pool)

    msgs = await store.list_messages("u1", "c1")

    sql = str(conn.fetch.call_args_list[0])
    assert "ASC" in sql and "LIMIT" not in sql
    assert [m["content"] for m in msgs] == ["a"]


async def test_pg_count_messages():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool()
    conn.fetchval = AsyncMock(return_value=42)
    store = PostgresChatMemoryStore(pool=pool)

    assert await store.count_messages("u1", "c1") == 42
    assert "COUNT" in str(conn.fetchval.call_args_list[0])


async def test_pg_count_messages_fallback_on_error():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    pool, conn = _make_pool()
    conn.fetchval = AsyncMock(side_effect=Exception("connection lost"))
    store = PostgresChatMemoryStore(pool=pool)

    # 内存 fallback 中没有数据 → 0，且异常被吞掉
    assert await store.count_messages("u1", "c1") == 0


# ---------- ServiceMemoryStore 透传 ----------


async def test_service_memory_store_passthrough():
    from services.memory_service import ServiceMemoryStore

    backend = ChatMemoryStore()
    store = ServiceMemoryStore(backend=backend)
    for i in range(10):
        await store.append("u1", "c1", "system-chat", "user", f"msg-{i}")

    msgs = await store.list_messages("u1", "c1", "system-chat", limit=3, offset=1)
    assert [m["content"] for m in msgs] == ["msg-6", "msg-7", "msg-8"]
    assert await store.count_messages("u1", "c1", "system-chat") == 10
    # 合并后不再按 service 隔离 conversation_id，同一 conv 任意 service 共享数据
    assert await store.count_messages("u1", "c1", "other-service") == 10
