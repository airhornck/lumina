# Lumina 现行架构梳理（as-built）

> 文档版本：v1.0
> 核对日期：2026-09-07（依据工作区代码 + git HEAD 逐模块核对）
> 定位：本文件是 **Lumina 当前（as-built）架构的唯一入口**，README 顶部架构图为历史快照。
> 依据：`docs/specs/phase4_unified_planner_deprecation_spec.md`、`.cursorrules`、`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`

---

## 1. 定位与核心模式

Lumina 是面向个人创作者 / KOL 的**对话式 AI 营销智能助手平台**：用户以自然语言表达营销诉求（账号诊断、流量分析、内容/脚本生成、选题推荐、合规预检、内容定位矩阵、爆款榜单、每周决策快照等），系统以 **Hermes LLM Agent 为唯一执行引擎** 自主决策（回复 / 反问澄清 / 工具调用 / todo 多步分解），并通过 **SSE v2 事件契约** 向前端实时暴露思考与工具调用过程。

核心原则（Phase 4 SPEC §3.2）：**单一入口、无意图分类**——所有用户消息无条件进入 Hermes planner loop，系统中不再存在意图关键词正则、意图→Agent 映射表、模板回复与独立任务状态机。

技术形态：Python 3.11+ / FastAPI / FastMCP / asyncpg(PostgreSQL+pgvector) / LiteLLM / Playwright / Pydantic v2。

---

## 2. 架构演进简史（为什么代码库是现在的样子）

| 阶段 | 架构 | 状态 |
|---|---|---|
| 初版 | OpenClaw(Node.js) Layer1 + 四层架构 | ❌ 已放弃（vendor 已删除，见 `docs/LUMINA_OPENCLAW_RENOVATION_PLAN.md`） |
| v2~v3 | `MarketingOrchestra` + `AgentOrchestrator`（意图正则分类、14 Agent、PARALLEL/SERIAL/MIXED 硬编码组队） | ❌ 已退役（核心文件已随 Phase 4 P2 删除） |
| **Phase 4（现行）** | **Hermes LLM planner 统一编排**，业务能力全部注册为 Hermes Tool | ✅ 现行链路（P0/P1/P2 已执行，P3 待启动） |

关键决策依据：
- 底座选型：NousResearch **Hermes Agent**（Python 进程内集成）取代 OpenClaw（Node 跨语言桥接），见 `docs/LUMINA_RENOVATION_BASE_COMPARISON_AND_PLAN.md`；
- 阶段规格：`docs/specs/phase0_*`（记忆/渐进式生成/任务状态）→ `phase1_hermes_*`（adapter/tools/security/memory_provider）→ `phase2_*`（成本/向量记忆/Markdown skill）→ `phase3_*`（统一接口/技能路由/三大 skill）→ `phase4_unified_planner_deprecation_spec.md`；
- 工程红线：`.cursorrules`（宪法级规范，禁止绕过 llm_hub、危险 toolset 黑名单、接口稳定性）。

---

## 3. 分层架构全景（现行）

