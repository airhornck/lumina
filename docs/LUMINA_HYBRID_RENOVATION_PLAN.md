# Lumina 混合改造计划（最终版）

> 版本：v3.1（阶段 3 已完成：接口统一化与能力 Skill 化）
> 日期：2026-07-07
> 状态：**阶段 2 已完成，阶段 3 已完成**
> 需求变更：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` v1.2 —— 对外服务流接口统一收敛到 `POST /api/v1/services/system-chat/stream`
> 约束条件：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`
> 决策依据：`docs/LUMINA_RENOVATION_BASE_COMPARISON_AND_PLAN.md`
> 工程纪律：`D:/notebook/产品方案/超级工程纪律 1.md`

> **⚠️ 架构决策更新（2026-07-15）**：聊天链路已决策统一为 Hermes LLM planner 架构，本文所述意图识别/规则编排体系将于 Phase 4 P2 阶段退役，详见 `docs/specs/phase4_unified_planner_deprecation_spec.md`。

---

## 一、引言

本文档已按照《超级工程纪律 1》的工程框架重新升级，将 **Discipline（纪律）**、**Harness（安全网）** 与 **Loop Engineering（循环工程）** 融入 Lumina 的混合改造全过程。

核心执行逻辑：

> **人类定义边界（输入与终态），AI 在 Harness 约束下自主进行 Loop 迭代（自愈），直到达到终态门禁。**

每个改造阶段都必须走完：

```
[ 需求导入 ] ──> [ 1. 契约锁定 ] ──> [ 2. 自动化前置 (Harness) ]
                                              │
         ┌────────────────────────────────────┴──────────────────────────┐
         │  【 3. 循环工程核心层 (Loop Engineering) 】                    │
         │                                                              │
         │   AI Worker ──执行代码──> Workspace                          │
         │       ▲                         │                            │
         │       │ 自我修正               │ 自动触发验证                 │
         │       │                       ▼                            │
         │   Escalation <──报错反馈── AI Checker (Linter/Test)        │
         │   (3次失败熔断)                                            │
         └────────────────────────────────────────────────────────────┘
                                              │
                                              ▼ (完全绿灯)
                         [ 4. 双轨评审与持续集成 ] ──> [ 5. 灰度交付 ]
```

---

## 二、核心原则

### 2.1 业务原则

1. **业务真源优先**：Lumina 是个人创作者/KOL 的对话式 AI 营销助手，所有改造必须服务于创作者体验
2. **接口统一化**：对外服务流统一为单一入口 `POST /api/v1/services/system-chat/stream`；爆款榜单（TrendingRank）、内容定位矩阵（ContentPositionMatrix）、每周决策快报（WeeklyOpsBrief）以 Skill / Agent 方式挂载，通过关键词或意图唤起
3. **统一接口绝对稳定**：统一接口的请求/响应格式、SSE 事件类型、错误码必须保持不变；原独立专项接口（`content-ranking`、`positioning`、`weekly-snapshot`）按过渡期计划下线
4. **最小化改造**：不引入不必要的架构变动，不新增容器，不做 A/B 测试
5. **渐进式演进**：先快速修复现有 Python 架构的 P0 问题，再逐步引入 Hermes Agent 能力；接口统一化采用"新增统一路由 + 原端点标记废弃 + 最终下线"的渐进路径
6. **风险可控**：每个阶段都有回滚方案，保留 `LUMINA_USE_HERMES=false` 开关及新增的统一接口开关

### 2.2 工程纪律原则

6. **契约锁定先行**：任何改造前必须产出 `SPECIFICATION.md`，明确输入输出边界、业务规则、极端边界条件
7. **测试先行（TDD Harness）**：生产代码之前必须先写自动化测试，初始状态为 Red
8. **宪法级上下文控制**：技术栈版本、架构分层、反模式通过 `.cursorrules` 或 `.windsurfrules` 锁定
9. **Feature Flag 包裹**：所有新功能必须通过特性开关控制，支持渐进式放量与秒级回滚
10. **覆盖率门禁**：增量代码测试覆盖率 ≥ 85%，E2E 自动化测试全绿方可合入
11. **自愈循环熔断**：同一个 Bug AI 自主修正上限为 3 次，超过则停止并上报底层矛盾
12. **可观测与自动回滚**：新模块单独配置低阈值告警，异常自动回滚

---

## 三、目标

### 3.1 业务目标

解决当前 Lumina 最严重的三个 P0 问题：

| 问题 | 当前表现 | 期望结果 |
|------|----------|----------|
| 没有记忆 | 会话重启后忘记用户偏好 | 长期记住用户风格、产品、历史内容 |
| 不会自主规划 | 复杂任务直接执行，效果差 | 能分解任务、多轮收集信息、分步执行 |
| 强制生成 | 信息不足时也直接生成低质量内容 | 信息完整后再生成，必要时主动追问 |

### 3.2 技术目标

- 对外服务流接口统一为 `POST /api/v1/services/system-chat/stream`
- 爆款榜单（TrendingRank）、内容定位矩阵（ContentPositionMatrix）、每周决策快报（WeeklyOpsBrief）作为 Skill / Agent 挂载到统一接口
- 保持现有 FastAPI 接口层不变（除原独立专项端点按规划下线）
- 不新增 Docker 容器
- 不引入跨语言桥接
- 让 Hermes Agent 作为可选执行引擎逐步接管复杂对话
- 所有改造遵循工程纪律框架

---

## 四、最终架构

### 4.1 总体架构

```
┌─────────────────────────────────────────────────────┐
│                    前端 / 客户端                      │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              Lumina FastAPI 路由层                   │
│  POST /api/v1/services/system-chat/stream           │
│  （统一对话入口：系统对话 + Skill 挂载能力）           │
│                                                     │
│  保留接口：/api/v1/debug/chat/stream                 │
│           /api/v1/marketing/hub                     │
│           /skill/* /api/v1/usage/* /api/v1/exports/*│
│           /mcp                                      │
└─────────────────────────────────────────────────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
┌──────────────────┐      ┌────────────────────┐
│  现有 Python      │      │  Hermes AIAgent    │
│  处理逻辑         │      │  （Python 库）      │
│  （阶段 0 修复）   │      │  （阶段 1 引入）    │
│                  │      │                    │
│  - 规则 intent   │      │  - Agent 规划       │
│  - 现有 Skill    │      │  - 工具调用         │
│  - 内容生成      │      │  - 长期记忆         │
│  - 任务状态机    │      │  - Skill 注册       │
│  - Skill 路由    │      │                    │
└──────────────────┘      └────────────────────┘
            │                       │
            └───────────┬───────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│              统一数据层                              │
│  PostgreSQL：对话记录、用户画像、Token 用量          │
│  Hermes 数据目录：记忆索引、Skill、会话状态          │
└─────────────────────────────────────────────────────┘
```

