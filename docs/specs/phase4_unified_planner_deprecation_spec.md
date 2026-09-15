# Phase 4 SPEC：统一 LLM Planner 架构与旧体系退役

> 文档版本：v1.0
> 日期：2026-07-15
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`
> 前置 SPEC：`phase1_hermes_adapter_spec.md`、`phase1_hermes_tools_spec.md`、`phase1_hermes_memory_provider_spec.md`、`phase1_hermes_security_spec.md`、`phase2_markdown_skill_spec.md`
> 状态：P0/P1/P2 已执行（2026-07-15）——Hermes 已成为唯一执行引擎，`LUMINA_USE_HERMES` 开关与 §7/§8 清单均已落地删除；P3 待启动

---

## 一、需求导入

### 1.1 背景与问题

当前聊天链路（`system_chat` → `MarketingOrchestra.process()`）本质是 **"关键词触发器 + 固定流水线 + LLM 润色话术"**，而非"LLM 理解需求 → 规划 → 编排"：

1. **意图识别是纯正则**：`apps/orchestra/src/orchestra/core.py:386-472` 的 `_classify_intent()` 为 if-elif 关键词链，无 LLM、无语义理解、无多轮上下文（`session_history` 仅用于诊断跟进一个特判）。
2. **路径强制执行**：`core.py:758-770` 的 `_should_use_agent_team()` 中 `content/topic/risk` 三类**无条件**走 Agent 团队（对比：`diagnosis/traffic` 均有上下文门槛）。
3. **组队零规划**：`kind → intent_key → intent_agent_map → SKILL_TOOL_MAP → 固定参数 builder` 四层硬编码查表（`core.py:784-792`、`agent_orchestrator.py:70-92,259,471-553`），全程无 LLM 参与。且 `agent_orchestrator.py:115` 配置路径解析错误（指向不存在的 `apps/config/agents.yaml`），恒加载内置默认配置，根目录 `config/agents.yaml` 从未生效。
4. **上下文断裂**：`select_topic` 的参数仅 `{industry, user_id, platform}`（`agent_orchestrator.py:506-510`），用户原话不传入；`industry` 恒为 `"general"`；`platform` 三层硬编码兜底为 `"xiaohongshu"`（`core.py:1458`、`agent_orchestrator.py:474`）；文本平台抽取函数 `_extract_account_info_from_input`（`core.py:642-707`）仅挂在 diagnosis 分支。
5. **占位数据外露**：未配置 `NEWSAPI_KEY` 时 `fetch_industry_news` 返回占位数据，`trend_analysis` 直接把内部兜底文案 `"需要真实数据支持"` 暴露给用户（`packages/lumina-skills/src/lumina_skills/tool_skills.py:61-76` → `content.py:371`）。
6. **已建成的多层意图引擎悬空**：`apps/intent/`（L1 规则 → L2 向量记忆 → L2.5 分类器 → L3 LLM 兜底）从未接入聊天链路，仅暴露两个调试接口。

**典型事故 case**（本 SPEC 的验收基线）：用户先说"我是一名个人创作者，我打算在抖音进行创作"，再说"我今年22岁，我的客户主要是年轻人，帮我针对年轻人进行一个最近的方向选择"——第三句因命中 `方向选择` 关键词（`core.py:451`）被强制路由到 `content_strategist` + `select_topic(industry="general", platform="xiaohongshu")`，输出了与用户平台（抖音）、人群（年轻人）完全脱节的模板化选题，并以 NLG 话术包装成"已完成分析"。

### 1.2 业务目标

| # | 目标 | 衡量标准 |
|---|---|---|
| G1 | 所有用户消息统一由 LLM planner 处理，彻底废除闲聊识别与意图分类 | 代码库中不存在任何意图关键词正则与意图→Agent 映射表 |
| G2 | 体验对齐"直接使用 Hermes Agent"：思考可见、工具调用可见、会反问、有多轮记忆 | SSE 事件流包含 thinking/tool_start/tool_complete；多轮会话不失忆；信息不足时主动澄清 |
| G3 | 工具调用参数来自对话上下文 | 用户说"抖音"则 `platform="douyin"`；说"年轻人/22岁"则体现在工具入参或生成内容中 |
| G4 | 保留并复用现有业务能力资产 | lumina-skills、orchestra/skills、RPA、methodologies 全部作为 Hermes 工具可调 |
| G5 | 安全可控 | 危险工具集黑名单生效；planner 失败降级为自然语言回复，绝不强制执行工具 |
| G6 | **接口输出格式与要求不变**（硬约束） | SSE v2 事件序列、字段结构、业务事件（`export_link`/`compliance_report`）、`done` payload、usage 统计与现行 orchestra 链路完全一致；生成内容形成 URL（export link）的能力不丢失。详见 §4.4 |

### 1.3 用户故事

- **US-1（闲聊）**：用户说"你好" → 直接自然回复，不调用任何工具。
- **US-2（咨询，信息不足）**：用户说"我想做抖音，帮我看看方向" → planner 判断缺少赛道/人群信息，通过 clarify 反问："你打算做哪个赛道？目标观众是谁？"——而不是直接执行分析。
- **US-3（执行，上下文完整）**：用户已说明"22岁个人创作者、抖音、受众年轻人"，再说"帮我选个最近的方向" → planner 调用 `lumina_recommend_topics(platform="douyin", brief="22岁个人创作者，目标受众年轻人")`，并流式展示思考与工具调用过程。
- **US-4（多步需求）**：用户说"先看看最近什么火，再帮我定三个选题" → planner 用 todo 分解为 `trending` → `select_topic` 两步串行执行。
- **US-5（多轮记忆）**：用户隔天回来问"昨天那个方向帮我想个标题" → 通过会话历史/记忆召回上下文，直接调用文案工具，不要求用户重复背景。

---

## 二、底座选型结论

### 2.1 Hermes vs OpenClaw

| 维度 | Hermes Agent | OpenClaw |
|---|---|---|
| 语言/集成方式 | Python，进程内 import | Node.js，跨语言 HTTP 桥接 |
| 项目内决策记录 | `docs/LUMINA_RENOVATION_BASE_COMPARISON_AND_PLAN.md` 选定混合方案 | `docs/LUMINA_OPENCLAW_RENOVATION_PLAN.md` 明确记载**已放弃**（跨语言桥接成本高，vendor 仅为薄壳） |
| vendor 状态 | `vendor/hermes-agent/` 空目录（待入库） | `vendor/openclaw/` 8090 个文件已从工作区删除（git HEAD 仍跟踪，本 SPEC 含清除） |
| 运行时依赖 | `LUMINA_USE_HERMES` 开关 + 适配层 743 行（`apps/api/src/services/hermes_*.py`） | 无任何运行时调用，仅剩注释/文档引用 |

### 2.2 决策

**选用 Hermes Agent（NousResearch/hermes-agent，MIT）作为唯一执行引擎。** 其原生能力直接覆盖目标架构的全部核心需求：

- LLM planner loop（`agent/conversation_loop.py` `run_conversation()`）：LLM 自主决定回复、反问或调用工具，天然同时取代"闲聊识别"与"意图分类"；
- 30+ provider（含 DeepSeek），OpenAI 兼容 function calling，原生 `stream=True` 逐 token 流式；
- 全套流式回调（`stream_delta/tool_start/tool_complete/thinking/step/status/clarify_callback`）——"过程可见"的体验基础；
- `SessionDB`（SQLite + WAL + FTS5）会话持久化 + `session_search` 跨会话回忆；
- `MemoryProvider` 可插拔记忆接口（本项目已实现 `LuminaMemoryProvider`）；
- toolset 白/黑名单机制（安全护栏）；
- 内建 `clarify`（主动追问）、`todo`（多步分解）、`delegate`（子代理）工具；
- agentskills.io 标准 skill 系统（营销方法论可按需自取，不塞 prompt）。

OpenClaw 方向不再投入，遗留物按 §8.2 清除。

---

## 三、目标架构

### 3.1 架构全景

```
用户消息
  │
  ▼
