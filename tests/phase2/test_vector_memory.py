"""Phase 2 TDD Harness：向量记忆测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_vector_extension_ddl():
    """DDL 脚本中必须包含 vector 扩展与 memory_embeddings 表。"""
    from pathlib import Path

    init_sql = Path("infra/sql/init.sql").read_text(encoding="utf-8")
    assert 'CREATE EXTENSION IF NOT EXISTS "vector"' in init_sql
    assert "CREATE TABLE IF NOT EXISTS memory_embeddings" in init_sql


@pytest.mark.asyncio
async def test_embedding_generation():
    """模拟 embedding 生成返回 1536 维向量。"""
    from chat_debug.vector_memory import EmbeddingGenerator

    generator = EmbeddingGenerator(model="text-embedding-3-small")
    with patch.object(generator, "_generate", new=AsyncMock(return_value=[0.1] * 1536)):
        vec = await generator.generate("hello")
    assert len(vec) == 1536


@pytest.mark.asyncio
async def test_memory_embedding_write():
    """Feature Flag 开启时写入 memory_embeddings。"""
    from chat_debug.vector_memory import VectorMemoryStore

    with patch.dict("os.environ", {"LUMINA_USE_VECTOR_MEMORY": "true"}):
        store = VectorMemoryStore(dsn="postgresql://mock")
    store._initialized = True

    class FakeConn:
        execute = AsyncMock(return_value=None)

    class FakeCtx:
        async def __aenter__(self):
            return FakeConn()
        async def __aexit__(self, *args):
            return False

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=FakeCtx())
    store._pool = mock_pool

    with patch.object(store._embedder, "generate", new=AsyncMock(return_value=[0.1] * 1536)):
        await store.add_memory(
            user_id="u1",
            memory_type="style",
            content="喜欢短句和 emoji",
        )

    assert FakeConn.execute.called


@pytest.mark.asyncio
async def test_semantic_search():
    """按 cosine 相似度返回结果。"""
    from chat_debug.vector_memory import VectorMemoryStore

    with patch.dict("os.environ", {"LUMINA_USE_VECTOR_MEMORY": "true"}):
        store = VectorMemoryStore(dsn="postgresql://mock")
    store._initialized = True

    class FakeConn:
        fetch = AsyncMock(
            return_value=[
                {"memory_type": "style", "content": "喜欢 emoji", "metadata": {}, "score": 0.92},
            ]
        )

    class FakeCtx:
        async def __aenter__(self):
            return FakeConn()
        async def __aexit__(self, *args):
            return False

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=FakeCtx())
    store._pool = mock_pool

    with patch.object(store._embedder, "generate", new=AsyncMock(return_value=[0.1] * 1536)):
        results = await store.search("emoji 风格", user_id="u1", top_k=3)

    assert len(results) == 1
    assert results[0]["score"] == 0.92


@pytest.mark.asyncio
async def test_feature_flag_disabled():
    """Flag 关闭时不应初始化向量 store。"""
    from chat_debug.vector_memory import VectorMemoryStore

    with patch.dict("os.environ", {"LUMINA_USE_VECTOR_MEMORY": "false"}):
        store = VectorMemoryStore(dsn="postgresql://mock")
        assert store.enabled is False