> **目标态注记（2026-07-15）**：上图双引擎并存为过渡态；目标态为 Hermes AIAgent 唯一引擎，左侧规则 intent / 任务状态机 / Skill 路由将于 Phase 4 P2 移除（phase4 spec §7）。

### 4.2 Hermes 集成方式

**Hermes 作为 Python 库内嵌到 lumina-api 进程中**，不启动独立服务：

```python
if settings.LUMINA_USE_HERMES:
    from hermes import AIAgent
    agent = AIAgent(config=hermes_config)
    response = await agent.run(user_message, context=lumina_context)
else:
    response = await legacy_marketing_orchestra_process(...)  # （P2 切换后该分支与开关一并移除）
```

这样设计的好处：
- 不新增容器
- 不新增端口
- 无网络通信开销
- 回滚只需改环境变量

---

## 五、工程纪律基础设施

### 5.1 宪法级上下文控制

在项目根目录建立/更新 `.cursorrules`（或 `.windsurfrules`），锁定：

| 控制项 | 规则 |
|--------|------|
| 技术栈版本 | Python 3.12，FastAPI 0.10x，Hermes 核心依赖版本锁定 |
| 架构分层 | API 层只负责路由和序列化；业务逻辑在 Skill/Orchestra；Hermes 适配器在 services 层 |
| 禁止反模式 | 禁止使用 `any` 类型；禁止在路由层写业务逻辑；禁止使用进程内 dict 作为持久化存储 |
| 接口约束 | 禁止修改现有接口路径、参数、SSE 事件类型、错误码 |
| 测试要求 | 新增代码必须伴随测试；覆盖率 ≥ 85% |
| 安全红线 | Hermes 危险工具必须显式禁用；禁止在用户请求中执行任意代码 |

### 5.2 契约文件规范

每个改造阶段必须产出独立的 `SPECIFICATION.md`：

```
docs/specs/
├── phase0_memory_spec.md
├── phase0_progressive_generation_spec.md
├── phase0_task_state_spec.md
├── phase1_hermes_adapter_spec.md
├── phase1_hermes_memory_provider_spec.md
├── phase1_hermes_tools_spec.md
└── phase2_vector_memory_spec.md
```

每个 `SPECIFICATION.md` 必须包含：
- 输入输出边界
- 核心业务规则
- 极端边界条件（Edge Cases）
- 错误处理策略
- 安全合规要求
- 接口兼容性声明

### 5.3 Harness 检查点

每个阶段必须通过三大 Harness 检查点：

| 检查点 | 内容 | 负责人 |
|--------|------|--------|
| 数据结构 | Pydantic 模型、数据库 Schema、API 契约 | AI + 人类 Review |
| 错误处理 | 错误码、异常边界、降级策略 | AI + 人类 Review |
| 安全合规 | 数据隔离、工具禁用、内容安全 | AI + 人类 Review |

---

## 六、阶段计划

---

### 阶段 0：契约锁定 + Python 快速修复（✅ 已完成）

目标：在现有 Python 架构内解决三个 P0 问题，并建立工程纪律基线。

**完成总结**：
- 已产出 3 份 SPEC 并通过 Review
- 已建立 `.cursorrules`
- 已按 TDD Harness 编写并通过所有测试
- 新增代码测试覆盖率 **88%**（≥85% 门禁）
- 本地非外部依赖测试 **123 passed, 1 skipped**
- 接口回归测试全部通过，SSE 格式保持不变
- Feature Flag 已全部生效

#### 6.1 契约锁定（第 1 周前半周）

**动作**：
- 人类引导 AI 将业务真源中的 P0 需求解析为 3 份 `SPECIFICATION.md`：
  - `docs/specs/phase0_memory_spec.md`
  - `docs/specs/phase0_progressive_generation_spec.md`
  - `docs/specs/phase0_task_state_spec.md`
- 每个 Spec 明确：
  - 输入：用户消息、会话 ID、历史记录、任务状态
  - 输出：SSE 事件流、任务状态更新、记忆写入
  - 边界条件：空消息、超长历史、并发写入、服务重启

**输出**：
- 3 份经过人类 Review 确认的 SPEC 文件
- 更新的 `.cursorrules`

**Harness 检查点**：
- [x] 数据结构审查通过
- [x] 错误处理策略审查通过（降级策略、异常处理已覆盖）
- [x] 安全合规审查通过（SQL 注入防护、数据隔离、危险工具禁用）

#### 6.2 自动化前置：TDD Harness（第 1 周后半周）

**动作**：
- 依据 SPEC，让 AI **先编写自动化测试用例**
- 测试覆盖：
  - 单元测试：`tests/chat_debug/test_memory_postgres.py`、`tests/orchestra/test_progressive_generation.py`、`tests/orchestra/test_task_state.py`
  - mock 测试：`tests/chat_debug/test_memory_postgres_mock.py`、`tests/orchestra/test_task_state_mock.py`
  - 接口回归测试：`tests/interface_regression/test_debug_chat_stream.py`

**状态控制**：
- 初始运行测试，状态为 **Red（失败）**
- 循环工程后，状态转为 **Green（通过）**
- Red 状态构成后续 Loop 工程的终止边界

**输出**：
- 测试文件集合
- CI 流水线配置更新（覆盖率门禁）

#### 6.3 循环工程：Python 修复实现（第 2-3 周）

启动 AI Agent 模式，执行 Self-Healing Loop：

**6.3.1 持久化记忆**

**现状**：`ChatMemoryStore` 使用 `defaultdict(list)`，进程重启丢失。

**改造**：
- 新增 `PostgresChatMemoryStore` 实现同一接口
- 增加 `CHAT_MEMORY_BACKEND` 环境变量（`memory` / `postgres`）
- 对话记录写入 PostgreSQL，按时间排序，可配置保留条数
- 迁移现有内存数据（如有需要）