```
用户消息 (HTTP POST + SSE)
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ L1 接入层  apps/api  FastAPI 宿主（apps/api/src/api/main.py）      │
│   · POST /api/v1/services/system-chat/stream   ← 唯一服务流入口   │
│     （cross-platform-content 保留；content-ranking/positioning/   │
│       weekly-snapshot 已下线返回 410）                            │
│   · /skill、/api/v1/demo、/api/v1/usage、/api/v1/exports          │
│   · /api/v1/debug（调试 chat / 记忆 / 对话日志）+ /debug/chat UI    │
│   · /mcp：FastMCP Skill Hub（streamable-http，同进程挂载）         │
│   · 启动：uvicorn api.main:app --app-dir apps/api/src（端口 8000） │
└──────────────────────────────────────────────────────────────────┘
   │ services/handlers/system_chat.py：记忆读写 / 指代补全 /
   │  画像更新 / 平台解析（画像>显式>当前消息>历史）
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ L2 大脑层  HermesEngineAdapter（services/hermes_adapter.py）        │
│   · vendor/hermes-agent（Hermes 0.16.0，钉版 vendor）的 AIAgent：   │
│     LLM planner loop —— 思考 → 反问(clarify)/todo 分解 → 工具调用 → │
│     回填 → 再思考                                                 │
│   · persona 注入：data/hermes/personas/lumina-marketing.md          │
│   · 同步线程 → asyncio 事件桥接（_EventBridge）：                   │
│     thinking/tool_start/tool_complete/assistant 流式 delta         │
│     实时转 SSE（禁止假流式；思考标签增量过滤）                     │
│   · agent 按 (user_id, conversation_id) 缓存复用；工具全局注册一次 │
│   · 记忆：注入 LuminaMemoryProvider（同步写由 router/adapter 负责）│
│   · 快路径：关键词直连（查爆款榜单/内容定位矩阵/生成本周快报）       │
│     跳过 planner，直接调用对应 skill（只确定调谁，不裁剪上下文）    │
└──────────────────────────────────────────────────────────────────┘
   │ function calling（进程内 ToolRegistry，lumina_marketing 工具集）
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ L3 工具层（历史业务资产全部复用，仅改变被调用方式）                 │
│   · services/hermes_tools.py：9 个 lumina_* 工具（schema+handler） │
│     分发、平台一致性守卫、请求上下文透传（并发安全）               │
│   · services/content_engine/：跨平台内容生成管线                    │
│     （主稿 master_generator → 平台适配 platform_adaptor →          │
│       合规扫描 compliance_scanner → HTML 导出 export/storage）     │
│   · packages/lumina-skills TOOL_REGISTRY：13 个原子 Skill           │
│     （诊断/流量/风控/文案/脚本/选题/方法论/案例/问答/行业资讯/       │
│       竞品监控/数据可视化/热点）                                   │
│   · apps/orchestra/src/orchestra/skills/：content_ranking /         │
│     positioning_matrix / weekly_snapshot（旧 Layer2 工具化产物）   │
│   · apps/rpa：Playwright 浏览器自动化（扫码登录/账号抓取/会话管理） │
│   · 双库真源：data/platforms/*.yml + data/methodologies/*.yml       │
└──────────────────────────────────────────────────────────────────┘
   │ llm_hub（唯一 LLM 入口，宪法红线） / knowledge-base / 平台 RPA
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ L4 数据 / 记忆层                                                    │
│   · PostgreSQL（asyncpg 连接池，apps/api/src/infra/db.py）：         │
│     chat 消息记忆（CHAT_MEMORY_BACKEND=postgres 默认）、             │
│     用户画像、llm_usage_logs 用量表（infra/sql/init.sql 建表）      │
│   · Hermes 侧：SessionDB（SQLite+FTS5）+ Session 文件                │
│   · 对话审计：data/logs/chat/chat-YYYY-MM-DD.jsonl（每轮一条，       │
│     LUMINA_CHAT_LOG_DIR 可覆盖，含敏感内容仅限私有部署）            │
│   · 内容导出物：static/content/*.html（HTTP 静态可访问链接）         │
└──────────────────────────────────────────────────────────────────┘
```

分层职责（Phase 4 SPEC §3.3）：

| 层 | 职责 | 不做的事 |
|---|---|---|
| 接入层 | SSE 事件桥接、会话标识映射、请求/响应契约 | 不做任何内容判断 |
| 大脑层（Hermes planner） | 理解、规划、调用、回复 | 不硬编码业务分支 |
| 工具层 | 业务能力执行（纯函数/服务调用） | 不做意图判断、不感知对话 |
| 记忆层 | 会话持久化、用户画像、跨会话召回 | 不参与决策 |

---

## 4. 目录地图与模块职责

