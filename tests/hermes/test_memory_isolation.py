"""记忆/Agent 按 user_id 隔离的测试。

回归背景：adapter 曾以 conversation_id 作为 agent 缓存唯一键，
不同用户共用会话 ID（如 debug 前端默认 debug-conv）时会共享同一个
AIAgent 实例（hermes session + 记忆 provider 均泄漏给先创建者）。
"""

from __future__ import annotations


def test_agent_cache_key_isolated_by_user():
    from services.hermes_adapter import HermesEngineAdapter

    k1 = HermesEngineAdapter._agent_cache_key("user-a", "conv-1")
    k2 = HermesEngineAdapter._agent_cache_key("user-b", "conv-1")
    assert k1 != k2, "同一 conversation_id 不同 user_id 必须得到不同缓存键"


def test_agent_cache_key_stable_and_safe():
    from services.hermes_adapter import HermesEngineAdapter

    k = HermesEngineAdapter._agent_cache_key("user-a", "conv-1")
    assert k == HermesEngineAdapter._agent_cache_key("user-a", "conv-1")
    # session_id 会进 hermes 会话文件路径，不能含 Windows 非法字符
    assert not any(ch in k for ch in '<>:"/\\|?*')


def test_agent_cache_key_empty_conversation():
    from services.hermes_adapter import HermesEngineAdapter

    assert HermesEngineAdapter._agent_cache_key("user-a", "") == "anon-user-a"
    assert HermesEngineAdapter._agent_cache_key("user-a", "") != (
        HermesEngineAdapter._agent_cache_key("user-b", "")
    )


def test_chat_memory_store_isolated_by_user():
    """chat_debug 记忆库按 (user_id, conversation_id) 隔离。"""
    import asyncio

    from chat_debug.memory import ChatMemoryStore

    async def _run():
        store = ChatMemoryStore()
        await store.append("user-a", "conv-1", "user", "A 的消息")
        await store.append("user-b", "conv-1", "user", "B 的消息")
        a = await store.list_messages("user-a", "conv-1")
        b = await store.list_messages("user-b", "conv-1")
        assert [m["content"] for m in a] == ["A 的消息"]
        assert [m["content"] for m in b] == ["B 的消息"]
        await store.clear("user-a", "conv-1")
        assert await store.list_messages("user-a", "conv-1") == []
        assert len(await store.list_messages("user-b", "conv-1")) == 1

    asyncio.run(_run())


def test_service_memory_store_isolated_by_user():
    """services 记忆库按 (user_id, conversation_id) 隔离。"""
    import asyncio

    from chat_debug.memory import ChatMemoryStore
    from services.memory_service import ServiceMemoryStore

    async def _run():
        store = ServiceMemoryStore(ChatMemoryStore())
        await store.append("user-a", "conv-1", "system-chat", "user", "A")
        await store.append("user-b", "conv-1", "system-chat", "user", "B")
        a = await store.list_messages("user-a", "conv-1", "system-chat")
        b = await store.list_messages("user-b", "conv-1", "system-chat")
        assert [m["content"] for m in a] == ["A"]
        assert [m["content"] for m in b] == ["B"]

    asyncio.run(_run())
