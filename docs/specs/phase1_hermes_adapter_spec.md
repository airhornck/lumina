# Phase 1 Hermes 引擎适配器 SPECIFICATION

> 文档版本：v1.0
> 日期：2026-07-04
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

将 Hermes Agent 作为可选执行引擎内嵌到 Lumina 中，接管 `/api/v1/debug/chat/stream` 的 `system_chat` 能力。Hermes 的输出必须转换为 Lumina 现有的 SSE 格式，前端无感知。

### 1.2 用户故事

> 作为用户，我希望 Lumina 在处理复杂营销任务时具备更强的自主规划和工具调用能力，同时保持现有的对话体验。

---

## 二、输入输出边界

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_message` | str | 是 | 用户当前输入 |
| `user_id` | str | 是 | 用户唯一标识 |
| `conversation_id` | str | 是 | 对话唯一标识 |
| `session_history` | List[Dict] | 是 | Lumina 格式的历史消息 |
| `platform` | str | 否 | 当前平台，默认 `xiaohongshu` |
| `context` | Dict[str, Any] | 否 | 额外上下文，如 hub_context |

### 2.2 输出

异步迭代器，产生 Lumina SSE v2 格式的事件字符串：

```python
# start
'data: {"type": "start", "service": "system-chat", "stream_format": 2, "request_id": "..."}\n\n'

# assistant_delta
'data: {"type": "assistant_delta", "text": "..."}\n\n'

# export_link（可选）
'data: {"type": "export_link", "format": "html", "url": "...", ...}\n\n'

# compliance_report（可选）
'data: {"type": "compliance_report", "risk_level": "...", ...}\n\n'

# done
'data: {"type": "done", "service": "system-chat", "request_id": "...", "full_length": 123, ...}\n\n'
```

### 2.3 边界条件

| 场景 | 预期行为 |
|------|----------|
| Hermes 未安装 | 启动时优雅降级，返回错误 SSE 事件 |
| Hermes 调用异常 | 捕获异常，返回 `error` SSE 事件，不崩溃 |
| Hermes 输出为空 | 返回最小化的 start + done |
| 流式输出中断 | 已发送的内容保持有效，最后发送 done |
| `LUMINA_USE_HERMES=false` | 不调用 Hermes，走原有路径 |

---

## 三、核心业务规则

### 3.1 适配器职责

`HermesEngineAdapter` 负责：
1. 管理 `AIAgent` 实例生命周期
2. 将 Lumina 输入转换为 Hermes 输入格式
3. 调用 Hermes `chat()` 或 `run_conversation()`
4. 将 Hermes 输出转换为 Lumina SSE 事件流
5. 处理异常和降级

### 3.2 Hermes 调用方式

使用同步阻塞调用 `agent.chat()`，因为 Lumina 的 SSE 生成器本身在异步上下文中运行，可以将 Hermes 调用放在线程池中：

```python
loop = asyncio.get_event_loop()
response = await loop.run_in_executor(None, agent.chat, user_message)
```

### 3.3 会话映射

- Lumina `conversation_id` 映射到 Hermes `session_id`
- Lumina `user_id` 映射到 Hermes 用户标识（如需要）
- 历史消息转换为 OpenAI message 格式后传入 `conversation_history`

### 3.4 人设注入

使用项目内 `data/hermes/personas/lumina-marketing.md` 作为 system prompt，告诉 Hermes：
- 它是 Lumina AI 营销助手
- 只回答营销相关问题
- 必须遵守 Lumina 的工具限制
- 输出风格要求

### 3.5 输出转换规则

| Hermes 输出 | Lumina SSE |
|-------------|------------|
| `final_response` 文本 | `assistant_delta` 分块 |
| 工具结果中的 `export_urls` | `export_link` 事件 |
| 工具结果中的 `compliance` | `compliance_report` 事件 |
| 无结构化输出 | 纯文本 `assistant_delta` |

---

## 四、错误处理

| 错误场景 | 处理策略 | 返回给用户 |
|----------|----------|------------|
| Hermes 未安装 | 记录 error，返回错误 SSE | "Hermes 引擎未安装" |
| Hermes 初始化失败 | 记录 error，返回错误 SSE | "引擎初始化失败" |
| Hermes 调用超时 | 记录 error，返回错误 SSE | "响应超时" |
| Hermes 调用异常 | 记录 error，返回错误 SSE | "引擎调用失败" |
| 输出转换异常 | 记录 error，返回错误 SSE | "输出转换失败" |

---

## 五、安全合规

| 要求 | 实现 |
|------|------|
| 危险工具禁用 | 通过 `disabled_toolsets` 禁用 terminal/browser/code_execution/delegation |
| 不暴露 Hermes 内部错误 | 用户-facing 错误只显示摘要 |
| 不泄露用户数据 | 日志中不打印用户消息内容 |

---

## 六、接口兼容性声明

- 不修改 `/api/v1/debug/chat/stream` 接口路径
- 不修改 SSE 事件类型
- 新增环境变量 `LUMINA_USE_HERMES`

---

## 七、Feature Flag

```bash
LUMINA_USE_HERMES=false   # 默认关闭，走原有路径
LUMINA_USE_HERMES=true    # 启用 Hermes 引擎
```

---

## 八、测试用例（TDD Harness）

### 8.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_hermes_to_sse_start | 调用 adapter | 第一个事件为 start |
| test_hermes_to_sse_delta | Hermes 返回 "你好" | 产生 assistant_delta "你好" |
| test_hermes_to_sse_done | 完整流程 | 最后一个事件为 done |
| test_hermes_disabled | Flag=false | 抛出 NotImplementedError 或返回空迭代器 |
| test_hermes_not_installed | 模拟 ImportError | 返回 error SSE 事件 |
| test_hermes_exception | 模拟 Hermes 异常 | 返回 error SSE 事件 |

### 8.2 接口回归测试

| 用例 | 预期 |
|------|------|
| test_debug_chat_stream_with_hermes | SSE 事件类型和字段不变 |

---

## 九、实现文件

| 文件 | 说明 |
|------|------|
| 新增 `apps/api/src/services/hermes_adapter.py` | Hermes 引擎适配器 |
| `apps/api/src/chat_debug/router.py` | 根据 Flag 选择引擎 |
| 新增 `tests/hermes/test_adapter.py` | 单元测试 |

---

## 十、风险与回滚

| 风险 | 缓解 |
|------|------|
| Hermes 依赖冲突 | 使用可选依赖组 `[hermes]` |
| Hermes 输出不稳定 | 保留原有路径作为 fallback |
| 响应延迟增加 | 线程池执行 + 超时控制 |

**回滚**：设置 `LUMINA_USE_HERMES=false` 即可。