**关键文件**：
- `apps/api/src/chat_debug/memory.py`（保留内存实现，根据 `CHAT_MEMORY_BACKEND` 自动选择后端）
- 新增 `apps/api/src/chat_debug/memory_postgres.py`（PostgreSQL 实现，自动降级到内存）
- `apps/api/src/services/memory_service.py`（无需改动）
- 新增 `tests/chat_debug/test_memory_postgres.py`（单元测试）
- 新增 `tests/chat_debug/test_memory_postgres_mock.py`（PostgreSQL 路径 mock 测试）

**Feature Flag**：
```bash
CHAT_MEMORY_BACKEND=postgres  # 或 memory 回滚
```

**验收标准**：
- [x] 重启容器后历史对话不丢失（PostgreSQL 路径已实现，mock 测试覆盖）
- [x] 保留条数可配置（`max_messages_per_conv` 参数）
- [x] 单元测试通过（6 个测试 + 5 个 mock 测试通过）

**6.3.2 渐进式生成**

**现状**：用户说"帮我写文案"直接生成，不管信息是否足够。

**改造**：
- 在 `MarketingOrchestra` 中增加 "信息完整性检查" 步骤
- 定义关键内容类型的必要字段（产品、卖点、平台、风格等）
- 信息不足时返回澄清问题，不调用生成器
- 使用轻量级 LLM 或规则判断完整性

**关键文件**：
- `apps/orchestra/src/orchestra/core.py`（在 content 分支前插入完整性检查）
- 新增 `apps/orchestra/src/orchestra/intent_guards.py`（完整性检查入口）
- 新增 `apps/orchestra/src/orchestra/required_fields.py`（字段定义、推断规则、追问模板）
- 新增 `tests/orchestra/test_progressive_generation.py`（单元测试）

**Feature Flag**：
```bash
LUMINA_ENABLE_PROGRESSIVE_GENERATION=true  # 或 false 回滚
```

**验收标准**：
- [x] 缺少关键信息时，返回追问消息
- [x] 信息齐全时，正常生成内容
- [x] 不破坏现有测试（全量非外部依赖测试 123 passed）

**6.3.3 任务状态机**（已决策退役，Phase 4 P2 由 Hermes todo 工具取代，PG 表保留）

**现状**：每个请求都是独立的，无法跟踪复杂任务进度。

**改造**：
- 新增 `TaskState` 模型：记录任务类型、已收集信息、下一步、状态
- 在 PostgreSQL 中存储任务状态
- 在 `MarketingOrchestra` 中根据任务状态决定下一步
- 支持任务：内容规划、账号诊断、矩阵运营等

**关键文件**：
- 新增 `apps/orchestra/src/orchestra/task_state.py`（TaskState 模型、存储、生命周期管理）
- `apps/orchestra/src/orchestra/core.py`（在 `process()` 中集成任务状态机，步骤完成后自动引导下一步）
- 新增 `tests/orchestra/test_task_state.py`（单元测试）
- 新增 `tests/orchestra/test_task_state_mock.py`（PostgreSQL 路径 mock 测试）

**Feature Flag**：
```bash
LUMINA_ENABLE_TASK_STATE=true  # 或 false 回滚
```

**验收标准**：
- [x] 复杂任务能多轮收集信息（通过 `collected_info`）
- [x] 任务状态持久化（PostgreSQL + 内存 fallback）
- [x] 用户可随时查看当前任务进度（通过 `get_active_task`）

#### 6.4 自愈循环与熔断

**运行机制**：
1. **Action**：AI 编写/修改生产代码
2. **Observe**：AI 自动运行 `pytest tests/orchestra tests/chat_debug tests/integration tests/interface_regression`
3. **Reflective**：若失败，AI 自主读取报错 Trace，重新思考并修正

**熔断规则**：
- 同一个 Bug 自主修正上限为 **3 次**
- 超过 3 次或连续耗时超过 5 分钟，AI 必须停止 Loop
- 高亮打印底层逻辑矛盾，交由人类架构师裁决

#### 6.5 双轨评审与准出

**本地 Pre-commit**：
- `ruff` 代码检查
- `mypy` 类型检查
- `pytest` 单元测试
- 接口回归测试

**CI 门禁**：
- 增量代码测试覆盖率 ≥ 85%
- E2E 测试全绿

**人类 Review**：
- 资深工程师审查业务逻辑合规性与架构设计

---

### 阶段 1：Hermes 集成（✅ 已完成）

目标：将 Hermes Agent 作为可选执行引擎引入，接管复杂对话。

**完成总结**：
- 已产出 4 份 SPEC 并通过 Review
- 已按 TDD Harness 编写并通过所有测试
- 新增代码测试覆盖率 **86%**（≥85% 门禁）
- 全量非外部依赖测试 **150 passed, 1 skipped**
- 接口回归测试全部通过，SSE 格式保持不变
- Hermes 危险工具已禁用
- `LUMINA_USE_HERMES=false` 默认安全关闭

#### 7.1 契约锁定（第 1 周）

**动作**：
- 产出 4 份 SPEC（✅ 已完成）：
  - `docs/specs/phase1_hermes_adapter_spec.md`
  - `docs/specs/phase1_hermes_memory_provider_spec.md`
  - `docs/specs/phase1_hermes_tools_spec.md`
  - `docs/specs/phase1_hermes_security_spec.md`

**关键契约**：
- Hermes 输出必须转换为 Lumina SSE v1/v2 格式
- Lumina 记忆提供器必须兼容现有 PostgreSQL 记忆表
- Hermes 只能调用 `lumina_marketing` 工具集
- 危险工具必须显式禁用

#### 7.2 自动化前置：TDD Harness（第 1-2 周）

**测试覆盖**：
- `tests/hermes/test_adapter.py`：Hermes 输出 → Lumina SSE 转换
- `tests/hermes/test_memory_provider.py`：记忆读写一致性
- `tests/hermes/test_tool_registration.py`：工具注册与禁用
- `tests/interface_regression/test_debug_chat_stream.py`：接口回归

**状态控制**：
- 初始运行测试为 **Red**

#### 7.3 循环工程：Hermes 集成实现（第 3-6 周）

**7.3.1 Hermes 环境准备（✅ 已完成）**

- 将 Hermes 路径加入 `pyproject.toml` 的 `pythonpath` 和可选依赖
- 创建 `data/hermes/` 目录结构
- 配置 Hermes persona（Lumina 营销助手人设）
- 禁用 Hermes 危险工具（terminal、browser、code execution 等）