```
apps/
├── api/src/                    ← FastAPI 主进程（唯一服务，v0.4.0）
│   ├── api/main.py             FastAPI 入口：DB/用量/LLM Hub 生命周期、路由挂载、
│   │                           /mcp Skill Hub、静态目录（/debug/chat /sdk /static/content）
│   ├── api/{skill,demo,usage,export}_router.py   四组能力路由
│   ├── services/               核心业务编排
│   │   ├── handlers/system_chat.py               统一服务流处理器（Hermes 唯一链路）
│   │   ├── handlers/cross_platform_content.py    跨平台内容处理器（保留的非核心服务）
│   │   ├── hermes_adapter.py    ★ Hermes 引擎桥接（真流式 SSE + 事件契约）
│   │   ├── hermes_tools.py      ★ 9 个 lumina_* 工具定义 + 分发/平台守卫/上下文透传
│   │   ├── hermes_security.py   安全配置（危险 toolset 黑名单、私有 URL 禁访）
│   │   ├── hermes_memory_provider.py   LuminaMemoryProvider（Hermes↔Lumina 记忆桥）
│   │   ├── hermes_markdown_skill.py   方法论执行 → Markdown 产出（lumina_execute_methodology）
│   │   ├── content_engine/      跨平台内容管线（master/adaptor/compliance/export/…）
│   │   ├── conversation_profile_service.py   用户画像（平台/领域抽取、注入 system prompt）
│   │   ├── intent_completion.py 短消息指代补全（仅启发式补全，非意图路由）
│   │   ├── conversation_log.py  对话审计 JSONL
│   │   ├── usage_service.py     llm_usage_logs 读写
│   │   └── platform_utils.py    平台别名归一化 / 多平台意图检测
│   ├── chat_debug/             debug 对话 / 记忆 / 向量记忆 / 日志查询（调试工作台后端）
│   ├── infra/db.py             asyncpg 连接池
│   └── prompts/                内容相关静态提示词（master_content/platform_adapt/…）
├── orchestra/src/orchestra/    ← 旧 Layer2 残留：skills/（content_ranking、
│                                 positioning_matrix、weekly_snapshot 及内部
│                                 trending_rank/content_position_matrix 子包）被 Hermes 工具化复用；
│                                 task_state/intent_guards 等旧模块保留未删
├── skill-hub/src/skill_hub_app/  FastMCP Skill Hub（复用同一 TOOL_REGISTRY）
└── rpa/src/rpa/                Playwright RPA（account_crawler / qrcode_login /
                                session_manager / browser_grid / proxy_manager / anti_detection）

packages/
├── lumina-skills/src/lumina_skills/   13 个原子 Skill 实现
│   ├── diagnosis.py  content.py  assets.py  tool_skills.py
│   └── registry.py（TOOL_REGISTRY）+ methodology_utils.py
├── llm-hub/src/llm_hub/       LLM 池唯一入口
│   └── hub/client/loader/config_models/cost_optimizer/stream_usage/usage_reporter
├── knowledge-base/src/knowledge_base/  PlatformRegistry / MethodologyRegistry
├── sop-engine/src/sop_engine/ 历史遗留：SOP DAG 编译器（旧方法论编排）
├── skill-hub-client/          同进程直连 TOOL_REGISTRY 的调用封装（非 HTTP）
└── agent-core/                历史遗留：旧 Agent 基类

vendor/hermes-agent/           ★ Hermes Agent 0.16.0 全量源码 vendor 钉版
                               （运行时由 hermes_adapter 追加 sys.path 加载；
                                 禁止本地修改，升级=整体重拷+LUMINA_PIN.md 更新）

config/、infra/config/llm.yaml   LLM 池配置（llm_pool + default_llm + skill_config）
infra/sql/init.sql               Postgres DDL（users/sessions/messages/llm_usage_logs…）
data/
├── platforms/                 平台规范 YAML（xiaohongshu/douyin/bilibili/wechat_official）
├── methodologies/             方法论 YAML（11 套：AIDA/PAS/定位/StoryArc/TrendRide/…）
├── hermes/                    HERMES_HOME：config.yaml、personas/lumina-marketing.md、
│                              sessions/memories/skills 等运行时目录
├── credentials/  sessions/   平台凭证与会话（data/sessions/*.json）
└── logs/chat/                对话审计 JSONL
static/                        debug_chat UI、sdk（luminaChatClient.js）、content 导出物
docs/  tests/  scripts/
```

> 注：顶层 `hermes-agent/` 为遗留空目录（真实代码在 `vendor/hermes-agent/`）。

---

## 5. 请求生命周期（system-chat）

以"帮我看看最近适合做什么方向"为例：

1. `POST /api/v1/services/system-chat/stream` → `services/router.py` 校验 service 白名单 → `handlers/system_chat.py`；
2. 读该 `(user_id, conversation_id)` 最近 24 条记忆 → 落 user 轮 → 短消息指代补全（`intent_completion.py`）→ 画像抽取/更新 → 平台解析（优先级：画像 > 显式 > 当前消息 > 历史，变更检测）；
3. `HermesEngineAdapter.chat_stream()`：
   - 关键词直连命中（查爆款榜单/内容定位矩阵/生成本周快报）→ 跳过 planner 直接调 skill；
   - 否则取/建 `AIAgent`（按 user_id+conversation_id 缓存；工具集 `lumina_marketing` + 安全内建，进程内注册一次）→ 工作线程执行 `run_conversation()`，回调经 `_EventBridge` 桥回事件循环；
4. LLM planner 决策 → function calling 调 `lumina_*` 工具 → `hermes_tools` 平台对齐守卫 → SkillHub/ContentEngine/Orchestra skill 执行；
5. 前端收到 SSE 事件序列；
6. assistant 轮写记忆；对话审计落一条 JSONL（path=planner|keyword|mock）。

### SSE v2 事件契约（对外稳定协议，.cursorrules §4.2）

```
start → thinking_delta* / tool_start* / tool_complete* / assistant_delta*
      → export_link* / compliance_report?
      → done { full_length, conversation_id, usage, reply_ms, payload }
error 事件用于失败降级（自然语言致歉，绝不强制再执行工具）
```

