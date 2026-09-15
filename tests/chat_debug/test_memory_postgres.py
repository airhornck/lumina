"""Phase 0 TDD Harness：持久化对话记忆 Red 状态测试。"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def unique_conv():
    return f"test-{uuid.uuid4().hex[:8]}"


async def _get_store():
    from chat_debug.memory_postgres import PostgresChatMemoryStore

    dsn = os.environ.get("DATABASE_URL")
    return PostgresChatMemoryStore(dsn=dsn, max_messages_per_conv=200)


async def test_append_and_list(unique_conv):
    store = await _get_store()
    user_id = "test-user"
    await store.append(user_id, unique_conv, "user", "你好")
    await store.append(user_id, unique_conv, "assistant", "有什么可以帮你？")
    messages = await store.list_messages(user_id, unique_conv)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Requires PostgreSQL DATABASE_URL",
)
async def test_persistence_across_instances(unique_conv):
    user_id = "test-user"
    dsn = os.environ.get("DATABASE_URL")

    from chat_debug.memory_postgres import PostgresChatMemoryStore

    store_a = PostgresChatMemoryStore(dsn=dsn)
    await store_a.append(user_id, unique_conv, "user", "持久化测试")

    store_b = PostgresChatMemoryStore(dsn=dsn)
    messages = await store_b.list_messages(user_id, unique_conv)
    assert any(m["content"] == "持久化测试" for m in messages)


async def test_clear(unique_conv):
    store = await _get_store()
    user_id = "test-user"
    await store.append(user_id, unique_conv, "user", "消息")
    await store.clear(user_id, unique_conv)
    messages = await store.list_messages(user_id, unique_conv)
    assert messages == []


async def test_max_messages(unique_conv):
    """Phase 1：取消 200 条滚动截断，历史全量保留。"""
    store = await _get_store()
    user_id = "test-user"
    for i in range(250):
        await store.append(user_id, unique_conv, "user", f"msg-{i}")
    messages = await store.list_messages(user_id, unique_conv)
    assert len(messages) == 250
    assert messages[0]["content"] == "msg-0"
    assert messages[-1]["content"] == "msg-249"


async def test_capability_field(unique_conv):
    store = await _get_store()
    user_id = "test-user"
    await store.append(
        user_id, unique_conv, "user", "帮我写文案", capability="system_chat"
    )
    messages = await store.list_messages(user_id, unique_conv)
    assert messages[0].get("capability") == "system_chat"


async def test_empty_list(unique_conv):
    store = await _get_store()
    messages = await store.list_messages("test-user", unique_conv)
    assert messages == []


async def test_concurrent_appends(unique_conv):
    store = await _get_store()
    user_id = "test-user"

    async def append_many(start: int):
        for i in range(start, start + 50):
            await store.append(user_id, unique_conv, "user", f"msg-{i}")

    await asyncio.gather(
        append_many(0), append_many(50), append_many(100), append_many(150)
    )
    messages = await store.list_messages(user_id, unique_conv)
    assert len(messages) == 200