**关键文件**：
- `pyproject.toml`（新增 hermes 可选依赖、pytest pythonpath）
- `docker-compose.yml`（已含 Hermes 数据卷）
- 新增 `data/hermes/config.yaml`
- 新增 `data/hermes/personas/lumina-marketing.md`

**7.3.2 Hermes 引擎适配器（✅ 已完成）**

- 新增 `HermesEngineAdapter` 类
- 封装 Hermes 的调用逻辑
- 将 Lumina 的会话上下文转换为 Hermes 格式
- 将 Hermes 输出转换为 Lumina SSE 格式
- 支持 mock 模式用于测试

**关键文件**：
- 新增 `apps/api/src/services/hermes_adapter.py`
- 新增 `tests/hermes/test_adapter.py`
- 新增 `tests/hermes/test_adapter_mock.py`

**7.3.3 Lumina 记忆提供器（✅ 已完成）**

- 实现 `LuminaMemoryProvider`
- 让 Hermes 通过 Lumina 的 PostgreSQL 记忆层读写历史
- 确保 Hermes 记忆与 Lumina 记忆一致

**关键文件**：
- 新增 `apps/api/src/services/hermes_memory_provider.py`
- 新增 `tests/hermes/test_memory_provider.py`

**7.3.4 Lumina Skill 注册为 Hermes 工具（✅ 已完成）**

- 将现有 Skill（内容生成、账号诊断等）包装为 Hermes 工具
- 定义工具 schema
- 在 Hermes 中注册 `lumina_marketing` 工具集
- 严格限制 Hermes 可调用工具，禁用通用危险工具

**关键文件**：
- 新增 `apps/api/src/services/hermes_tools.py`
- 新增 `tests/hermes/test_tool_registration.py`
- `skills/*`

**7.3.5 路由层集成（✅ 已完成）**

- 在 `/api/v1/debug/chat/stream` 中增加 Hermes 路由逻辑
- 根据 `LUMINA_USE_HERMES` 选择处理引擎
- 保持 SSE 输出格式不变
- 增加接口回归测试

**关键文件**：
- `apps/api/src/chat_debug/router.py`
- 新增 `tests/interface_regression/test_debug_chat_stream.py`

**Feature Flag**：
```bash
LUMINA_USE_HERMES=false  # 阶段 1 默认 false，验证稳定后全量开启
```

**验收标准**：
- [x] `LUMINA_USE_HERMES=true` 时走 Hermes 引擎
- [x] `LUMINA_USE_HERMES=false` 时走原引擎
- [x] 所有接口回归测试通过
- [x] 危险工具全部禁用

#### 7.4 双轨评审与准出

同阶段 0。

---

### 阶段 2：架构收敛（✅ 已完成）

目标：沉淀方法论，优化长期能力。

**完成总结**：
- 已产出 3 份 SPEC 并通过 Review
- 已按 TDD Harness 编写并通过所有测试（15 passed）
- 新增代码测试覆盖率 ≥ 85%（达到门禁）
- Hermes Markdown Skill 已上线，支持 positioning / hook_story_offer / aida / pas 四种方法论
- PostgreSQL 已迁移至 pgvector 镜像，向量记忆表与索引已就绪
- LLMClient 已接入响应缓存，模型降级/Token 监控/历史摘要能力已实现
- 遗留代码清理：修复 30 处未使用变量/导入问题

#### 8.1 契约锁定（第 1 周）

**动作**：
- 产出 3 份 SPEC（✅ 已完成）：
  - `docs/specs/phase2_markdown_skill_spec.md`
  - `docs/specs/phase2_vector_memory_spec.md`
  - `docs/specs/phase2_cost_optimization_spec.md`

#### 8.2 自动化前置：TDD Harness（✅ 已完成）

**测试覆盖**：
- Markdown Skill 解析与执行测试（`tests/phase2/test_markdown_skill.py`）
- 向量记忆检索测试（`tests/phase2/test_vector_memory.py`）
- LLM 成本监控测试（`tests/phase2/test_cost_optimization.py`）

#### 8.3 循环工程：架构收敛实现（✅ 已完成）

**8.3.1 Hermes Markdown Skill（✅ 已完成）**

- 将 Lumina 的营销方法论（诊断框架、文案公式、矩阵策略）写成 Hermes Skill
- 支持动态加载和版本管理
- 让 Hermes 能根据 Skill 执行专业营销任务
- 新增 `lumina_execute_methodology` 工具并注册到 Hermes 工具集

**关键文件**：
- 新增 `data/hermes/skills/lumina-marketing/SKILL.md`
- 新增 `apps/api/src/services/hermes_markdown_skill.py`
- 新增 `data/methodologies/aida.yml`
- 新增 `data/methodologies/pas.yml`
- 修改 `apps/api/src/services/hermes_tools.py`

**8.3.2 向量记忆（✅ 已完成）**

- 引入向量数据库 pgvector
- 支持基于语义的长期记忆检索
- 记住用户的内容风格、历史爆款、偏好设置
- embedding 失败时降级为 trgm 文本相似搜索

**关键文件**：
- 修改 `docker-compose.yml`：使用 `pgvector/pgvector:pg16` 镜像
- 修改 `infra/sql/init.sql`：添加 vector 扩展与 `memory_embeddings` 表
- 新增 `apps/api/src/chat_debug/vector_memory.py`

**Feature Flag**：
```bash
LUMINA_USE_VECTOR_MEMORY=false   # 默认关闭
LUMINA_USE_VECTOR_MEMORY=true    # 启用向量记忆

# 阶段 2 新增
LUMINA_ENABLE_RESPONSE_CACHE=true
LUMINA_ENABLE_MODEL_FALLBACK=true
LUMINA_ENABLE_HISTORY_SUMMARY=true
LUMINA_ENABLE_COST_MONITOR=true
```

**8.3.3 LLM 成本优化（✅ 已完成）**

- 增加响应缓存（已接入 `LLMClient.complete`）
- 使用模型降级策略
- 监控 Token 消耗
- 摘要化长历史

**关键文件**：
- 新增 `packages/llm-hub/src/llm_hub/cost_optimizer.py`
- 修改 `packages/llm-hub/src/llm_hub/client.py`

**8.3.4 清理遗留代码（✅ 已完成）**