### 确定性快路径

`KEYWORD_TOOL_TRIGGERS`（hermes_tools.py）：

| 关键词 | 直连工具 | 后端 |
|---|---|---|
| 查爆款榜单 | `lumina_content_ranking` | orchestra content_ranking_skill |
| 内容定位矩阵 | `lumina_positioning_matrix` | orchestra positioning_matrix_skill |
| 生成本周快报 | `lumina_weekly_snapshot` | orchestra weekly_snapshot_skill |

---

## 6. HTTP API 端点面

| 前缀 | 端点 | 用途 |
|---|---|---|
| `/health` | GET | 健康检查（含 llm_hub/db/mcp 状态） |
| `/docs` `/redoc` `/openapi.json` | — | 自动文档 |
| `/api/v1/services/{service}/stream` | POST | 服务流式对话（system-chat / cross-platform-content） |
| `/api/v1/services/{service}/memory` | GET/DELETE | 服务对话记忆查询/清除 |
| `/api/v1/debug/chat/*` | GET/POST | 调试对话流、capabilities、记忆、chat-logs |
| `/skill/execute` `/skill/list` | POST/GET | 直接执行/列出 Skill |
| `/api/v1/demo/position-matrix` `/weekly-rankings` | GET | Demo 工作台数据 |
| `/api/v1/usage/stats|summary|daily` | GET | Token 用量统计 |
| `/api/v1/exports/{export_id}` | GET | 导出 HTML 页面 |
| `/mcp` | POST(SSE-HTTP) | FastMCP Skill Hub（13 个原子 Skill，streamable-http） |
| `/debug/chat` `/sdk` `/static/content` | 静态 | 调试 UI / 前端 SDK / 内容导出物 |

已下线：`content-ranking`、`positioning`、`weekly-snapshot` 服务流 → 410 Gone（收敛到 system-chat）。

---

## 7. 能力与工具全景

### 7.1 Hermes 工具（9 个，lumina_marketing 工具集）

| 工具 | 后端实现 | 备注 |
|---|---|---|
| `lumina_generate_content` | services/content_engine（CrossPlatformEngine） | 产出可访问 HTML 链接 → export_link 事件 |
| `lumina_diagnose_account` | SkillHub `diagnose_account`（可联动 apps/rpa 抓取） | |
| `lumina_analyze_traffic` | SkillHub `analyze_traffic` | |
| `lumina_detect_risk` | SkillHub `detect_risk` | 映射 compliance → compliance_report 事件 |
| `lumina_recommend_topics` | SkillHub `select_topic`（LLM 选题推荐） | |
| `lumina_execute_methodology` | hermes_markdown_skill（方法论执行→Markdown） | |
| `lumina_content_ranking` | orchestra content_ranking_skill | 关键词直连候选 |
| `lumina_positioning_matrix` | orchestra positioning_matrix_skill | 关键词直连候选 |
| `lumina_weekly_snapshot` | orchestra weekly_snapshot_skill | 关键词直连候选 |

### 7.2 Skill Hub 原子 Skill（13 个，packages/lumina-skills）

诊断：`diagnose_account / analyze_traffic / detect_risk`
内容：`generate_text / generate_script / select_topic`
资产：`retrieve_methodology / match_cases / qa_knowledge`
工具：`fetch_industry_news / monitor_competitor / visualize_data / fetch_trending_topics`

### 7.3 内容生成管线（services/content_engine）

`CrossPlatformEngine`（主稿生成 master_generator → 平台适配 platform_adaptor → 合规扫描 compliance_scanner → HTML 渲染/导出 export_service/storage → 资源上传 resource_uploader），下游 LLM 统一走 llm_hub，规范读取 PlatformRegistry / MethodologyRegistry。

### 7.4 双知识真源（YAML 即配置）

- `data/platforms/*.yml`：xiaohongshu / douyin / bilibili / wechat_official —— content_dna、audit_rules（合规）、content_formats（长度/格式约束）；
- `data/methodologies/*.yml`：AIDA、AIDA-Advanced、PAS、定位、StoryArc、TrendRide、HookStoryOffer、BigIdea、WhatWhyHow、HoshinKanri 等 11 套，含 steps + prompt_templates；
- 统一读取：`packages/knowledge-base`（PlatformRegistry / MethodologyRegistry）。

### 7.5 LLM 层（llm-hub，唯一入口）

