# Lumina 核心架构文档

> **版本**: v1.0  
> **日期**: 2026-04-21  
> **目的**: 明确项目中最稳定的核心层，指导后续需求在**不触碰核心架构**的前提下正确扩展  
> **原则**: 核心层只修 bug，不承载业务变化；所有业务变化通过"扩展点"吸收

---

## 1. 核心架构全景

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              上层应用 / 业务扩展层                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │新增 demo │  │新增跨平台│  │新增内容诊断 │  │ 新增 Skill / Agent       │ │
│  │router    │  │内容生成  │  │服务流       │  │                          │ │
│  │(REST)    │  │(SSE)     │  │(SSE)        │  │                          │ │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  └────────────┬─────────────┘ │
│       │             │               │                       │               │
│       ▼             ▼               ▼                       ▼               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         核心架构层（本文档保护范围）                    │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │   │
│  │  │ API 接入层    │  │ 服务流层      │  │ 编排层                   │   │   │
│  │  │ · main.py    │  │ · router.py  │  │ · router.py              │   │   │
│  │  │ · models.py  │  │ · memory     │  │ · MarketingOrchestra     │   │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘   │   │
│  │         │                 │                     │                   │   │
│  │  ┌──────┴─────────────────┴─────────────────────┴───────────────┐   │   │
│  │  │                    基础设施层                                    │   │   │
│  │  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐ │   │   │
│  │  │  │ llm-hub  │  │knowledge-base│  │ skill-hub-client/app     │ │   │   │
│  │  │  └──────────┘  └──────────────┘  └──────────────────────────┘ │   │   │
│  │  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐ │   │   │
│  │  │  │sop-engine│  │lumina-skills │  │ intent 引擎              │ │   │   │
│  │  │  └──────────┘  └──────────────┘  └──────────────────────────┘ │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │         │                 │                     │                   │   │
│  │  ┌──────┴─────────────────┴─────────────────────┴───────────────┐   │   │
│  │  │                    数据与配置层                                  │   │   │
│  │  │  · config/agents.yaml    · config/intent_rules.yaml            │   │   │
│  │  │  · config/llm.yaml       · data/platforms/*.yml               │   │   │
│  │  │  · data/methodologies/*.yml  · data/sessions/                 │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **上图规则**：所有新增需求应该发生在"上层应用 / 业务扩展层"，通过核心层暴露的"扩展点"接入，**不应侵入核心层内部逻辑**。

---

## 2. API 接入层（进程装配层）

### 2.1 `apps/api/src/api/main.py` — 统一 FastAPI 入口

**核心职责**
- 进程级初始化（LLM Hub `lifespan`）
- 路由/子应用装配（`include_router` / `mount`）
- 基础设施中间件（CORS、静态文件、健康探针）

**为什么它是稳定核心**
- 文件中**没有任何业务逻辑**
- `intent_router`、`skill_router` 的挂载被包在 `try/except` 中，局部失败不拖垮进程
- 所有已有 router 的挂载方式完全一致，新增 router 只需复制现有模式

**不变量**
- 不做 if/else 业务判断
- 不在 lifespan 中增加业务初始化（只初始化 LLM Hub）
- CORS 和静态文件配置保持现状

**正确扩展方式**
```python
# ✅ 正确：新增 router 并 include
from api.demo_router import router as demo_router
app.include_router(demo_router)

# ❌ 错误：在 main.py 中插入业务判断、新增 Pydantic 模型、改变 lifespan
```

### 2.2 `apps/api/src/services/models.py` — `ServiceStreamRequest` 请求契约

**核心职责**
- 定义 SSE 服务流层的统一请求模型
- 通过 `context: Dict[str, Any]` 提供业务扩展沙盒

**当前字段**
```python
class ServiceStreamRequest(BaseModel):
    user_id: str              # 用户唯一标识
    conversation_id: str      # 对话唯一标识
    message: str              # 用户当前输入
    platform: Optional[str]   # 可选平台上下文
    context: Dict[str, Any]   # 业务上下文扩展沙盒
    mode: Optional[str]       # 子模式（唯一例外，仅 positioning 使用）
```

**为什么它是稳定核心**
- 所有 service handler 的函数签名都基于这个模型展开
- `user_id` + `conversation_id` + `service` 三元组是记忆隔离的根基
- 它是服务流层的"最小公倍数"设计

**正确扩展方式**
```python
# ✅ 正确：通过 context 传递业务专属数据
{
  "message": "分析我的流量",
  "context": {
    "metrics": {"views": 12000, "likes": 480},
    "competitor_id": "demo_001"
  }
}

# ❌ 错误：修改 ServiceStreamRequest 增加字段
class ServiceStreamRequest(BaseModel):
    ...
    competitor_id: Optional[str] = None   # 仅个别服务需要
```

> **黄金法则**：只有当某个参数被绝大多数服务都需要时，才考虑提升到模型一级字段（如 `platform`）。否则永远走 `context`。

---

## 3. 服务流层（插件注册模式）

### 3.1 `apps/api/src/services/router.py` — 服务流路由分发

**核心职责**
- 白名单准入控制（`ALLOWED_SERVICES`）
- 统一入口分发（`POST /{service}/stream`）
- 横切记忆管理（`GET / DELETE /{service}/memory`）

**当前设计**
```python
ALLOWED_SERVICES = frozenset({
    "system-chat", "content-ranking", "positioning", "weekly-snapshot"
})

@router.post("/{service}/stream")
async def service_stream(service: str, body: ServiceStreamRequest) -> StreamingResponse:
    if service not in ALLOWED_SERVICES:
        raise HTTPException(...)
    # if/elif 分发到对应 handler
```

**为什么它是稳定核心**
- 强约束的插件注册模式：白名单 + 统一 handler 签名
- 记忆管理完全独立于业务 handler，是基础设施级横切关注点
- 修改分发逻辑会影响所有已有服务

**正确扩展方式**
```python
# Step 1: 在 handlers/ 下新建 my_service.py
async def handle_my_service_stream(user_id, conversation_id, message,
                                    platform, context, store):
    ...

# Step 2: 在 router.py 中导入并注册
from services.handlers.my_service import handle_my_service_stream
ALLOWED_SERVICES = frozenset({..., "my-service"})

# Step 3: 在 if/elif 链中增加分支
elif service == "my-service":
    gen = handle_my_service_stream(...)

# ❌ 错误：修改 ServiceStreamRequest、改变 URL 模式、在 router 层引入鉴权
```

### 3.2 `apps/api/src/services/memory_service.py` — 会话记忆隔离

**核心职责**
- 在底层 `ChatMemoryStore` 之上增加 `service` 命名空间隔离
- 提供 `append` / `list_messages` / `clear` 三个原子操作
- 隔离键格式：`{conversation_id}::{service}`

**对外接口**
```python
get_service_memory_store() -> ServiceMemoryStore
ServiceMemoryStore.append(user_id, conversation_id, service, role, content)
ServiceMemoryStore.list_messages(user_id, conversation_id, service)
ServiceMemoryStore.clear(user_id, conversation_id, service)
```

**为什么它是稳定核心**
- 全服务路由（4 个现有服务流 + 未来新增服务）全部通过它读写记忆
- 键格式 `{conversation_id}::{service}` 一旦改变，历史会话全部失效

**正确扩展方式**
```python
# ✅ 正确：注入新的后端实现
class RedisMemoryStore:
    async def append(self, user_id, conversation_id, service, role, content): ...
    async def list_messages(self, user_id, conversation_id, service): ...
    async def clear(self, user_id, conversation_id, service): ...

store = ServiceMemoryStore(backend=RedisMemoryStore())

# ❌ 错误：修改 ChatMemoryStore 的内部 dict 结构、改 ServiceMemoryStore 方法签名
```

---

## 4. 编排层（单入口契约）

### 4.1 `apps/orchestra/src/orchestra/router.py` — 编排 HTTP 适配

**核心职责**
- 只有一个 POST `/hub` 端点
- 将 HTTP body 解包后全部交给 `MarketingOrchestra.process()`
- 不做任何业务判断

**请求模型**
```python
class MarketingHubBody(BaseModel):
    user_input: str
    user_id: str = "anonymous"
    session_history: List[Dict[str, Any]] = []
    platform: Optional[str] = None
    context: Dict[str, Any] = {}
```

**为什么它是稳定核心**
- 这是整个系统的"单入口契约"
- router 只依赖 `MarketingOrchestra` 的接口，不依赖其内部实现
- `context` 设计吸收了所有业务变体

**正确扩展方式**
```python
# ✅ 正确：通过 context 传递新参数
{
  "user_input": "分析竞品",
  "context": {
    "competitor_id": "xxx",
    "metrics": {"views": 12000}
  }
}

# ❌ 错误：修改 MarketingHubBody 字段、新增 /hub-v2 端点
```

### 4.2 `apps/orchestra/src/orchestra/core.py` — `MarketingOrchestra`

**核心职责**
- 意图分类（`_classify_intent`）
- 矩阵意图解析（`_resolve_matrix_intent`）
- SOP DAG 执行（`run_sop`）
- 动态执行入口（`run_dynamic`）

**为什么它是稳定核心**
- 所有上层请求（无论是 `/hub` 还是内部调用）最终都汇聚到 `process()`
- 意图到 Agent 的映射、Agent 到 Skill 的调用链是系统的"中枢神经系统"
- `_MATRIX_SKILLS` 的动态导入机制提供了扩展点

**正确扩展方式**
```python
# ✅ 正确：新增意图正则 → 在 orchestra/core.py 的 _classify_intent 中增加分支
# ✅ 正确：新增矩阵意图 → 在 _resolve_matrix_intent 中增加正则匹配
# ✅ 正确：新增 SOP → 在 data/methodologies/ 新增 YAML，通过 compile_methodology_dag 自动编译

# ❌ 错误：修改 process() 的返回结构、删除 _classify_intent 中的现有分支
```

---

## 5. 基础设施层（公共地基）

### 5.1 `packages/llm-hub/` — LLM 统一调度中枢

**核心职责**
- 多提供商客户端池管理（OpenAI / Anthropic / DeepSeek / Qwen）
- 分级路由策略（`cost_aware` / `quality_first` / `latency_first` / `round_robin`）
- 流式与非流式统一调用
- 环境变量展开（`${VAR:-default}`）

**对外接口**
```python
init_default_hub(config_path: str) -> LLMHub
get_hub() -> Optional[LLMHub]
get_client(skill_name=None, component=None, llm_name=None) -> Optional[LLMClient]

LLMClient.complete(prompt, response_format=..., temperature=..., ...)
LLMClient.stream_completion(messages, ...)
```

**为什么它是稳定核心**
- `main.py` lifespan 中初始化；健康检查直接依赖 `get_hub()`
- 所有 Skill 调用 LLM 的唯一通道（通过 `lumina_skills.llm_utils.call_llm()` 底层都走 `get_client()`）
- 一旦修改返回结构或初始化方式，全系统崩溃

**正确扩展方式**
```python
# ✅ 正确：新增模型 → 修改 client.py 中 litellm_model_id() 映射（纯新增）
# ✅ 正确：调整配置 → 编辑 config/llm.yaml 的 llm_pool / skill_config
# ✅ 正确：新路由策略 → 在 llm.yaml 的 strategies 中定义

# ❌ 错误：重写 LLMClient 类、硬编码到 hub.py、删除现有字段
```

### 5.2 `packages/knowledge-base/` — 双库体系

**核心职责**
- **PlatformRegistry**：从 `data/platforms/*.yml` 热加载平台规范（content_dna / audit_rules / content_formats）
- **MethodologyRegistry**：从 `data/methodologies/*.yml` 热加载方法论（steps / prompt_templates / case_studies）

**对外接口**
```python
PlatformRegistry.load(platform_id: str) -> PlatformSpec   # 永不崩溃
PlatformRegistry.reload(platform_id=None)

MethodologyRegistry.load(methodology_id: str) -> Methodology
MethodologyRegistry.find_best_match(query, industry, goal) -> Optional[Methodology]
MethodologyRegistry.list_ids() -> List[str]
```

**为什么它是稳定核心**
- SOP 引擎直接依赖两者编译 DAG
- `skill-content-strategist`、`skill-creative-studio`、`skill-compliance-officer` 全部读取这些字段
- `PlatformSpec` / `Methodology` 的字段名是事实契约

**正确扩展方式**
```python
# ✅ 正确：新增平台 → data/platforms/weibo_v2024.yml
# ✅ 正确：新增方法论 → data/methodologies/my_method.yml
# ✅ 正确：自定义匹配 → 子类化 MethodologyRegistry 重写 find_best_match()

# ❌ 错误：修改 PlatformRegistry.load() 逻辑、删除现有字段、改已有 YAML 结构
```

### 5.3 `packages/skill-hub-client/` + `apps/skill-hub/` — Skill 注册与调用

**核心职责**
- **SkillHubClient**：同进程直连，通过名称调用 `TOOL_REGISTRY` 中的函数
- **MCP Server**：基于 FastMCP 将 `TOOL_REGISTRY` 暴露为 MCP 工具
- 统一返回契约：`{"ok": bool, "result": ...}` 或 `{"ok": False, "error": ...}`

**对外接口**
```python
SkillHubClient.call(skill_name: str, params: dict) -> dict
build_skill_hub_mcp() -> FastMCP

TOOL_REGISTRY: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]]
register_all_tools(mcp)
```

**为什么它是稳定核心**
- `orchestra/core.py` 通过 `SkillHubClient.call()` 执行所有 Skill
- SOP 执行依赖 `.call()` 的统一返回结构统计 `ok_count` / `fail_count`
- `main.py` 将 `build_skill_hub_mcp()` 挂载到 `/mcp`
- `TOOL_REGISTRY` 键名是 API，改名会导致 Orchestra 和 MCP Server 同时失效

**正确扩展方式**
```python
# ✅ 正确：新增 Skill → 实现函数 → 在 TOOL_REGISTRY 中注册
# ✅ 正确：替换传输层 → 子类化 SkillHubClient 注入自定义 registry

# ❌ 错误：修改 SkillHubClient.call() 签名、改 {"ok": bool} 返回格式、删现有键
```

### 5.4 `packages/lumina-skills/` — Skill 开发基础设施

#### `llm_utils.py` — LLM 调用抽象

| 函数 | 职责 |
|------|------|
| `call_llm()` | 统一非流式，内部 fallback：`llm_hub` → `litellm direct` → `fallback_response` |
| `stream_llm()` | 统一流式，同样走 fallback 链 |
| `build_prompt()` | 模板渲染，缺失变量自动填充 `[missing_key]` |

**正确扩展方式**：新增 prompt 模板，不绕过 `call_llm` 的 fallback 链。

#### `methodology_utils.py` — 方法论库工具

| 函数 | 职责 |
|------|------|
| `resolve_methodology()` | 根据 query/industry/goal 匹配最佳方法论（registry 可注入） |
| `build_methodology_prompt()` | 将方法论渲染为可注入 LLM prompt 的文本 |
| `match_methodology_for_content()` | 基于关键词规则快速匹配 |

**正确扩展方式**：新增匹配规则，不绕过 `resolve_methodology`。

#### `registry.py` — MCP 工具注册表

```python
TOOL_REGISTRY = {
    "diagnose_account": diagnose_account,
    "generate_text": generate_text,
    ...
}
```

**正确扩展方式**：新增键值对，不绕过注册表直接操作 MCP 实例。

### 5.5 `packages/sop-engine/` — SOP 编排编译器

**核心职责**
- 将 `Methodology` 的 `steps` 和 `PlatformSpec` 编译为可执行的 DAG 节点列表
- 自动注入 `methodology_id`、`methodology_prompt_templates` 到每个节点的 `params`

**对外接口**
```python
compile_methodology_dag(
    methodology_id: str,
    platform_id: str,
    methodology_lib: MethodologyRegistry | None = None,
    platform_lib: PlatformRegistry | None = None,
) -> List[Dict[str, Any]]
# 返回节点结构：
# [{"id": "...", "agent_role": "...", "skill": "...", "params": {...}, ...}]
```

**为什么它是稳定核心**
- `orchestra/core.py` 的 `run_sop()` 是唯一直接消费者
- 节点 Schema（`id` / `agent_role` / `skill` / `params` / `theory`）是契约
- Skill 参数来源（`methodology_prompt_template`）通过这里注入

**正确扩展方式**
```python
# ✅ 正确：新增方法论 → data/methodologies/ 新增 YAML（零代码变更）
# ✅ 正确：条件分支 DAG → 新建 compile_conditional_dag() 函数，保持原函数不变
# ✅ 正确：自定义注册表 → 调用时传入 methodology_lib=MyRegistry()

# ❌ 错误：修改 compile_methodology_dag 返回结构、删除现有键
```

---

## 6. 数据与配置层（驱动体系）

### 6.1 `config/` — YAML 配置驱动

| 文件 | 职责 | 消费者 |
|------|------|--------|
| `llm.yaml` | LLM 池、Skill/Component 分配、策略优先级、Fallback 顺序 | `llm_hub.hub.LLMHub.from_config_file()` |
| `intent_rules.yaml` | L1 规则引擎的纯数据配置（正则规则、动态阈值、意图切换检测） | `apps/intent/src/intent/l1_rules.py` |
| `agents.yaml` | Agent 集群拓扑（单账号/矩阵/通用工具）、Skill 绑定、触发词、编排规则 | 设计契约（当前 orchestra 部分硬编码，但 YAML 是权威来源） |

**为什么它是稳定核心**
- `main.py` lifespan 加载 `llm.yaml`，失败则 Skill 层无 LLM
- `intent_rules.yaml` 是 L1 规则引擎的数据源，修改结构会直接破坏 `L1RuleEngine`
- `agents.yaml` 是"哪个 Agent 处理什么意图"的唯一来源

**正确扩展方式**
```python
# ✅ 正确：新增 Agent → agents.yaml 对应组新增条目
# ✅ 正确：新增意图正则 → intent_rules.yaml 对应类别新增正则行
# ✅ 正确：调整 LLM 分配 → llm.yaml 的 skill_config / component_config 修改
# ✅ 正确：新增策略 → llm.yaml 的 strategies 下定义

# ❌ 错误：在 orchestra/core.py 中硬编码新 Agent 路由、直接改 L1RuleEngine 源码
```

### 6.2 `data/` — 数据资产层

| 目录 | 内容 | Schema 契约 |
|------|------|-------------|
| `platforms/` | 平台规范 YAML | `platform_id` / `content_dna` / `audit_rules` / `content_formats` |
| `methodologies/` | 方法论 YAML | `methodology_id` / `name` / `steps` / `prompt_templates` |
| `sessions/` | 运行时会话状态 JSON | 由 `ChatMemoryStore` 写入代码定义 |
| `credentials/` | 凭证与密钥 | 由账号管理模块定义 |

**为什么它是稳定核心**
- Schema 即契约：`PlatformSpec` / `Methodology` 的 `from_config()` 期望特定字段名
- `skill-creative-studio`、`skill-compliance-officer`、`sop-engine` 都直接读取
- `sessions/` 的结构是持久化契约

**正确扩展方式**
```python
# ✅ 正确：新增平台 → data/platforms/{platform}_v2024.yml
# ✅ 正确：新增方法论 → data/methodologies/{name}.yml
# ✅ 正确：新增数据资产目录 → 新建子目录并配套新建 Registry 类

# ❌ 错误：修改现有平台的 content_formats 结构、删除/重命名现有方法论文件
```

---

## 7. 扩展指南速查表

### 7.1 按需求类型选择扩展路径

| 需求场景 | 正确扩展路径 | 不应触碰的核心 |
|---------|------------|-------------|
| **新增一个 REST 接口**（如 demo 榜单/矩阵） | 新建 `apps/api/src/api/xxx_router.py` → `main.py` include_router | `main.py` 的核心逻辑、`services/router.py` |
| **新增一个 SSE 服务流**（如跨平台内容生成） | 新建 `services/handlers/xxx.py` → `services/router.py` 注册到 `ALLOWED_SERVICES` | `ServiceStreamRequest` 字段、`services/router.py` 的分发逻辑 |
| **新增一个 Skill 能力**（如图片分析） | 在 `packages/lumina-skills/` 实现函数 → `registry.py` 注册 → 可能被 `orchestra` 调用 | `SkillHubClient.call()` 签名、`TOOL_REGISTRY` 契约格式、绕过 `call_llm()` |
| **新增一个内容方法论** | 新建 `data/methodologies/xxx.yml`（零代码变更） | `MethodologyRegistry` 核心逻辑、`sop-engine/compiler.py` |
| **新增一个平台规范** | 新建 `data/platforms/xxx.yml`（零代码变更） | `PlatformRegistry.load()` 逻辑、`PlatformSpec` 模型删除字段 |
| **新增一个 LLM 模型** | 修改 `config/llm.yaml` 的 `llm_pool` / `skill_config` | `LLMClient` 类、`hub.py` 的 `_resolve_config()` |
| **新增一个 Agent** | 修改 `config/agents.yaml` 定义拓扑 | `orchestra/core.py` 的硬编码路由（应尽量迁移到配置） |
| **新增一个意图分类规则** | 修改 `config/intent_rules.yaml` 新增正则 | `L1RuleEngine` 的解析逻辑、`_classify_intent` 的正则删除 |
| **替换记忆存储后端** | 实现相同接口的新 backend 类，注入 `ServiceMemoryStore` | `ServiceMemoryStore` 方法签名、`ChatMemoryStore` 的 dict 结构 |
| **新增多轮对话上下文** | 使用现有 `ServiceMemoryStore.append/list_messages` | 记忆隔离键格式 `{conversation_id}::{service}` |

### 7.2 核心层修改红线

以下修改必须走**架构评审**，不允许随意变更：

| 红线项 | 影响范围 | 后果 |
|--------|---------|------|
| 修改 `ServiceStreamRequest` 的必填字段 | 所有 service handler | 全服务流接口契约破坏 |
| 修改 `TOOL_REGISTRY` 键名或删除现有键 | Orchestra + MCP Server + SkillHubClient | Skill 调用链断裂 |
| 修改 `SkillHubClient.call()` 返回结构 | Orchestra `run_sop()` | SOP 执行统计失效 |
| 修改 `compile_methodology_dag()` 返回的节点 Schema | Orchestra `run_sop()` | DAG 执行异常 |
| 修改 `PlatformSpec` / `Methodology` 模型删除字段 | 所有读取 platform/methodology 的 Skill | Skill 运行时异常 |
| 修改记忆隔离键格式 | 所有服务的多轮对话 | 历史会话全部失效 |
| 在 `main.py` lifespan 中增加业务初始化 | 进程启动逻辑 | 启动变慢、失败风险增加 |
| 修改 `orchestra/router.py` `/hub` 返回结构 | OpenClaw 等外部调用方 | 外部集成断裂 |

---

## 8. 黄金法则

1. **配置 > 代码**
   > 优先通过 `config/` 和 `data/` 的 YAML 文件满足新需求。能写 YAML 解决的不写 Python。

2. **注册 > 修改**
   > 新增 Skill 时在 `registry.py` 注册；新增模型时在 `llm.yaml` 注册；新增服务时在 `ALLOWED_SERVICES` 注册。注册是加法，修改是破坏。

3. **包装 > 侵入**
   > 需要自定义行为时，子类化或包装核心类（如 `SkillHubClient`、`MethodologyRegistry`），而非修改其源码。

4. **契约守恒**
   > `TOOL_REGISTRY` 的键名、`compile_methodology_dag` 的节点 Schema、`ServiceMemoryStore` 的三元组隔离、`call()` 的 `{"ok": bool}` 返回格式，是系统的**硬契约**，修改成本极高。

5. **context 优先**
   > 所有业务变体优先通过 `context: Dict[str, Any]` 传递，不提升为一级字段。`context` 是系统的"无限扩展沙盒"。

6. **新增 Router 而非改造 Router**
   > 新增接口时新建 router 文件并 `include_router`，不在现有 router 中插入业务分支。