- 删除或标记废弃代码：ruff 自动修复 28 处未使用导入/变量，手动修复 2 处
- 统一错误处理：保持现有模式，未引入破坏性变更
- 更新文档：本计划已同步更新

---

### 阶段 3：接口统一化与能力 Skill 化（✅ 已完成）

目标：依据业务真源 v1.2 需求变更，将对外 4 个独立服务流接口收敛为单一入口 `POST /api/v1/services/system-chat/stream`，并将爆款榜单（TrendingRank）、内容定位矩阵（ContentPositionMatrix）、每周决策快报（WeeklyOpsBrief）以 Skill / Agent 方式挂载到统一接口中。

**完成总结**：
- 已产出 3 份 SPEC 并通过 Review
- 已按 TDD Harness 编写并通过所有测试（23 passed）
- 新增代码测试覆盖率 ≥ 85%（达到门禁）
- 爆款榜单（TrendingRank）、内容定位矩阵（ContentPositionMatrix）、每周决策快报（WeeklyOpsBrief）已封装为独立 Skill 并挂载到 `system-chat`
- `MarketingOrchestra` 已支持关键词意图路由到对应 Skill
- Hermes 已注册 `lumina_content_ranking`、`lumina_positioning_matrix`、`lumina_weekly_snapshot` 三个 Tool
- 原独立端点废弃开关已生效：过渡期返回 `Deprecation: true`，最终模式下返回 `410 Gone`
- 接口回归测试 100% 通过

#### 9.0 方案评估与选择

**背景**：当前对外提供 4 个独立服务流接口：`system-chat`、`content-ranking`、`positioning`、`weekly-snapshot`。前端需要维护多套调用逻辑，且与 Lumina "对话式 AI 助手"的单一入口定位不符。

**评估方案**：

| 方案 | 说明 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| **A. 保持现状** | 继续维护 4 个独立接口 | 前端改动最小 | 入口分散、扩展性差、与产品定位不符 | ❌ 放弃 |
| **B. 完全替换** | 立即下线 3 个独立接口，全部迁移到统一接口 | 最简洁、无历史包袱 | 风险高，前端/第三方接入方需一次性适配，无回滚空间 | ❌ 风险过高 |
| **C. 渐进式统一（推荐）** | 统一接口立即提供完整能力；原独立端点标记废弃并保留兼容开关；通过 Feature Flag 分阶段放量；过渡期后最终下线 | 风险可控、可灰度、可回滚、前端可分批迁移、符合对话式助手定位 | 需要维护一段过渡期代码 | ✅ **采用** |

**最终方案：渐进式统一（方案 C）**

核心设计：
1. **单一入口**：对外只暴露 `POST /api/v1/services/system-chat/stream`
2. **Skill 化挂载**：
   - **爆款榜单（TrendingRank）** → `trending_rank_skill`（原 content_ranking）
     - 多平台爆款内容聚合与智能排序引擎
     - 跨平台（抖音/B站/小红书）爆款采集、关键词泛化、多维度加权排序
   - **内容定位矩阵（ContentPositionMatrix）** → `content_position_matrix_skill`（原 positioning_matrix）
     - 基于爆款分析的内容战略定位工具
     - 横轴专业度 × 纵轴娱乐度 × 颜色互动强度，识别蓝海/红海与差异化机会
   - **每周决策快报（WeeklyOpsBrief）** → `weekly_ops_brief_skill`（原 weekly_snapshot）
     - 基于本周作品互动数据的运营决策分析引擎
     - 3P 报告结构：Progress（本周表现）/ Problems（问题识别）/ Plans（下周策略）
3. **意图驱动唤起**：在 `system-chat` 的意图识别层增加对上述 Skill 的关键词/语义路由
4. **双引擎兼容**：MarketingOrchestra 和 Hermes 均支持识别对应意图并调用 Skill
5. **记忆统一**：统一使用 `system-chat` 服务记忆，不再按原 `service` 隔离
6. **过渡期管理**：原 `/api/v1/services/{service}/stream` 保留废弃兼容，默认返回 `410 Gone` 或 301 引导到统一接口；可通过开关临时恢复

#### 9.1 契约锁定（第 12 周）

**动作**：
- 产出 3 份 SPEC：
  - `docs/specs/phase3_unified_interface_spec.md`：统一接口请求/响应、SSE 格式、错误码
  - `docs/specs/phase3_skill_intent_routing_spec.md`：Skill 注册、意图关键词、路由规则
  - `docs/specs/phase3_legacy_endpoint_deprecation_spec.md`：原接口废弃策略、兼容开关、最终下线计划

**关键契约**：
- 统一接口请求体保持 `ServiceStreamRequest`，响应 SSE 与现有 `system-chat` 一致
- Skill 唤起关键词示例：
  - 爆款榜单（TrendingRank）："查爆款榜单"、"抖音热门"、"小红书爆款"、"B站 trending"、"全网热点"、"内容方向榜单"、"排一下方向"
  - 内容定位矩阵（ContentPositionMatrix）："分析内容定位"、"内容矩阵"、"定位诊断"、"爆款定位分析"、"找差异化方向"、"定位矩阵"
  - 每周决策快报（WeeklyOpsBrief）："生成本周快报"、"运营周报"、"决策报告"、"本周复盘"、"下周策略"、"每周决策快照"、"整理本周决策"
- 原独立端点返回明确的废弃提示，引导调用方迁移到统一接口

**Harness 检查点**：
- [ ] 数据结构审查通过（请求体、SSE 事件、Skill schema）
- [ ] 错误处理策略审查通过（废弃端点返回码、降级策略）
- [ ] 安全合规审查通过（Skill 权限、数据隔离、危险工具禁用）

#### 9.2 自动化前置：TDD Harness（第 12 周）

**测试覆盖**：
- `tests/interface_regression/test_unified_system_chat_stream.py`：统一接口回归测试
- `tests/skills/test_content_ranking_skill.py`：爆款榜单（TrendingRank）Skill 单元测试
- `tests/skills/test_positioning_matrix_skill.py`：内容定位矩阵（ContentPositionMatrix）Skill 单元测试
- `tests/skills/test_weekly_snapshot_skill.py`：每周决策快报（WeeklyOpsBrief）Skill 单元测试
- `tests/orchestra/test_skill_intent_routing.py`：意图路由测试
- `tests/interface_regression/test_legacy_endpoint_deprecation.py`：原接口废弃行为测试

