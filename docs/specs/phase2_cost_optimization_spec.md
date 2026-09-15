# Phase 2 LLM 成本优化 SPECIFICATION

> 文档版本：v1.0
> 日期：2026-07-07
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

在保持输出质量的前提下降低 LLM 调用成本：增加响应缓存、模型降级策略、Token 消耗监控、长历史摘要化。

### 1.2 用户故事

> 作为运营方，我希望 Lumina 不要对相同问题重复调用昂贵的 LLM，并能在对话历史变长时自动摘要，控制单次请求成本。

---

## 二、输入输出边界

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `messages` | List[Dict] | 是 | 当前请求消息列表 |
| `model` | str | 是 | 当前模型标识 |
| `user_id` | str | 否 | 用于成本归因 |
| `skill_name` | str | 否 | 用于成本归因 |

### 2.2 输出

- 流式/非流式 LLM 响应文本。
- 可选 `done.usage` 字段上报累计 token。
- 缓存命中时直接返回，不调用 LLM。

### 2.3 边界条件

| 场景 | 预期行为 |
|------|----------|
| 缓存命中 | 直接返回缓存结果，不上报新 token |
| 历史超长 | 自动摘要旧消息，保留最近 N 条 |
| 模型降级 | 按配置切换到 cheaper 模型 |
| 成本超限 | 告警（但不阻断服务） |

---

## 三、核心业务规则

### 3.1 响应缓存

- 缓存键：`hash(model + normalized_messages + temperature)`。
- 缓存值：完整响应文本。
- 默认 TTL：300 秒。
- 仅缓存非流式响应；流式响应可在完成后再写入缓存。
- 内存缓存实现，避免外部依赖。

### 3.2 模型降级策略

配置 `LUMINA_COST_FALLBACK_MODEL`：

```yaml
# infra/config/llm.yaml 示例
skill_config:
  debug_chat:
    provider: deepseek
    model: deepseek-chat
    fallback_model: deepseek-chat-lite   # 或本地模型
```

降级触发条件：
- 当前模型连续失败 2 次。
- 配置 `cost_optimization.fallback_on_high_tokens=true` 且 prompt 超过阈值。

### 3.3 Token 消耗监控

扩展现有 `llm_usage_logs` 表：

```sql
ALTER TABLE llm_usage_logs ADD COLUMN IF NOT EXISTS cost_estimate DECIMAL(12,6);
ALTER TABLE llm_usage_logs ADD COLUMN IF NOT EXISTS cached BOOLEAN DEFAULT false;
```

新增成本监控器 `CostMonitor`：
- 按 user_id / model / skill_name 统计 1 小时内 token 与估算成本。
- 超过阈值时记录 warning。

### 3.4 长历史摘要化

- 当 messages 总 token 超过阈值（默认 3000）时，对较早消息调用 LLM 生成摘要。
- 摘要替换原消息，保留最近 6 条完整消息。

---

## 四、Feature Flag

```bash
LUMINA_ENABLE_RESPONSE_CACHE=true
LUMINA_ENABLE_MODEL_FALLBACK=true
LUMINA_ENABLE_HISTORY_SUMMARY=true
LUMINA_ENABLE_COST_MONITOR=true
```

---

## 五、接口兼容性声明

- 不修改 `/api/v1/debug/chat/stream` 路径与 SSE 格式。
- `done.usage` 字段已在阶段 0/1 支持，本阶段补充缓存标记 `cached`。

---

## 六、测试用例（TDD Harness）

### 6.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_cache_hit | 相同消息第二次请求 | 返回缓存，不调用 LLM |
| test_cache_miss | 不同消息 | 调用 LLM 并写入缓存 |
| test_model_fallback | 主模型失败 2 次 | 使用 fallback 模型 |
| test_token_monitor | 模拟大用量 | cost_monitor 返回告警 |
| test_history_summary | 长历史 | 旧消息被摘要替换 |

---

## 七、实现文件

| 文件 | 说明 |
|------|------|
| 新增 `packages/llm-hub/src/llm_hub/cost_optimizer.py` | 缓存、降级、摘要、监控 |
| 修改 `packages/llm-hub/src/llm_hub/client.py` | 接入 cost optimizer |
| 修改 `infra/sql/init.sql` | llm_usage_logs 增加 cost_estimate / cached 字段 |
| 新增 `tests/phase2/test_cost_optimization.py` | 单元测试 |

---

## 八、风险与回滚

| 风险 | 缓解 |
|------|------|
| 缓存导致过时回复 | 短 TTL + 按消息 hash |
| 降级模型质量下降 | 仅在高 token 或失败时降级 |
| 摘要丢失细节 | 保留最近完整消息 |

**回滚**：关闭对应 Feature Flag。