配置 `infra/config/llm.yaml`：llm_pool（deepseek-v3 默认 / gpt-4o-mini / claude-sonnet）+ default_strategy（cost_aware）+ skill_config（skill→模型分配）；`set_usage_reporter` 将 token 用量上报 `llm_usage_logs`。Hermes 主模型经 `LUMINA_HERMES_PROVIDER/MODEL` 环境变量（默认 deepseek / `deepseek-v4-flash` 见 docker-compose），API key 取 `DEEPSEEK_API_KEY`，缺省回退 `data/hermes/config.yaml` 的 lumina.fallback_api_key。

---

## 8. 数据 / 记忆拓扑

| 数据 | 存储 | 说明 |
|---|---|---|
| 对话消息记忆 | PostgreSQL（默认，`CHAT_MEMORY_BACKEND=postgres`）| chat_debug/PostgresChatMemoryStore，按 (user, conversation, service) 隔离 |
| Hermes 会话 | SessionDB（SQLite+FTS5）+ HERMES_HOME=data/hermes | 由 vendor Hermes 管理 |
| 用户画像 | PostgreSQL（conversation profile）| 平台/领域抽取，注入 system prompt |
| Token 用量 | PostgreSQL `llm_usage_logs` | llm_hub usage_reporter → usage_service |
| 对话审计 | `data/logs/chat/chat-*.jsonl` | 每轮一条，含意图/工具调用证据 |
| 内容导出 | `static/content/*.html` | 通过 /static/content 静态可访问 |
| 平台凭证/会话 | `data/credentials`、`data/sessions/*.json` | RPA 扫码登录维护 |

---

## 9. 配置与运行

### 环境变量（关键）

| 变量 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | LLM 密钥 |
| `LLM_CONFIG_PATH` | llm.yaml 路径（默认 infra/config/llm.yaml） |
| `DATABASE_URL` | Postgres 连接串（缺省则无 DB 持久化降级运行） |
| `CHAT_MEMORY_BACKEND` | postgres / json（默认 postgres） |
| `LUMINA_HERMES_PROVIDER` / `LUMINA_HERMES_MODEL` | Hermes 引擎 provider/model |
| `LUMINA_CHAT_LOG_DIR` | 对话日志目录覆盖 |
| `PORT` | uvicorn 端口（默认 8000） |

### 本地 / Docker

- 本地：`pip install -e ".[dev]"` → `python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api/src`；
- Docker：`docker compose -f docker-compose.local.yml up --build`（postgres pgvector:pg16 + lumina-api 热重载，vendor 与 data/hermes 卷挂载）；
- 部署细节见 `docs/PRODUCTION_DEPLOYMENT.md`、`docs/DOCKER_DEPLOYMENT.md`。

---

## 10. 现状注意点与待办（核对时发现）

1. **README 滞后**：顶部架构图 / 项目结构 / 快速开始仍描述 Orchestra 时代内容（含已删的 `apps/intent`、`skills/skill-*`、`AgentOrchestrator`），现行以本文件 + Phase 4 SPEC 为准。
2. **历史遗留仍在库**：`packages/sop-engine`、`packages/agent-core`、`apps/orchestra` 的 `task_state/intent_guards` 等旧模块、`chat_debug` 旧 LLM 直连路径——无引用但未删（有回归风险，需按 Phase 4 P3 清理计划处理）。
3. **仓库卫生**：根目录存有十余个数百 MB 的 `lumina*.tar` 镜像包与大量调试产物（`pytest_*.txt`、`*_sse.txt`、`chatgpt.txt` 等），建议移出仓库/入 .gitignore。
4. **敏感信息**：`infra/config/llm.yaml`、`data/hermes/config.yaml` 含明文 fallback API key（镜像私有部署用），勿推送公开仓库；建议改注入式密钥。
5. **并发链路注意**：Hermes 工具调用并发执行于同一事件循环线程，请求上下文经显式参数透传而非 threading.local（hermes_tools 设计约束，改动需谨慎）。

---

## 11. 相关文档

- 阶段总纲：`docs/specs/phase4_unified_planner_deprecation_spec.md`（现行架构 SPEC，含 SSE 契约）
- 工程宪法：`.cursorrules`
- 业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`
- 对外服务 API：`docs/API_SERVICES_INTEGRATION.md`（v2.0）、`docs/CONVERSATION_HISTORY_API*.md`
- 部署：`docs/PRODUCTION_DEPLOYMENT.md`、`docs/DOCKER_DEPLOYMENT.md`
- 各阶段完成报告：`docs/PHASE2_COMPLETION_REPORT.md`、`docs/PHASE3_COMPLETION_REPORT.md`（Phase 4 报告未生成）
- Hermes vendor 钉版说明：`vendor/hermes-agent/LUMINA_PIN.md`