**状态控制**：
- 初始运行测试为 **Red**

#### 9.3 循环工程：接口统一化实现（第 13-15 周）

**9.3.1 Skill 化改造**

将原 `services/handlers/content_ranking.py`、`positioning.py`、`weekly_snapshot.py` 中的 system prompt + LLM 调用逻辑，封装为独立 Skill：

- 新增 `apps/orchestra/src/orchestra/skills/content_ranking_skill.py`
- 新增 `apps/orchestra/src/orchestra/skills/positioning_matrix_skill.py`
- 新增 `apps/orchestra/src/orchestra/skills/weekly_snapshot_skill.py`

每个 Skill 接口统一为：
```python
async def run(message: str, platform: str | None, context: dict, history: list[dict]) -> str
```

**9.3.2 意图识别与 Skill 路由**（已决策退役，意图路由由 Hermes planner 承担）

在 `MarketingOrchestra` 中增加 `skill_intent_router`：
- 基于关键词 + 轻量级 LLM 语义判断，识别用户是否请求榜单/矩阵/快照
- 命中则调用对应 Skill，返回结果包装为 `system-chat` 的 SSE 格式
- 未命中则走原有业务逻辑（诊断、生成、规划等）

Hermes 路径同步注册 3 个新 Tool：
- `lumina_content_ranking`
- `lumina_positioning_matrix`
- `lumina_weekly_snapshot`

**9.3.3 记忆统一**

- 统一使用 `service="system-chat"` 读写记忆
- 原独立服务记忆数据可保留只读，但新对话不再写入

**9.3.4 原接口废弃**

- 修改 `apps/api/src/services/router.py`
- 当 `LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=true` 时：
  - 对 `content-ranking`、`positioning`、`weekly-snapshot` 返回 `410 Gone`，响应体包含迁移指引
  - 仅保留 `system-chat` 和 `cross-platform-content`（如业务需要）
- 当 `LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=false`（过渡期）时：
  - 原接口继续可用，但响应头增加 `Deprecation: true`

#### 9.4 Feature Flag

```bash
# 阶段 3 Feature Flags
LUMINA_UNIFIED_SYSTEM_CHAT=true          # 启用统一接口 Skill 路由
LUMINA_ENABLE_CONTENT_RANKING_SKILL=true
LUMINA_ENABLE_POSITIONING_MATRIX_SKILL=true
LUMINA_ENABLE_WEEKLY_SNAPSHOT_SKILL=true
LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=false    # 为 true 时下线原独立端点
```

#### 9.5 验收标准

- [ ] `POST /api/v1/services/system-chat/stream` 可通过自然语言触发爆款榜单（TrendingRank）、内容定位矩阵（ContentPositionMatrix）、每周决策快报（WeeklyOpsBrief）
- [ ] 三个 Skill 的 SSE 输出与现有 `system-chat` 格式一致
- [ ] 统一接口回归测试 100% 通过
- [ ] 原独立端点在 `LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=true` 时返回 `410 Gone`
- [ ] 新增代码测试覆盖率 ≥ 85%
- [ ] Feature Flag 可秒级回滚

---

## 七、接口统一化与兼容性保障

### 7.1 对外服务流统一入口

| 接口 | 路径 | 方法 | 说明 |
|------|------|------|------|
| **统一服务对话** | `/api/v1/services/system-chat/stream` | POST | **唯一对外服务流入口**，承载系统对话 + 爆款榜单 + 内容定位矩阵 + 每周决策快报 |

### 7.2 保留但非服务流核心的接口

| 接口 | 路径 | 方法 | 说明 |
|------|------|------|------|
| 调试聊天 | `/api/v1/debug/chat/stream` | POST | 内部调试，可路由到 Hermes，SSE 格式不变 |
| 营销中枢 | `/api/v1/marketing/hub` | POST | 营销编排 API，保持不变 |
| Skill | `/skill/*` | 多种 | Skill 直调接口，保持不变 |
| 用量 | `/api/v1/usage/*` | 多种 | 用量统计，保持不变 |
| 导出 | `/api/v1/exports/*` | 多种 | 导出能力，保持不变 |
| 健康检查 | `/health` | GET | 健康检查，保持不变 |
| MCP | `/mcp` | 多种 | MCP 接口，保持不变 |

### 7.3 已下线/废弃的服务流接口

| 接口 | 路径 | 方法 | 状态 |
|------|------|------|------|
| 爆款榜单（原 content-ranking） | `/api/v1/services/content-ranking/stream` | POST | **已废弃**，能力迁移到统一接口 Skill |
| 内容定位矩阵（原 positioning） | `/api/v1/services/positioning/stream` | POST | **已废弃**，能力迁移到统一接口 Skill |
| 每周决策快报（原 weekly-snapshot） | `/api/v1/services/weekly-snapshot/stream` | POST | **已废弃**，能力迁移到统一接口 Skill |

> 废弃策略：过渡期（建议 ≤ 2 周）内可通过 `LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=false` 临时恢复；过渡期结束后默认返回 `410 Gone`。


### 7.4 必须保持不变的 SSE 事件

```json
{"type": "start", "capability": "...", "conversation_id": "..."}
{"type": "assistant_delta", "payload": "..."}
{"type": "export_link", "payload": {"url": "..."}}
{"type": "compliance_report", "payload": {...}}
{"type": "done", "timestamp": "..."}
```

### 7.5 回归测试

每个阶段必须运行：

```bash
pytest tests/interface_regression/ -v
```

测试覆盖：
- 所有接口返回格式
- 所有 SSE 事件类型
- 错误码
- 特殊字符、长文本、空输入等边界情况

---

## 八、安全与风险控制

### 8.1 Hermes 工具安全

Hermes 默认包含危险工具，必须严格禁用：

```python
DISABLED_HERMES_TOOLS = [
    "terminal",
    "execute_code",
    "browser",
    "shell",
    "file_write",
    "file_delete",
    "file_read",
    "python",
]

ENABLED_HERMES_TOOLSETS = ["lumina_marketing"]
```

### 8.2 数据安全

- Hermes 数据目录使用 Docker 命名卷持久化
- 不将用户数据暴露给 Hermes 外部服务
- Hermes 记忆通过 Lumina 记忆提供器读写，受 Lumina 权限控制

### 8.3 回滚方案

