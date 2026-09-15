# Phase 1 Lumina Skill 注册为 Hermes 工具 SPECIFICATION

> 文档版本：v1.0
> 日期：2026-07-04
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

将 Lumina 现有的 Skill（内容生成、账号诊断、数据分析等）包装为 Hermes 可调用的工具，让 Hermes Agent 在自主规划时能够调用 Lumina 的专业能力。

### 1.2 用户故事

> 作为用户，我希望 Hermes 在规划营销任务时，能够调用 Lumina 已有的专业 Skill，而不是重新实现。

---

## 二、输入输出边界

### 2.1 输入

Hermes 调用工具时传入：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tool_name` | str | 是 | Hermes 调用的工具名，如 `lumina_generate_content` |
| `args` | Dict[str, Any] | 是 | 工具参数 |

### 2.2 输出

每个工具返回 JSON 字符串：

```json
{
  "ok": true,
  "result": { ... },
  "error": null
}
```

### 2.3 边界条件

| 场景 | 预期行为 |
|------|----------|
| Skill 不存在 | 返回错误 JSON |
| Skill 调用异常 | 捕获异常，返回错误 JSON |
| 参数缺失 | 返回参数校验错误 |
| 异步 Skill | 在事件循环中 await |

---

## 三、核心业务规则

### 3.1 工具集定义

注册一个 `lumina_marketing` 工具集，包含以下工具：

| 工具名 | 对应 Skill | 用途 |
|--------|-----------|------|
| `lumina_generate_content` | content_engine | 生成文案/笔记 |
| `lumina_diagnose_account` | diagnosis | 账号诊断 |
| `lumina_analyze_traffic` | analyze_traffic | 流量分析 |
| `lumina_detect_risk` | detect_risk | 合规检测 |
| `lumina_recommend_topics` | topic | 选题推荐 |

### 3.2 工具注册方式

由于 Hermes 的工具注册在 import 时完成，Lumina 需要：
1. 在适配器初始化时 import `hermes_tools` 模块
2. 模块内部调用 `registry.register()`
3. Hermes 初始化时通过 `enabled_toolsets=["lumina_marketing"]` 启用

### 3.3 工具 Schema 格式

OpenAI function-calling 格式：

```json
{
  "type": "function",
  "function": {
    "name": "lumina_generate_content",
    "description": "生成小红书/抖音等平台适配的营销文案",
    "parameters": {
      "type": "object",
      "properties": {
        "topic": {"type": "string"},
        "platform": {"type": "string", "enum": ["xiaohongshu", "douyin", "bilibili"]},
        "style": {"type": "string"},
        "target_audience": {"type": "string"}
      },
      "required": ["topic", "platform"]
    }
  }
}
```

### 3.4 Skill 调用封装

```python
async def handle_lumina_generate_content(args: Dict[str, Any]) -> str:
    from services.content_engine.cross_platform_engine import CrossPlatformEngine
    engine = CrossPlatformEngine()
    result = await engine.generate_sync(...)
    return json.dumps({"ok": True, "result": result.__dict__})
```

### 3.5 错误处理

所有工具必须捕获异常，返回：

```json
{"ok": false, "error": "错误摘要"}
```

---

## 四、安全合规

| 要求 | 实现 |
|------|------|
| 只注册只读/安全工具 | 不注册 RPA 登录、文件写入等敏感操作 |
| 参数校验 | 使用 Pydantic 模型校验 |
| 不暴露内部错误 | 返回摘要，记录详细日志 |

---

## 五、接口兼容性声明

- 不修改现有 `/skill/*` 接口
- Hermes 工具名为新增，不影响前端

---

## 六、测试用例（TDD Harness）

### 6.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_tool_registration | - | `lumina_generate_content` 在 registry 中 |
| test_generate_content_schema | - | schema 包含 topic/platform |
| test_generate_content_mock | mock CrossPlatformEngine | 返回 ok=true |
| test_tool_not_found | 调用不存在工具 | 返回 ok=false |
| test_tool_exception | 模拟 Skill 异常 | 返回 ok=false |

---

## 七、实现文件

| 文件 | 说明 |
|------|------|
| 新增 `apps/api/src/services/hermes_tools.py` | Lumina Skill 包装为 Hermes 工具 |
| `skills/*` | 现有 Skill 实现 |
| 新增 `tests/hermes/test_tool_registration.py` | 单元测试 |

---

## 八、风险与回滚

| 风险 | 缓解 |
|------|------|
| Hermes 工具注册冲突 | 使用 `lumina_` 前缀 |
| Skill 调用超时 | 设置超时控制 |
| 循环调用 | Hermes `max_iterations` 限制 |

**回滚**：设置 `LUMINA_USE_HERMES=false` 即可。
