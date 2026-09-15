# Phase 1 Hermes 安全加固 SPECIFICATION

> 文档版本：v1.0
> 日期：2026-07-04
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

Hermes Agent 默认包含大量危险工具（terminal、browser、code execution 等）。在 Lumina 场景中，用户是个人创作者/KOL，只需要营销助手能力。必须严格限制 Hermes 的工具集，防止任意代码执行、文件修改、浏览器自动化等风险。

### 1.2 用户故事

> 作为平台运营方，我希望 Hermes 在 Lumina 中只能调用安全的营销工具，不能执行任意代码或访问用户系统。

---

## 二、输入输出边界

### 2.1 输入

安全策略在 Hermes 初始化时配置：

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `enabled_toolsets` | List[str] | 白名单工具集 |
| `disabled_toolsets` | List[str] | 黑名单工具集 |
| `max_iterations` | int | 最大工具调用轮数 |
| `approvals.mode` | str | manual / smart / off |

### 2.2 输出

配置后的 Hermes 实例：
- 只暴露允许的工具
- 调用危险工具时被阻止
- 用户请求涉及危险操作时被拒绝

---

## 三、核心业务规则

### 3.1 默认禁用工具集

```python
DISABLED_HERMES_TOOLSETS = [
    "terminal",
    "browser",
    "code_execution",
    "delegation",
    "computer_use",
    "messaging",
    "cronjob",
    "homeassistant",
    "discord",
    "discord_admin",
]
```

### 3.2 默认启用工具集

```python
ENABLED_HERMES_TOOLSETS = [
    "lumina_marketing",  # Lumina 自定义工具集
    "web",               # 如需联网搜索
    "clarify",           # 澄清问题
]
```

### 3.3 最大迭代次数

限制 Hermes 工具调用轮数，防止无限循环：

```python
max_iterations = 10
```

### 3.4 审批模式

```python
# 通过 config.yaml 或 AIAgent 参数
approvals_mode = "manual"  # 危险操作需要确认
```

### 3.5 运行时安全断言

在创建 Hermes 实例前，强制检查：

```python
assert "terminal" not in enabled_toolsets
assert "browser" not in enabled_toolsets
assert "code_execution" not in enabled_toolsets
```

---

## 四、错误处理

| 错误场景 | 处理策略 |
|----------|----------|
| Hermes 仍暴露危险工具 | 启动失败，记录 critical 日志 |
| 用户请求触发危险工具 | Hermes 拒绝执行，返回安全提示 |
| 工具集配置被篡改 | 初始化时强制校验 |

---

## 五、安全合规

| 要求 | 实现 |
|------|------|
| 最小权限原则 | 只启用 lumina_marketing + 必要工具 |
| 零代码执行 | 禁用 terminal/code_execution |
| 零浏览器自动化 | 禁用 browser |
| 零子代理 | 禁用 delegation |
| 可审计 | 记录 Hermes 所有工具调用 |

---

## 六、测试用例（TDD Harness）

### 6.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_disabled_tools | 初始化后 | terminal/browser/code_execution 不在 tools 中 |
| test_enabled_lumina_tools | 初始化后 | lumina_* 工具在 tools 中 |
| test_max_iterations_set | - | AIAgent.max_iterations <= 10 |
| test_dangerous_tool_blocked | 模拟调用 terminal | 被拒绝或不存在 |

---

## 七、实现文件

| 文件 | 说明 |
|------|------|
| 新增 `apps/api/src/services/hermes_security.py` | 安全策略与校验 |
| 新增 `apps/api/src/services/hermes_adapter.py` | 使用安全策略初始化 Hermes |
| 新增 `data/hermes/config.yaml` | Hermes 配置文件 |
| 新增 `tests/hermes/test_security.py` | 安全测试 |

---

## 八、风险与回滚

| 风险 | 缓解 |
|------|------|
| Hermes 版本更新引入新危险工具 | 白名单策略，新工具默认不启用 |
| 配置被覆盖 | 运行时强制校验 |
| 用户绕过限制 | 通过 prompt 注入防御 + 工具白名单 |

**回滚**：设置 `LUMINA_USE_HERMES=false` 即可。
