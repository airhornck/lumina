"""向量记忆：基于 pgvector 的语义长期记忆。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_DIM = 1536
_CREATE_EXTENSION_SQL = "CREATE EXTENSION IF NOT EXISTS vector;"
_CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS memory_embeddings (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    memory_type VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR({_DIM}),
    metadata JSONB DEFAULT '{{}}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_user_type
    ON memory_embeddings (user_id, memory_type);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_vector
    ON memory_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""


class EmbeddingGenerator:
    """Embedding 生成器，默认使用 OpenAI text-embedding-3-small。"""

    def __init__(self, model: str = "text-embedding-3-small", provider: str = "openai") -> None:
        self.model = model
        self.provider = provider

    async def generate(self, text: str) -> List[float]:
        """生成文本 embedding；失败时返回空列表。"""
        try:
            return await self._generate(text)
        except Exception as e:
            logger.warning("Embedding generation failed: %s", e)
            return []

    async def _generate(self, text: str) -> List[float]:
        import litellm

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
        api_base = os.environ.get("OPENAI_BASE_URL") or os.environ.get("DEEPSEEK_API_BASE")
        model_id = f"{self.provider}/{self.model}"
        kwargs: Dict[str, Any] = {
            "model": model_id,
            "input": text,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base
        resp = await litellm.aembedding(**kwargs)
        data = resp.get("data") if isinstance(resp, dict) else getattr(resp, "data", None)
        if not data:
            return []
        first = data[0]
        embedding = first.get("embedding") if isinstance(first, dict) else getattr(first, "embedding", None)
        if not embedding:
            return []
        return list(embedding)


class VectorMemoryStore:
    """基于 pgvector 的向量记忆存储。"""

    def __init__(
        self,
        dsn: str | None = None,
        pool: Any | None = None,
        embedder: EmbeddingGenerator | None = None,
    ) -> None:
        self._dsn = dsn or os.environ.get("DATABASE_URL")
        self._pool = pool
        self._embedder = embedder or EmbeddingGenerator()
        self._lock = asyncio.Lock()
        self._initialized = False
        self.enabled = os.environ.get("LUMINA_USE_VECTOR_MEMORY", "").lower() in ("true", "1", "yes")

    async def _get_pool(self) -> Any | None:
        if self._pool is not None:
            return self._pool
        from infra.db import get_pool

        pool = get_pool()
        if pool is not None:
            return pool
        if self._dsn:
            try:
                import asyncpg

                self._pool = await asyncpg.create_pool(
                    self._dsn,
                    min_size=1,
                    max_size=3,
                    command_timeout=30,
                )
                return self._pool
            except Exception as e:
                logger.warning("Failed to create postgres pool from dsn: %s", e)
        return None

    async def _ensure_extension(self) -> bool:
        pool = await self._get_pool()
        if pool is None:
            return False
        try:
            async with pool.acquire() as conn:
                await conn.execute(_CREATE_EXTENSION_SQL)
            return True
        except Exception as e:
            logger.warning("Failed to create pgvector extension: %s", e)
            return False

    async def _ensure_schema(self) -> bool:
        if self._initialized:
            return True
        if not await self._ensure_extension():
            return False
        pool = await self._get_pool()
        if pool is None:
            return False
        try:
            async with pool.acquire() as conn:
                await conn.execute(_CREATE_TABLE_SQL)
            self._initialized = True
            return True
        except Exception as e:
            logger.warning("Failed to ensure memory_embeddings schema: %s", e)
            return False

    async def add_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        metadata: Dict[str, Any] | None = None,
    ) -> bool:
        """写入一条带 embedding 的记忆。"""
        if not self.enabled:
            return False
        async with self._lock:
            if not await self._ensure_schema():
                return False
            pool = await self._get_pool()
            if pool is None:
                return False

            embedding = await self._embedder.generate(content)
            if not embedding:
                return False

            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO memory_embeddings
                            (user_id, memory_type, content, embedding, metadata)
                        VALUES ($1, $2, $3, $4::float8[]::vector, $5)
                        """,
                        user_id,
                        memory_type,
                        content,
                        embedding,
                        json.dumps(metadata or {}),
                    )
                return True
            except Exception as e:
                logger.warning("Failed to add vector memory: %s", e)
                return False

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        memory_type: str | None = None,
    ) -> List[Dict[str, Any]]:
        """语义检索记忆。"""
        if not self.enabled:
            return []
        async with self._lock:
            if not await self._ensure_schema():
                return []
            pool = await self._get_pool()
            if pool is None:
                return []

            embedding = await self._embedder.generate(query)
            if not embedding:
                return await self._fallback_trgm_search(query, user_id, top_k, memory_type)

            try:
                async with pool.acquire() as conn:
                    if memory_type:
                        rows = await conn.fetch(
                            """
                            SELECT memory_type, content, metadata,
                                   1 - (embedding <=> $1::float8[]::vector) AS score
                            FROM memory_embeddings
                            WHERE user_id = $2 AND memory_type = $3
                            ORDER BY embedding <=> $1::float8[]::vector
                            LIMIT $4
                            """,
                            embedding,
                            user_id,
                            memory_type,
                            top_k,
                        )
                    else:
                        rows = await conn.fetch(
                            """
                            SELECT memory_type, content, metadata,
                                   1 - (embedding <=> $1::float8[]::vector) AS score
                            FROM memory_embeddings
                            WHERE user_id = $2
                            ORDER BY embedding <=> $1::float8[]::vector
                            LIMIT $3
                            """,
                            embedding,
                            user_id,
                            top_k,
                        )
                return [
                    {
                        "memory_type": row["memory_type"],
                        "content": row["content"],
                        "metadata": row["metadata"] or {},
                        "score": float(row["score"]),
                    }
                    for row in rows
                ]
            except Exception as e:
                logger.warning("Vector memory search failed: %s", e)
                return await self._fallback_trgm_search(query, user_id, top_k, memory_type)

    async def _fallback_trgm_search(
        self,
        query: str,
        user_id: str,
        top_k: int,
        memory_type: str | None,
    ) -> List[Dict[str, Any]]:
        """embedding 失败时降级为 trgm 文本相似搜索。"""
        pool = await self._get_pool()
        if pool is None:
            return []
        try:
            async with pool.acquire() as conn:
                if memory_type:
                    rows = await conn.fetch(
                        """
                        SELECT memory_type, content, metadata,
                               similarity(content, $1) AS score
                        FROM memory_embeddings
                        WHERE user_id = $2 AND memory_type = $3
                        ORDER BY content <-> $1
                        LIMIT $4
                        """,
                        query,
                        user_id,
                        memory_type,
                        top_k,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT memory_type, content, metadata,
                               similarity(content, $1) AS score
                        FROM memory_embeddings
                        WHERE user_id = $2
                        ORDER BY content <-> $1
                        LIMIT $3
                        """,
                        query,
                        user_id,
                        top_k,
                    )
            return [
                {
                    "memory_type": row["memory_type"],
                    "content": row["content"],
                    "metadata": row["metadata"] or {},
                    "score": float(row["score"]),
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning("Trgm fallback search failed: %s", e)
            return []