┌──────────────────────────────────────────────────────┐
│ 接入层 apps/api（SSE v2 契约保持，前端无感切换）          │
│   system_chat / debug/chat/stream                     │
│   → HermesEngineAdapter（重写，见 §5 G2-G5）            │
└──────────────────────────────────────────────────────┘
  │ run_conversation(user_message, conversation_history,
  │                  system_message=persona, stream_callbacks…)
  ▼
┌──────────────────────────────────────────────────────┐
│ 大脑层 Hermes AIAgent（唯一决策点）                      │
│   · LLM planner loop：思考 → 调工具 → 回填 → 再思考      │
│   · persona 注入：data/hermes/personas/lumina-marketing.md│
│   · 内建：clarify 反问 / todo 多步 / session_search 回忆  │
│   · 工具集白名单：lumina_marketing + 安全内建，其余禁用    │
└──────────────────────────────────────────────────────┘
  │ function calling（进程内 ToolRegistry）
  ▼
┌──────────────────────────────────────────────────────┐
│ 工具层（现有资产全部保留，仅改变被调用方式）               │
│   packages/lumina-skills（内容/诊断/流量/风控/选题）      │
│   apps/orchestra/src/orchestra/skills/                 │
│     （content_ranking / positioning_matrix /           │
│       weekly_snapshot / cross_platform）               │
│   apps/rpa（账号诊断数据获取）                           │
│   data/methodologies（AIDA/PAS/定位等方法论）            │
└──────────────────────────────────────────────────────┘
  │
  ▼
