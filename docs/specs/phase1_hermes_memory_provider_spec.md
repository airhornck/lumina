# Phase 1 Hermes 记忆提供器 SPECIFICATION

> 文档版本：v1.0
> 日期：2026-07-04
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` 5.2 P0-1 对话记忆
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

让 Hermes Agent 使用 Lumina 现有的 PostgreSQL 记忆层，确保：
1. Hermes 能读取 Lumina 的对话历史
2. Hermes 产生的新回复能写回 Lumina 记忆
3. 用户通过 Lumina 前端看到的记忆与 Hermes 内部一致

### 1.2 用户故事

> 作为用户，我希望无论 Lumina 使用原有引擎还是 Hermes 引擎，对话记忆都是一致的。

---

## 二、输入输出边界

### 2.1 输入

记忆提供器接收 Hermes 内部调用：

| 方法 | 输入 | 说明 |
|------|------|------|
| `initialize(session_id, **kwargs)` | session_id, user_id, conversation_id | 初始化会话 |
| `sync_turn(user_content, assistant_content, session_id, messages)` | 用户/助手消息 | 每轮对话同步 |
| `handle_tool_call(tool_name, args, **kwargs)` | tool_name, args | Hermes 调用记忆工具 |

### 2.2 输出

| 方法 | 输出 |
|------|------|
| `get_tool_schemas()` | OpenAI function schemas 列表 |
| `handle_tool_call()` | JSON 字符串 |
| `sync_turn()` | None |

### 2.3 边界条件

| 场景 | 预期行为 |
|------|----------|
| Lumina 记忆为空 | 返回空结果 |
| session_id 无法解析 | 返回错误提示 |
| 数据库不可用 | 降级到内存，不阻断 Hermes |
| 历史消息超长 | 截断到最近 N 条 |

---

## 三、核心业务规则

### 3.1 提供器职责

`LuminaMemoryProvider` 实现 Hermes 的 `MemoryProvider` 抽象：
1. 通过 Lumina 的 `ChatMemoryStore` 读写记忆
2. 向 Hermes 暴露记忆查询工具
3. 在 `sync_turn` 中将新消息写回 Lumina

### 3.2 工具暴露

向 Hermes 注册一个工具：

```json
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
          "description": "搜索关键词"
        }
      },
      "required": ["query"]
    }
  }
}
```

### 3.3 记忆同步

每次 Hermes 完成一轮对话后，调用 `sync_turn`：
1. 将用户消息写入 Lumina 记忆（user 角色）
2. 将助手回复写入 Lumina 记忆（assistant 角色）
3. 携带 capability="system_chat"

### 3.4 与 Lumina ChatMemoryStore 集成

```python
from chat_debug.memory import get_memory_store

self._store = get_memory_store()
```

### 3.5 session_id 解析

Hermes 的 `session_id` 直接使用 Lumina 的 `conversation_id`。

---

## 四、错误处理

| 错误场景 | 处理策略 |
|----------|----------|
| ChatMemoryStore 不可用 | 降级到空实现 |
| 写入失败 | 记录 warning，不阻断 Hermes |
| 查询失败 | 返回空结果 JSON |

---

## 五、安全合规

| 要求 | 实现 |
|------|------|
| 用户隔离 | 所有查询必须带 user_id |
| 不越权访问 | 只查询当前 conversation_id 的记忆 |
| 不泄露隐私 | 工具结果中不暴露其他用户数据 |

---

## 六、接口兼容性声明

- 不修改 Lumina `/api/v1/debug/chat/memory` 接口
- 不修改 Hermes 的 MemoryProvider 接口契约
- Hermes 记忆工具名称 `lumina_search_memory` 为新增

---

## 七、测试用例（TDD Harness）

### 7.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_provider_name | - | name == "lumina" |
| test_tool_schemas | - | 返回 lumina_search_memory schema |
| test_handle_search_memory | 历史有"夏季防晒"，query"防晒" | 返回包含该记录的 JSON |
| test_sync_turn_writes_memory | user="你好"，assistant="有什么可以帮你" | Lumina 记忆中有两条 |
| test_session_isolation | 不同 session_id | 互不干扰 |

---

## 八、实现文件

| 文件 | 说明 |
|------|------|
| 新增 `apps/api/src/services/hermes_memory_provider.py` | Lumina 记忆提供器 |
| `apps/api/src/chat_debug/memory.py` | 提供 `get_memory_store()` |
| 新增 `tests/hermes/test_memory_provider.py` | 单元测试 |

---

## 九、风险与回滚

| 风险 | 缓解 |
|------|------|
| Hermes 不调用 sync_turn | 在适配器中手动同步 |
| 记忆格式不兼容 | 统一使用 Lumina 格式 |
| 循环写入 | 只在 sync_turn 中写入，避免 adapter 重复写入 |

**回滚**：设置 `LUMINA_USE_HERMES=false` 即可。
