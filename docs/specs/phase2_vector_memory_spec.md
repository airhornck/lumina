# Phase 2 向量记忆 SPECIFICATION

> 文档版本：v1.0
> 日期：2026-07-07
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

在现有 PostgreSQL 持久化记忆之上，引入向量语义检索能力。让 Lumina 能够记住用户的内容风格、历史爆款、偏好设置，并在新对话中基于语义相似度召回相关记忆。

### 1.2 用户故事

> 作为用户，我希望 Lumina 记得我以前喜欢什么风格、哪些笔记表现好，这样下次生成内容时能自动延续我的调性。

---

## 二、输入输出边界

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | str | 是 | 用户唯一标识 |
| `conversation_id` | str | 否 | 当前会话 ID |
| `query` | str | 是 | 语义检索文本 |
| `top_k` | int | 否 | 返回条数，默认 5 |
| `memory_type` | str | 否 | 过滤记忆类型，如 `style`, `hit`, `preference` |

### 2.2 输出

```json
{
  "results": [
    {
      "id": "...",
      "memory_type": "style",
      "content": "...",
      "metadata": {},
      "score": 0.92
    }
  ]
}
```

### 2.3 边界条件

| 场景 | 预期行为 |
|------|----------|
| pgvector 未安装 | Feature Flag 关闭，走原关键词匹配 |
| 无匹配记忆 | 返回空列表 |
| embedding 服务不可用 | 降级为 trgm 文本相似搜索 |

---

## 三、核心业务规则

### 3.1 数据库设计

使用 pgvector 扩展，新增表：

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memory_embeddings (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    memory_type VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_user_type
    ON memory_embeddings (user_id, memory_type);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_vector
    ON memory_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

### 3.2 Embedding 生成

- 默认使用 OpenAI `text-embedding-3-small`（1536 维）。
- 通过 `llm_hub` 或 liteLLM 调用 embedding 接口。
- 生成失败时降级为 trgm 相似度。

### 3.3 记忆写入

在 `PostgresChatMemoryStore.append` 中，当 Feature Flag `LUMINA_USE_VECTOR_MEMORY=true` 时：
- 同步生成 embedding。
- 写入 `memory_embeddings` 表。
- `memory_type` 根据 capability / role 推断，默认 `chat`。

### 3.4 记忆检索

提供 `VectorMemoryStore.search(user_id, query, top_k=5, memory_type=None)`：
- 生成 query embedding。
- 执行 `ORDER BY embedding <=> query_embedding LIMIT top_k`。
- 返回 content + score。

---

## 四、Feature Flag

```bash
LUMINA_USE_VECTOR_MEMORY=false   # 默认关闭
LUMINA_USE_VECTOR_MEMORY=true    # 启用向量记忆
```

---

## 五、接口兼容性声明

- 不修改现有 `/api/v1/debug/chat/stream` SSE 格式。
- 记忆查询接口保持兼容。
- 向量记忆对现有对话流程透明。

---

## 六、测试用例（TDD Harness）

### 6.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_vector_extension_available | mock pool | 能执行 `CREATE EXTENSION vector` |
| test_embedding_generation | text | 返回 1536 维向量 |
| test_memory_embedding_write | user_id, content | memory_embeddings 表有记录 |
| test_semantic_search | query | 返回按 cosine 相似度排序的结果 |
| test_feature_flag_disabled | flag=false | 不写入向量记忆 |
| test_fallback_to_trgm | embedding 失败 | 使用 pg_trgm 返回结果 |

---

## 七、实现文件

| 文件 | 说明 |
|------|------|
| 修改 `docker-compose.yml` | 使用 `pgvector/pgvector:pg16` 镜像 |
| 修改 `infra/sql/init.sql` | 添加 vector 扩展与 memory_embeddings 表 |
| 新增 `apps/api/src/chat_debug/vector_memory.py` | VectorMemoryStore 实现 |
| 修改 `apps/api/src/chat_debug/memory_postgres.py` | append 时可选写入 embedding |
| 新增 `tests/phase2/test_vector_memory.py` | 单元测试 |

---

## 八、风险与回滚

| 风险 | 缓解 |
|------|------|
| pgvector 镜像不可用 | 保留 postgres 镜像，关闭 Feature Flag |
| embedding API 延迟 | 异步写入，失败降级 |
| 向量维度不匹配 | 统一使用 1536 维 |

**回滚**：设置 `LUMINA_USE_VECTOR_MEMORY=false`。