┌──────────────────────────────────────────────────────┐
│ 记忆层 Hermes SessionDB（SQLite+FTS5）                  │
│   + LuminaMemoryProvider（对接 chat_debug.memory，      │
│     用户画像/跨会话记忆）                                │
└──────────────────────────────────────────────────────┘
```

### 3.2 核心原则：单一入口，无意图分类

**所有用户消息无条件进入 Hermes planner loop。** 闲聊、澄清、单工具执行、多工具编排，全部由 LLM 在 loop 内自主决策。系统中不再存在：

- 任何意图关键词正则；
- 任何"意图种类 → 固定 Agent 团队"映射表；
- 任何按意图种类的模板回复；
- 任何独立于 LLM 的任务状态机（多步任务由 `todo` 工具 + planner loop 承担）。

### 3.3 分层职责

| 层 | 职责 | 不做的事 |
|---|---|---|
| 接入层 | SSE 事件桥接、会话标识映射、请求/响应契约 | 不做任何内容判断 |
| 大脑层 | 理解、规划、调用、回复 | 不硬编码任何业务分支 |
| 工具层 | 业务能力执行（纯函数/服务调用） | 不做意图判断，不感知对话 |
| 记忆层 | 会话持久化、用户画像、跨会话召回 | 不参与决策 |

---

## 四、输入输出边界

### 4.1 输入

沿用现有聊天请求契约（`apps/api/src/chat_debug/router.py` 与 `services/router.py`），字段不变：`message`、`conversation_id`、`user_id`、`platform`（可选）、`session_history` 等。adapter 负责：

- `conversation_id` → Hermes `session_id` 的稳定映射（同一对话复用同一 SessionDB 会话）；
- 从历史存储加载 `conversation_history` 并**真实传入** `run_conversation()`；
- 注入 persona 为 `system_message`；
- 注入 `LuminaMemoryProvider`。

### 4.2 输出（SSE v2 事件扩展）

保留现有事件：`start`、`assistant_delta`、`done`、`error`。新增事件（对齐 Hermes 回调）：

| 事件 | 来源回调 | 载荷 | 说明 |
|---|---|---|---|
| `thinking_delta` | `thinking/reasoning_callback` | `{"text": str}` | 模型思考过程流式展示 |
| `tool_start` | `tool_start_callback` | `{"tool": str, "args": dict}` | 工具调用开始（前端展示"正在调用 xxx"） |
| `tool_complete` | `tool_complete_callback` | `{"tool": str, "ok": bool, "elapsed_ms": int}` | 工具调用完成 |
| `usage` | `run_conversation` 返回 | `{"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}` | token 用量。**不单独发事件**，并入 `done` 事件的 `usage` 字段（与旧契约一致，见 §4.4） |

业务侧带事件（工具 handler 返回结构化结果，adapter 转换为对应 SSE 事件类型）：`export_link`、`compliance_report`——对齐旧链路已有事件，前端无感。

**禁止假流式**：`assistant_delta` 必须来自 `stream_delta_callback` 的真实 delta，禁止整段切块伪流（现状 `hermes_adapter.py:19-22`）。

### 4.4 接口兼容性硬约束（不可变更契约）

**现行 v2 SSE 事件序列（`apps/api/src/services/handlers/system_chat.py:103-185`）在 Hermes 路径下必须原样保持：**

```
start → assistant_delta* → export_link* → compliance_report? → done
```

| 事件 | 必须保持的字段 | 说明 |
|---|---|---|
| `start` | `service:"system-chat"`、`stream_format:2`、`request_id` | 一字不改 |
| `assistant_delta` | `text`（纯文本回复切块） | 仅文本来源从 NLG 模板变为 LLM 流式 delta |
| `export_link` | `format:"html"`、`url`、`platform`、`variant`、`title`、`summary`、`platform_required_content` | **生成内容形成 URL 的能力不可丢失**；当工具结果含 `export_urls` 时必须逐条发出（数据源从 hub_result 变为工具结果，事件格式不变） |
| `compliance_report` | `risk_level`、`risk_categories`、`violations`、`suggestion`、`format:"markdown"`、`report_md` | 工具结果含 `compliance` 时必须发出 |
| `done` | `service`、`request_id`、`full_length`、`conversation_id`、`usage`、`reply_ms`、`payload`（含 `has_content`/`content_urls`/`compliance` 追加规则） | 结构保持；`usage` 由 Hermes token 统计填充 |
| `error` | `message`（截断） | 保持 |

**约束规则**：
1. 新增事件（`thinking_delta`/`tool_start`/`tool_complete`）**只能插入**在 `start` 与 `done` 之间，不得修改、重排或删除上表任何既有事件与字段；前端不识别新事件时可安全忽略（向后兼容）。
2. 非流式接口（`POST /chat` 等）的响应 JSON 结构不变；Hermes 路径的对外行为与旧链路等价。
3. 内容生成类请求在 Hermes 路径下仍必须产出可访问的内容 URL（export link 服务继续由 `apps/api` export 模块承担，工具 handler 负责收集 `export_urls` 并交由 adapter 发事件）。
4. 双跑灰度期（P2）新旧两条路径对同一请求的 SSE 事件**种类集合**必须一致（新事件除外）。

### 4.3 行为契约（planner 判定标准）

| 场景 | 预期行为 | 反例（禁止） |
|---|---|---|
| 闲聊/问候 | 直接回复，零工具调用 | 问候后附带"为你完成分析" |
| 营销咨询但信息不足 | `clarify` 反问关键信息（平台/赛道/人群/目标） | 信息不全仍强行执行分析工具 |
| 明确执行请求 | 调用对应工具，**参数从对话上下文抽取** | 使用硬编码默认值（如 platform 恒为 xiaohongshu） |
| 多步需求 | `todo` 分解后串行/并行执行 | 只执行第一步就声称全部完成 |
| 超出营销域请求（天气/讲笑话等） | 礼貌说明服务边界 | 调用无关工具或编造回答 |
| 工具失败/超时 | 自然语言说明并给出替代建议 | 静默、伪造结果或降级为模板文案 |

---

## 五、现状缺口与修复清单

适配层骨架已在（`apps/api/src/services/hermes_adapter.py`、`hermes_tools.py`、`hermes_memory_provider.py`、`hermes_markdown_skill.py`，共 743 行 + 5 份 phase1/2 SPEC + 测试），但以下断点必须修复：

| # | 缺口 | 现状（文件:行号） | 修复内容 |
|---|---|---|---|
| G1 | **底座不在环境** | `hermes-agent/`、`vendor/hermes-agent/` 均为空目录；`import run_agent` 实测失败；`pyproject.toml:34-38` 可选依赖被注释 | hermes-agent 正式入库（决策点 D1），恢复依赖声明，CI 可构建 |
| G2 | **多轮失忆** | `hermes_adapter.py:143-148` 构建的 `conversation_history` **从未传给** `agent.chat()`；未传 `session_id` | 历史真实注入 + conversation_id→session_id 映射（phase1 adapter SPEC 已规定，落地） |
| G3 | **假流式 + 过程不可见** | `hermes_adapter.py:19-22` 按 96 字切块伪流；未接 `stream_delta_callback`；`tool_start/complete/thinking` 回调未桥接 | 真流式 + §4.2 全部新事件桥接 |
| G4 | **persona/记忆未注入** | `data/hermes/personas/lumina-marketing.md` 无代码加载；`LuminaMemoryProvider` 已测试但未注入 AIAgent | adapter 初始化时注入 persona 与 memory provider |
| G5 | **4 个工具是桩** | `hermes_tools.py` 中 diagnose / analyze_traffic / detect_risk / recommend_topics 返回 "not yet implemented in Hermes mode" | 接通 `skill_hub_client` TOOL_REGISTRY 真实实现（`select_topic`/`analyze_traffic`/`detect_risk` 等现成）；参数 schema 补充 `brief`/`platform` 等上下文字段，由 LLM 从对话抽取 |
| G6 | **业务事件缺失 + 并发隐患** | `export_link`、`compliance_report`、token 用量在 hermes 路径未实现；`asyncio.run()` 包同步 handler 的写法在并发下有隐患 | 工具侧带事件通道 + usage 事件；改造为常驻事件循环 + per-session AIAgent 实例管理 |

附带修复（工具层数据质量，独立于引擎切换也应做）：

- `tool_skills.py:61-76`：无 `NEWSAPI_KEY` 时不再向用户暴露 `"需要真实数据支持"`，改为工具结果中标记 `data_source: "placeholder"` 并由 LLM 自然说明数据局限；
- 选题/趋势类工具优先复用已有的 `fetch_trending_topics`（RPA 真实热点）替代占位新闻。

---

## 六、分阶段实施路线

### P0 — 打通底座（目标：`LUMINA_USE_HERMES=true` 体验 = 原生 Hermes） ✅ 已执行

1. G1 hermes 入库 + 依赖落地（裁剪 terminal/browser 等禁用 toolset 的依赖面）；
2. G2 历史注入 + 会话映射；G3 真流式 + 事件桥接；G4 persona/记忆注入；
3. **验收**：开"你好"→ 自然闲聊零工具；"帮我做抖音选题"→ 可见 thinking + `tool_start(lumina_recommend_topics)` + 流式回复；连续 5 轮对话不失忆；**SSE 事件序列符合 §4.4（start/done 字段与结构不变，新事件仅追加）**。

### P1 — 工具补全（目标：业务能力追平旧链路） ✅ 已执行

4. G5 四桩接通 + 参数 schema 上下文化（`brief`、`platform` 由 LLM 抽取）；
5. G6 业务事件 + usage 事件 + 并发改造；附带修复占位数据外露；
6. **验收**：诊断/选题/文案/风控四类用例在 hermes 路径全部完成；用例"明说抖音"时工具实参 `platform="douyin"` 断言通过；**内容生成用例产出 `export_link` 事件且 URL 可访问、`done.payload.has_content=true`，`compliance_report` 事件字段与 §4.4 一致**。

### P2 — 双跑灰度与切换（目标：删代码而非留开关） ✅ 已执行

7. 新旧链路双跑：同一评测会话集（§十一）双路执行，人工 + LLM 评审对比；
8. ~~默认翻转 `LUMINA_USE_HERMES=true`；观察期（建议 2 周）无 P0 级回退~~（双跑对比符合预期，用户授权直接切换，不留观察期）；
9. **执行 §7、§8 全部退役与清除**；移除 `LUMINA_USE_HERMES` 开关本身（Hermes 成为唯一路径）——已完成；
10. **验收**：`grep -rn "_classify_intent\|intent_agent_map\|SKILL_TOOL_MAP\|intent_rules" --include="*.py" --include="*.yaml"` 在活代码中零命中；全部对话只经 planner。

### P3 — 体验增强（目标：对齐并超越"直用 Hermes"）

11. 用户画像记忆调优（"22岁/抖音/受众年轻人"跨会话免重述）；`session_search` 开放；
12. 营销方法论迁移为 hermes 标准 skills（agentskills.io 格式），模型按需自取；
13. 评测集纳入 CI 回放，防行为退化；
14. **验收**：US-1~US-5 全部通过；CI 评测集通过率 100%。

---

## 七、旧体系退役清单（代码）

### 7.1 删除（P2 阶段执行）

| 对象 | 位置 | 说明 |
|---|---|---|
| 意图正则分类器及全部辅助函数 | `apps/orchestra/src/orchestra/core.py:97-472`（`_is_casual_or_greeting`、`_is_off_topic_chitchat`、`_is_clarify_feedback`、`_is_account_creation_or_howto`、`_QR_LOGIN_INTENT`、`_is_diagnosis_intent`、`_is_diagnosis_followup`、`_classify_intent` 等） | 闲聊/任务识别由 planner 承担 |
| 强制 Agent 团队判定 | `core.py:758-770` `_should_use_agent_team` | "强制走分析"根源 |
| 固定流水线分支群 | `core.py:925-1279` `run_dynamic()` 全部 `if kind == ...` 分支 | 含 topic/content/script/risk/news/cases 等固定分支 |
| 查表组队链 | `core.py:774-829` `_run_agent_team`、`core.py:784-792` `kind_to_intent`；`agent_orchestrator.py` 的 `intent_agent_map`（:259）、`SKILL_TOOL_MAP`（:70-92）、`_build_params_for_tool`（:471-553） | Agent/工具/参数选择由 LLM 完成 |
| 模板 NLG | `apps/orchestra/src/orchestra/nlg.py` 全文件 | 回复由 LLM 生成 |
| 任务状态机 | `apps/orchestra/src/orchestra/task_state.py` 全文件 + `core.py:1524` 集成点 | 多步任务由 `todo` 工具承担；**PostgreSQL 表保留不删**，代码停止读写 |
| 意图护栏 | `apps/orchestra/src/orchestra/intent_guards.py` | 随意图体系一并退役 |
| 独立意图引擎 | `apps/intent/` 整个应用 + `apps/api/src/api/intent_router.py`（`/intent/recognize`、`/intent/clarify` 调试接口） | 从未接入聊天链路，整体删除 |
| 意图规则配置 | `config/intent_rules.yaml` | 随 `apps/intent` 删除 |
| Agent 组队配置 | `config/agents.yaml`（`intent_agent_map`、`execution_modes` 及 13 个 agent 定义） | Hermes 不消费此文件；agent 角色能力改写为工具描述/persona 的一部分 |
| 旧链路入口 | `MarketingOrchestra.process()` 聊天处理职责 + `services/handlers/system_chat.py` 中 `marketing_orchestra_process` 调用 | 保留 `orchestra/skills/` 下的纯 skill 函数供工具层复用 |
| 双引擎开关 | `.env` / `.env.example` / `docker-compose*.yml` 中 `LUMINA_USE_HERMES` | P2 完成、旧链路删除后移除开关 |
| 随组件失效的测试 | `tests/intent/`、`tests/orchestra/`、`tests/integration/test_end_to_end.py::test_openclaw_to_intent` 等 | 删除或改写为 planner 行为测试 |

### 7.2 保留（工具层资产，仅改变被调用方式）

- `packages/lumina-skills/`（`content.py` `select_topic`/`generate_text`/`generate_script`、`diagnosis.py`、`tool_skills.py` 等）——包装为 Hermes 工具；
- `apps/orchestra/src/orchestra/skills/`（content_ranking / positioning_matrix / weekly_snapshot / cross_platform）——已接通 4 个，保持；
- `apps/rpa/`（账号诊断、热点抓取）——作为工具数据源；
- `packages/skill-hub-client/`、`apps/skill-hub/`——工具注册中心，P3 再评估是否演进为 MCP 统一；
- `packages/llm-hub/`——模型客户端基础设施；
- `data/methodologies/`——方法论库，P3 迁移为 hermes skills 格式；
- `apps/api` 的 SSE 接入层、`chat_debug.memory`（被 `LuminaMemoryProvider` 依赖）。

### 7.3 `skills/` 下 MCP server 的处理

`skills/skill-*/`（13 个 MCP server 形态实现）当前**未接入任何运行链路**（hermes 工具走的是进程内 import，skill-hub 走 TOOL_REGISTRY）。处理：P2 阶段逐一核对，未被 skill-hub 注册且无调用方的归档至 `archive/` 或删除；其中纯模板脚手架实现（如 `skill-community-manager` 的 if/elif 固定回复、`skill-growth-hacker` 的查表 ROI）优先清除。

---

## 八、无用内容清除清单（仓库卫生）

### 8.1 随旧体系删除（P2 同步执行）

- `packages/mcp-bridge/`：OpenClaw 插件桥接（`index.js`、`intent-aware-bridge.js`），OpenClaw 已放弃且无运行时调用方；
- `scripts/test_*.py` 中针对旧链路的手工测试脚本（`test_diagnosis_flow.py`、`test_direct_diagnosis*.py`、`test_export_link_*.py` 等）：逐一核对，有价值场景改写为 planner 评测用例，其余删除；
- 代码中指向已删组件的注释引用：`core.py:116`（intent-gate.ts 同步注释）、`orchestra/router.py:1` docstring（OpenClaw hub 说明）。

### 8.2 OpenClaw 遗留清除（可立即执行，独立于 P0-P3）

- `vendor/openclaw/`：工作区已删除但 git HEAD 仍跟踪 8090 个文件 → 提交该删除，使仓库状态干净；
- `.env.example:1,10` 的 OpenClaw 桥接注释、`docker-compose*.yml` 中残留引用 → 清理；
- `README.md` 及文档中的 OpenClaw 架构描述 → 按 §九联动更新；
- **保留不动**：`docs/LUMINA_OPENCLAW_RENOVATION_PLAN.md` 等历史决策文档（仅文首加指针，不改写历史）。

### 8.3 hermes 挂载占位清理

- `hermes-agent/`（根目录空目录）、`vendor/hermes-agent/`（空目录 + docker-compose 挂载）：按决策点 D1 选定入库方式后，或填入真身（vendor 拷贝钉版本），或删除占位改为 pip 依赖，二者不留空壳。

### 8.4 待拍板（不默认执行）

- 根目录 AI 咨询记录 `chatgpt.txt` / `deepseek.txt` / `gemini.txt` / `tongyi.txt`：建议归档至 `docs/consulting/`，是否删除由所有者决定；
- `docs/` 下 5 篇 PHASE 完成报告：保留为历史档案（仅加指针），不删除。

---

## 九、文档联动更新清单

随本 SPEC 一并执行（✅ = 本次已完成）：

| 文档 | 更新方式 | 状态 |
|---|---|---|
| `docs/CORE_ARCHITECTURE.md` | §4.2 改写为 Hermes planner 单入口；§6.1/§7.1 删除 intent_rules.yaml / intent_agent_map 扩展指引；文首加过渡声明 | ✅ |
| `README.md` | L7 简介、Layer1/2 架构描述、结构树（移除 apps/intent、nlg.py、intent_rules.yaml）、"添加新 Agent"改为"注册 Hermes Tool" | ✅ |
| `docs/LUMINA_HYBRID_RENOVATION_PLAN.md` | §4.1/4.2 加"Hermes 为唯一引擎"目标态注记；§6.3.3、§9.3.2 标已退役；新增阶段 4 小节指向本 SPEC；修正头尾状态不一致 | ✅ |
| `docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` | §8.2 技术栈表：意图分类标"已退役"、Hermes 改为"主执行引擎"；决策 1 追加指针。**不动 §5.2 业务需求条目** | ✅ |
| `docs/ARCHITECTURE.md` | 版本信息加弃用指针 | ✅ |
| `docs/Content.md`、`docs/API_SERVICES_INTEGRATION.md`、`docs/CROSS_PLATFORM_CONTENT_GENERATION.md`、`docs/LOCAL_DEVELOPMENT.md`、`docs/DOCKER_DEPLOYMENT.md` | 时序图/描述句/配置挂载/验证命令改为新链路描述 | ✅ |
| `docs/specs/phase0_task_state_spec.md`、`docs/specs/phase3_skill_intent_routing_spec.md` | 文首加弃用声明（后者 Hermes Tool 注册部分标注仍有效） | ✅ |
| `PHASE2/PHASE3_COMPLETION_REPORT.md`、`LUMINA_RENOVATION_BASE_COMPARISON_AND_PLAN.md`、`LUMINA_RENOVATION_EFFECTIVENESS_ASSESSMENT.md`、`LUMINA_DOCKER_FUNCTION_IMPACT_ANALYSIS.md`、`DEMO_WORKBENCH_REQUIREMENTS.md` | 文首加历史指针，内容不改写 | ✅ |

---

## 十、护栏设计

1. **工具白名单**：沿用 `data/hermes/config.yaml`，禁用 terminal / browser / code_execution / cron 等危险 toolset；仅暴露 `lumina_marketing` + 安全内建（clarify / todo / session_search）——LLM 幻觉调不出危险能力。
2. **失败降级**：LLM 超时/工具异常 → 自然语言致歉与建议；**绝不降级为强制执行某工具**（不重蹈"强制分析"覆辙）。
3. **可观测**：每次会话落盘规划轨迹（思考、工具调用、参数、结果、耗时），可回放、可评测——替代原 `intent.kind` 的调试价值。
4. **成本/延迟**：主模型沿用 DeepSeek；短会话裁剪工具目录（toolset 机制原生支持）；高频相同请求可后续加规划结果缓存。
5. **并发安全**：常驻事件循环 + per-session AIAgent 实例；禁止 `asyncio.run()` 包同步 handler。
6. **数据诚实**：工具返回占位/兜底数据时必须结构化标记，禁止以 LLM 话术包装成"真实分析结果"（对应 §五附带修复）。

---

## 十一、评测与回归

建立固定评测会话集（P2 双跑对比与 P3 CI 回放共用），至少覆盖：

| # | 用例 | 预期 |
|---|---|---|
| E1 | "你好" | 零工具调用，自然回复 |
| E2 | "我是一名个人创作者，我打算在抖音进行创作" | 零工具调用，回应并引导补充信息 |
| E3 | （承接 E2）"我今年22岁，客户主要是年轻人，帮我选个最近的方向" | 调用选题工具且参数含 `platform="douyin"` 与人群描述；或先 clarify |
| E4 | "帮我诊断下这个账号"（无 URL/凭证） | clarify 索要账号信息，不强行执行 |
| E5 | "先看看最近什么火，再定三个选题" | todo 分解为两步，按序执行 |
| E6 | "今天天气怎么样" | 礼貌说明服务边界，零工具调用 |
| E7 | 隔天追问"昨天那个方向帮我想个标题" | 召回上下文，直接执行文案生成 |
| E8 | "帮我生成一篇小红书笔记" | 产出 `export_link` 事件（URL 可访问）+ `done` 含 `usage` 与 `payload.has_content=true`，事件序列符合 §4.4 |

行为断言基于 §4.3 行为契约；工具实参断言（如 `platform`）替代旧的意图标签断言。

---

## 十二、决策点（待拍板）

| # | 决策 | 选项 | 建议 |
|---|---|---|---|
| D1 | hermes 入库方式 | git submodule / vendor 拷贝钉版本 / pip 包 | **vendor 拷贝钉版本**（仓库已有 vendor/ 惯例，CI 最稳） |
| D2 | 工具集成方式 | 进程内 ToolRegistry / MCP 统一 | **P0-P2 进程内**，P3 评估 MCP |
| D3 | 旧链路切换节奏 | 直接切换 / 双跑灰度 | **双跑 2 周 + 评测集对比**，再删旧代码 |
| D4 | 主模型 | DeepSeek / Claude / 其他 | DeepSeek 起步，persona 调温度；关键评测不过再升级 |
| D5 | 咨询 txt 与历史报告处理 | 归档 / 删除 / 不动 | 归档 `docs/consulting/`，报告不动 |

---

## 十三、风险与缓解

| 风险 | 等级 | 缓解 |
|---|---|---|
| planner 行为不确定导致体验回退（误判闲聊/误判执行） | 高 | §十一评测集双跑对比后才切换；clarify 优先于强制执行写进 persona；失败降级为回复 |
| hermes 体积/依赖膨胀 | 中 | 裁剪禁用 toolset 依赖；冷启动基准纳入验收 |
| 工具桩接通后暴露 skill 数据质量问题（占位新闻等） | 中 | §五附带修复先行；工具结果结构化标记数据来源 |
| 删除旧体系破坏未发现的调用方 | 中 | P2 删除前全仓 grep 调用方 + 完整测试套件通过；分批删除（先入口后内部） |
| 多轮历史注入导致 token 成本上升 | 低 | hermes 自带上下文压缩（`context_compressor.py`）；监控 usage 事件 |

---

## 十四、相关文档

- 业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`（§8.2 技术栈随本 SPEC 更新）
- 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`（新增阶段 4 指向本 SPEC）
- 前置 SPEC：`docs/specs/phase1_hermes_*.md`、`docs/specs/phase2_markdown_skill_spec.md`
- 底座选型：`docs/LUMINA_RENOVATION_BASE_COMPARISON_AND_PLAN.md`（历史决策：混合方案；本 SPEC 将其推进为"Hermes 唯一引擎"）
- 被本 SPEC 取代：`docs/specs/phase0_task_state_spec.md`、`docs/specs/phase3_skill_intent_routing_spec.md`（§5 Orchestra 集成部分）