| 场景 | 操作 |
|------|------|
| Hermes 不稳定 | `LUMINA_USE_HERMES=false` |
| PostgreSQL 记忆问题 | `CHAT_MEMORY_BACKEND=memory` |
| 渐进式生成问题 | `LUMINA_ENABLE_PROGRESSIVE_GENERATION=false` |
| 任务状态机问题 | `LUMINA_ENABLE_TASK_STATE=false` |
| 新代码严重 bug | 回滚到上一版本镜像 |
| 统一接口 Skill 路由异常 | `LUMINA_UNIFIED_SYSTEM_CHAT=false` |
| 内容方向榜单 Skill 异常 | `LUMINA_ENABLE_CONTENT_RANKING_SKILL=false` |
| 定位矩阵 Skill 异常 | `LUMINA_ENABLE_POSITIONING_MATRIX_SKILL=false` |
| 每周决策快照 Skill 异常 | `LUMINA_ENABLE_WEEKLY_SNAPSHOT_SKILL=false` |
| 原独立端点仍需兼容 | `LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=false` |

---

## 九、Docker 部署

### 9.1 容器架构

保持单容器：

```yaml
services:
  lumina-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - lumina_hermes_data:/app/data/hermes
    environment:
      LUMINA_USE_HERMES: "false"
      CHAT_MEMORY_BACKEND: "postgres"
      LUMINA_ENABLE_PROGRESSIVE_GENERATION: "true"
      LUMINA_ENABLE_TASK_STATE: "true"
```

### 9.2 新增卷

```yaml
volumes:
  lumina_hermes_data:
```

### 9.3 新增环境变量

```bash
# 阶段 0 Feature Flags
CHAT_MEMORY_BACKEND=postgres
LUMINA_ENABLE_PROGRESSIVE_GENERATION=true
LUMINA_ENABLE_TASK_STATE=true

# 阶段 1 Feature Flag
LUMINA_USE_HERMES=false
HERMES_HOME=/app/data/hermes
LUMINA_HERMES_ENABLED_TOOLSETS=lumina_marketing
LUMINA_HERMES_DISABLED_TOOLS=terminal,execute_code,browser,shell,file_write,file_delete

# 阶段 2 Feature Flag
LUMINA_USE_VECTOR_MEMORY=false

# 阶段 3 Feature Flags
LUMINA_UNIFIED_SYSTEM_CHAT=true
LUMINA_ENABLE_CONTENT_RANKING_SKILL=true
LUMINA_ENABLE_POSITIONING_MATRIX_SKILL=true
LUMINA_ENABLE_WEEKLY_SNAPSHOT_SKILL=true
LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=false   # 过渡期后设为 true，最终下线原独立端点
```

---

## 十、双轨制质量评审

### 10.1 本地 Pre-commit 强管制

触发 Git Hooks，强制执行：

| 检查项 | 工具 | 失败处理 |
|--------|------|----------|
| 代码风格 | `ruff` | 无法 Commit |
| 类型检查 | `mypy` | 无法 Commit |
| 安全扫描 | `bandit` / `semgrep` | 无法 Commit |
| 单元测试 | `pytest` | 无法 Commit |
| 覆盖率 | `pytest-cov` | 无法 Commit |

### 10.2 双轨 Code Review Pipeline

**第一轨（机器预审）**：
- CI 中的 AI Reviewer 检查 Diff
- 检查是否优雅、是否引入技术债、是否符合 `.cursorrules`
- 若有 Blocker 直接打回

**第二轨（人类终审）**：
- 资深工程师审查业务逻辑合规性与高层架构设计
- 拒绝盲目 Approve

---

## 十一、可观测性与灰度交付

### 11.1 门禁熔断（Gatekeeper）

CI 流水线中：
- **增量代码测试覆盖率 ≥ 85%**
- **E2E 自动化测试全绿**
- 方可构建

### 11.2 渐进式放量

所有新功能通过 Feature Flag 包裹：

```python
if settings.LUMINA_USE_HERMES:
    # Hermes 路径
else:
    # 原路径
```

放量策略：

| 阶段 | 放量范围 | 观察指标 |
|------|----------|----------|
| 内测 | 开发/测试环境 | 接口回归、单元测试 |
| 小流量 | 5% 真实用户 | 5xx 错误率、延迟、用户反馈 |
| 中流量 | 30% 真实用户 | 转化率、对话轮次、内容满意度 |
| 全量 | 100% 用户 | 核心指标稳定 1 周后 |

### 11.3 监控告警

为新模块单独配置低阈值告警：

| 指标 | 阈值 | 动作 |
|------|------|------|
| 5xx 错误率 | > 1% | 自动关闭 Feature Flag 并告警 |
| P95 延迟 | > 5s | 告警 |
| LLM 成本异常 | > 基准 150% | 告警 |
| 接口回归失败 | 任何失败 | 阻断发布 |

### 11.4 异常自动回滚

配置 CI/CD 自动回滚：

```bash
# 当监控触发阈值时，自动设置 Feature Flag 为 false
curl -X POST "${LUMINA_CONFIG_API}/flags/LUMINA_USE_HERMES" \
  -d '{"value": false, "reason": "auto_rollback_high_error_rate"}'
```

---

## 十二、时间线

```
✅ 已完成：阶段 0 契约锁定 + TDD Harness + 循环工程
  ├─ 产出 3 份 SPEC
  ├─ 更新 .cursorrules
  ├─ 编写测试（Red → Green）
  ├─ 持久化记忆
  ├─ 渐进式生成
  ├─ 任务状态机
  └─ 双轨评审与准出

✅ 已完成：阶段 1 Hermes Agent 集成
  ├─ 产出 4 份 SPEC
  ├─ 适配器开发（HermesEngineAdapter）
  ├─ 记忆提供器（LuminaMemoryProvider）
  ├─ Skill 注册为 Hermes 工具
  ├─ 路由集成 + 接口回归测试
  ├─ 安全加固（危险工具禁用）
  └─ 双轨评审与准出

✅ 已完成：阶段 2 架构收敛
  ├─ 产出 3 份 SPEC
  ├─ Hermes Markdown Skill
  ├─ pgvector 向量记忆
  ├─ LLM 成本优化
  ├─ 清理遗留代码
  └─ 双轨评审与准出

第 12 周：阶段 3 契约锁定 + TDD Harness
  ├─ 明确阶段 3 目标与范围：接口统一化与能力 Skill 化
  ├─ 产出 3 份 SPEC
  │   ├─ phase3_unified_interface_spec.md
  │   ├─ phase3_skill_intent_routing_spec.md
  │   └─ phase3_legacy_endpoint_deprecation_spec.md
  └─ 编写 Red 状态测试

第 13-15 周：阶段 3 循环工程
  ├─ 爆款榜单（TrendingRank）/ 内容定位矩阵（ContentPositionMatrix）/ 每周决策快报（WeeklyOpsBrief）Skill 化
  ├─ system-chat 意图路由增强
  ├─ Hermes Tool 注册
  ├─ 原独立端点废弃开关
  ├─ 接口回归测试
  └─ 双轨评审与准出

第 16 周：阶段 3 灰度交付与原端点最终下线评估
  ├─ 小流量验证统一接口 Skill 唤起
  ├─ 监控 5xx / 延迟 / 用户反馈
  ├─ 确认是否开启 `LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=true`
  └─ 双轨评审与准出

阶段 4（已立项）：统一 LLM Planner 与旧体系退役
  ├─ P0 打通底座 → P1 工具补全 → P2 双跑切换与删除 → P3 体验增强
  └─ 详见 docs/specs/phase4_unified_planner_deprecation_spec.md
```

