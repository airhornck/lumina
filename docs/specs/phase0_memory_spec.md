# Phase 0 持久化对话记忆 SPECIFICATION

> 文档版本：v1.0
> 日期：2026-07-04
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` 5.2 P0-1 对话记忆
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

Lumina 当前使用进程内 `dict` 存储对话记忆（`ChatMemoryStore`），服务重启后记忆全部丢失。本 SPEC 定义如何将对话记忆持久化到 PostgreSQL，同时保持现有接口 100% 兼容。

### 1.2 用户故事

> 作为用户，我希望 AI 记住之前的对话内容，这样我不需要重复说明我的账号信息和偏好。

### 1.3 验收标准（来自业务真源）

- [ ] 同一对话中，AI 能引用之前提到的信息（如账号链接、定位方向）
- [ ] 跨对话中，AI 能记住用户的账号画像（内容类型、风格偏好）
- [ ] 用户说"刚才那个"、"之前说的"时，AI 能正确关联
- [ ] 记忆在服务重启后不丢失

---

## 二、输入输出边界

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | str | 是 | 用户唯一标识，最大长度 128 |
| `conversation_id` | str | 是 | 对话唯一标识，最大长度 128 |
| `role` | str | 是 | 消息角色：`user` / `assistant` / `system` |
| `content` | str | 是 | 消息内容，最大长度 32000 |
| `capability` | str | 否 | 能力标识，如 `system_chat` |

### 2.2 输出

`list_messages()` 返回按时间升序排列的消息列表，每条消息格式：

```python
{
    "role": "user",
    "content": "帮我写个小红书文案",
    "ts": "2026-07-04T14:30:00+00:00",
    "capability": "system_chat"  # 可选
}
```

### 2.3 边界条件

| 场景 | 预期行为 |
|------|----------|
| `DATABASE_URL` 未设置 | 自动降级到内存存储，并记录 warning |
| 数据库连接失败 | 自动降级到内存存储，不阻断服务启动 |
| 同一对话并发写入 | 消息顺序正确，不丢失 |
| 消息数超过 `max_messages_per_conv` | 保留最新的 N 条，旧消息自动丢弃 |
| 空对话查询 | 返回空列表 |
| 非法 role | 允许写入，但 `_memory_rows_to_session()` 只处理 user/assistant |
| 服务重启 | 历史记录从 PostgreSQL 恢复 |

---

## 三、核心业务规则

### 3.1 存储后端选择

通过环境变量 `CHAT_MEMORY_BACKEND` 选择后端：

```bash
CHAT_MEMORY_BACKEND=postgres   # 默认目标
CHAT_MEMORY_BACKEND=memory     # 开发/回滚
```

- 当 `CHAT_MEMORY_BACKEND=postgres` 且 `DATABASE_URL` 有效时，使用 PostgreSQL
- 当数据库不可用时，**自动降级**到内存存储，并记录 warning
- 降级行为必须对用户透明（接口不变）

### 3.2 数据库 Schema

```sql
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
```

### 3.3 接口契约

`ChatMemoryStore` 抽象接口保持不变：

```python
class ChatMemoryStore:
    async def append(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        *,
        capability: str | None = None,
    ) -> None: ...

    async def list_messages(self, user_id: str, conversation_id: str) -> List[Dict[str, Any]]: ...

    async def clear(self, user_id: str, conversation_id: str) -> None: ...
```

新增 `PostgresChatMemoryStore` 实现该接口，原 `ChatMemoryStore` 保留作为内存后端。

### 3.4 数据隔离

- 数据按 `(user_id, conversation_id)` 隔离
- `ServiceMemoryStore` 继续使用 `conversation_id::service` 作为 conversation_id，不改动其逻辑

### 3.5 容量控制

- 默认 `max_messages_per_conv = 200`
- 超出后保留最新的 200 条
- 该控制可在应用层完成，不依赖数据库

---

## 四、错误处理

| 错误场景 | 处理策略 | 返回给用户 |
|----------|----------|------------|
| 数据库写入失败 | 降级到内存，记录 error | 无影响 |
| 数据库读取失败 | 降级到内存（空数据），记录 error | 可能丢失历史 |
| 非法 role | 拒绝写入，抛出 ValueError | 内部错误 |
| content 超长 | 截断或拒绝，取决于调用方 | 由调用方控制 |

---

## 五、安全合规

| 要求 | 实现 |
|------|------|
| SQL 注入防护 | 使用 asyncpg 参数化查询 |
| 用户数据隔离 | 所有查询必须带 `user_id` 过滤 |
| 不暴露敏感信息 | 日志中不打印 content 内容 |
| 最小权限 | 数据库用户仅需要 INSERT/SELECT/DELETE 权限 |

---

## 六、接口兼容性声明

- 不修改 `ChatMemoryStore` 接口
- 不修改 `/api/v1/debug/chat/memory` GET/DELETE 接口
- 不修改 SSE 事件格式
- 新增环境变量 `CHAT_MEMORY_BACKEND`，默认 `postgres`

---

## 七、Feature Flag

```bash
CHAT_MEMORY_BACKEND=postgres   # 启用持久化
CHAT_MEMORY_BACKEND=memory     # 回滚到内存
```

---

## 八、测试用例（TDD Harness）

### 8.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_append_and_list | append 3 条消息后 list | 返回 3 条，顺序正确 |
| test_persistence_across_instances | 实例 A append，实例 B list | B 能读取 A 写入的数据 |
| test_clear | append 后 clear | list 返回空 |
| test_max_messages | append 250 条，max=200 | list 返回最新 200 条 |
| test_capability_field | append 带 capability | list 返回包含 capability |
| test_empty_list | 未写入直接 list | 返回空列表 |
| test_concurrent_appends | 并发 append 100 条 | 最终数量为 100，不丢数据 |
| test_fallback_to_memory | DATABASE_URL 无效 | 自动使用内存后端，服务不崩溃 |

### 8.2 集成测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_chat_stream_remembers_history | 先发送"我是美妆账号"，再问"帮我写文案" | 第二轮不询问账号类型 |
| test_memory_api_persistence | 调用 POST /chat/stream 后 GET /chat/memory | 能看到历史消息 |
| test_service_memory_isolation | 同一 conversation 不同 service | 消息互不干扰 |

### 8.3 接口回归测试

| 用例 | 预期 |
|------|------|
| test_debug_chat_stream_sse_format | SSE 事件类型和字段不变 |
| test_debug_chat_memory_response_format | GET /chat/memory 响应格式不变 |
| test_debug_chat_memory_delete_response_format | DELETE /chat/memory 响应格式不变 |

---

## 九、实现文件

| 文件 | 说明 |
|------|------|
| `apps/api/src/chat_debug/memory.py` | 保留内存实现 |
| 新增 `apps/api/src/chat_debug/memory_postgres.py` | PostgreSQL 实现 |
| `apps/api/src/chat_debug/router.py` | 无需改动 |
| `apps/api/src/services/memory_service.py` | 无需改动 |
| 新增 `tests/chat_debug/test_memory_postgres.py` | 单元测试 |
| 新增 `tests/integration/test_memory_persistence.py` | 集成测试 |

---

## 十、风险与回滚

| 风险 | 缓解 |
|------|------|
| PostgreSQL 性能瓶颈 | 加索引，应用层缓存最近 N 条 |
| 数据库不可用 | 自动降级到内存 |
| 数据迁移失败 | 阶段 0 不强制迁移旧内存数据 |
| Schema 冲突 | 使用 `IF NOT EXISTS` |

**回滚**：设置 `CHAT_MEMORY_BACKEND=memory` 即可。