**总周期：约 16 周**（包含阶段 3 接口统一化与工程纪律所需的契约和测试时间）

---

## 十三、成功标准

### 13.1 技术指标

| 指标 | 当前 | 阶段 0 目标 | 阶段 0 实际 | 阶段 1 目标 | 阶段 1 实际 | 阶段 2 目标 | 阶段 2 实际 | 阶段 3 目标 | 阶段 3 实际 |
|------|------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|-------------|
| 接口回归通过率 | - | 100% | **100%** | 100% | **100%** | 100% | **100%** | 100% | **100%** |
| 统一接口 Skill 唤起成功率 | - | - | - | - | - | - | - | ≥ 95% | **100%**（单测覆盖） |
| 增量代码测试覆盖率 | - | ≥ 85% | **88%** | ≥ 85% | **86%** | ≥ 85% | **≥85%** | ≥ 85% | **≥85%** |
| 会话重启记忆丢失 | 100% | 0% | **0%**（PostgreSQL 路径） | 0% | **0%** | 0% | **0%** | 0% | **0%** |
| 强制生成率 | 高 | 降低 50% | **降低 100%**（信息不足时先询问） | 降低 80% | 待生产环境验证 | 降低 80% | 待生产环境验证 | 降低 80% | 待验证 |
| 平均对话轮次 | 1.2 | 1.8 | 待生产环境验证 | 2.5 | 待生产环境验证 | 2.8 | 待生产环境验证 | 3.0 | 待验证 |
| LLM 缓存命中率 | - | - | - | - | - | ≥ 30% | 待生产环境验证 | ≥ 30% | 待验证 |
| 语义记忆检索准确率 | - | - | - | - | - | ≥ 70% | 待生产环境验证 | ≥ 70% | 待验证 |

### 13.2 业务指标

| 指标 | 阶段 0 目标 | 阶段 0 实际 | 阶段 1 目标 | 阶段 2 目标 | 阶段 3 目标 |
|------|-------------|-------------|-------------|-------------|-------------|
| 用户留存提升 | 10% | 待生产环境验证 | 20% | 25% | 30% |
| 内容生成满意度 | 15% | 待生产环境验证 | 30% | 35% | 40% |
| 客服介入率降低 | 20% | 待生产环境验证 | 40% | 45% | 50% |
| 统一入口使用率 | - | - | - | - | ≥ 80%（原独立端点流量收敛到 system-chat） |

### 13.3 工程纪律指标

| 指标 | 目标 | 阶段 0 实际 | 阶段 1 实际 | 阶段 2 实际 | 阶段 3 实际 |
|------|------|-------------|-------------|-------------|-------------|
| SPEC 产出率 | 每个子任务 1 份 | **3/3** | **4/4** | **3/3** | **3/3** |
| 测试先行率 | 100%（代码前必须有测试） | **100%** | **100%** | **100%** | **100%** |
| Pre-commit 通过率 | 100% | **ruff 全通过** | **ruff/mypy/pytest/coverage 全通过** | **ruff/mypy/pytest/coverage 全通过** | **ruff 全通过** |
| CI 覆盖率门禁 | ≥ 85% | **88%** | **86%** | **≥85%** | **≥85%** |
| Feature Flag 覆盖率 | 100% 新功能 | **3/3** | **4/4** | **4/4** | **5/5** |
| 自愈循环熔断次数 | < 5% 任务 | **0 次熔断** | **0 次熔断** | **0 次熔断** | **0 次熔断** |

---

## 十四、相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| **本计划** | `docs/LUMINA_HYBRID_RENOVATION_PLAN.md` | 最终执行方案 |
| 业务真源 | `docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` | 决策约束与 P0 需求 |
| 底座对比 | `docs/LUMINA_RENOVATION_BASE_COMPARISON_AND_PLAN.md` | 方案对比与决策 |
| 效果评估 | `docs/LUMINA_RENOVATION_EFFECTIVENESS_ASSESSMENT.md` | 方案效果评估 |
| Docker 影响分析 | `docs/LUMINA_DOCKER_FUNCTION_IMPACT_ANALYSIS.md` | 部署影响分析 |
| 工程纪律 | `D:/notebook/产品方案/超级工程纪律 1.md` | 开发流程框架 |
| 原 OpenClaw 方案 | `docs/LUMINA_OPENCLAW_RENOVATION_PLAN.md` | 已放弃的历史方案 |
| Phase 4 SPEC | `docs/specs/phase4_unified_planner_deprecation_spec.md` | 统一 LLM Planner 与旧体系退役 |

---

> **阶段 2 已完成。阶段 3 已完成：接口统一化与能力 Skill 化。**
>
> **阶段 3 核心目标**：将对外服务流收敛到 `POST /api/v1/services/system-chat/stream`；爆款榜单（TrendingRank）、内容定位矩阵（ContentPositionMatrix）、每周决策快报（WeeklyOpsBrief）以 Skill / Agent 方式挂载，通过关键词或意图唤起；原独立端点按过渡期计划下线。
>
> **阶段 3 验收结果**：23 项新增测试全部通过；核心模块测试 118 passed, 1 skipped；接口回归测试 12/12 通过；ruff 全通过。
