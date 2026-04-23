# Lumina - AI 营销助手

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Lumina 是一个面向小红书、抖音、B站等内容平台的 AI 营销助手，采用**四层架构 + 双库驱动 + 多 Agent 编排**设计（OpenClaw 基座 → 多 Agent 中枢 → MCP Skill Hub → 平台规范库/方法论库），提供账号诊断、流量分析、内容生成、选题策略、合规预检、SOP 编排等核心能力。

**核心升级**：
- **Agent 编排层**：`AgentOrchestrator` 支持 PARALLEL/SERIAL/MIXED 三种执行模式，14 个 Agent 根据意图自动组队协作
- **动态 Skill 映射**：同一 Skill 在不同意图下自动路由到不同 Tool（如 `skill-data-analyst` 在 diagnosis 时调用 `diagnose_account`，在 traffic_analysis 时调用 `analyze_traffic`）
- **全链路 LLM 集成**：内容生成、脚本创作、选题推荐、案例匹配、知识问答均已接入 LLM，支持 DeepSeek/OpenAI/Anthropic 多模型切换
- **端到端测试覆盖**：17 个集成测试验证 Agent → Skill → LLM 完整调用链路

---

## 核心特性

| 能力域 | 特性说明 |
|--------|----------|
| **多 Agent 编排** | 14 个 Agent 自动组队，支持并行（诊断+策略同步执行）、串行（生成→审查流水线）、混合（矩阵搭建）三种模式 |
| **账号基因诊断** | 基于 RPA 真实数据抓取，分析账号定位、内容 DNA、健康度评分 |
| **流量结构分析** | 曝光/互动/转化漏斗分析，结合平台规范给出可落地的优化建议 |
| **内容智能生成** | 文案、标题、短视频脚本均自动匹配 AIDA/StoryArc/PAS/HookStoryOffer 等方法论框架 |
| **选题方向建议** | 动态轮换真实存在的方法论，结合热点新闻与平台审核规则生成内容日历 |
| **平台规范检查** | 自动读取 `data/platforms/*.yml` 的 `audit_rules` 和 `content_formats` 做实时预检 |
| **方法论 SOP** | 8 套可配置营销框架（AIDA、定位理论、StoryArc、TrendRide、PAS、HSO、BigIdea、WhatWhyHow），SOP 引擎自动将 `prompt_templates` 注入 DAG 节点 |
| **批量创意工厂** | 一稿多改、跨平台适配，每个变体均携带推荐的方法论指导 |
| **二维码登录** | 支持抖音/小红书扫码授权，自动维护会话 Cookie |

---

## 系统架构（最新）

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  接入层 / 插件层                                                                       │
│  ┌────────────────────────────────┐  ┌───────────────────────────────────────────┐  │
│  │  OpenClaw Layer1 (intent-gate) │  │  packages/mcp-bridge (Node.js)            │  │
│  │  • 营销意图闸机过滤            │  │  • IntentAwareBridge                      │  │
│  │  • 非营销闲聊拦截              │  │  • 调用 /intent/recognize + /skill/execute│  │
│  └────────────────────────────────┘  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼ HTTP API
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  Layer 1: FastAPI 统一接入层                                                         │
│  ┌─────────────────┬─────────────────┬─────────────────┬─────────────────────────┐  │
│  │ POST            │ POST            │ POST/GET        │ GET/Static              │  │
│  │ /api/v1/        │ /intent/        │ /mcp/*          │ /debug/chat/*           │  │
│  │ marketing/hub   │ recognize       │ Streamable-HTTP │ SSE + SPA               │  │
│  │                 │ clarify         │                 │                         │  │
│  │ POST            │ GET             │                 │ GET /health             │  │
│  │ /skill/execute  │ /skill/list     │                 │ GET /docs /redoc      │  │
│  └─────────────────┴─────────────────┴─────────────────┴─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  Layer 2: Orchestra 多 Agent 中枢（编排决策层）                                       │
│                                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │  MarketingOrchestra (apps/orchestra/core.py)                                  │  │
│  │  • 意图分类器：诊断 / 流量 / 文案 / 脚本 / 选题 / 方法论 / 竞品 / 风险 / 闲聊   │  │
│  │  • 智能路由：根据上下文完整性决定走 AgentTeam 或直接 Skill 调用               │  │
│  │  • SOP 路由 run_sop：加载 methodology_id → compile_methodology_dag()         │  │
│  │  • NLG 层：format_orchestra_reply / format_sop_summary 结构化结果转自然语言    │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │  AgentOrchestrator (apps/orchestra/agent_orchestrator.py)      【新增】        │  │
│  │  • 14 个 Agent 定义（config/agents.yaml）：单账号 6 + 矩阵 6 + 通用 2          │  │
│  │  • 意图→Agent 映射 + 执行模式配置（PARALLEL / SERIAL / MIXED）                │  │
│  │  • 动态 Skill→Tool 映射：同一 Skill 按意图路由到不同 Tool                      │  │
│  │  • execute_team：并行(gather) / 串行(accumulated_context) / 混合(优先级分组)   │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │  SOP 编排引擎：packages/sop-engine/compiler.py                                  │  │
│  │  • MethodologyRegistry.load(methodology_id)                                    │  │
│  │  • PlatformRegistry.load(platform_id)                                          │  │
│  │  • 将 steps 编译为线性 DAG 节点列表                                             │  │
│  │  • 将 methodology.prompt_templates 按 step_id 注入节点 params                    │  │
│  │  • 节点 params 携带 methodology_id + methodology_name                           │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼ SkillHubClient.call()
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  Layer 3: MCP Skill Hub + 13 个独立 SSE Skill                                        │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  核心 MCP 原子能力（挂载于 /mcp，共 12 个工具）                                │    │
│  │  packages/lumina-skills/src/lumina_skills/                                    │    │
│  │  ├── diagnosis.py      diagnose_account / analyze_traffic / detect_risk      │    │
│  │  ├── content.py        generate_text* / generate_script* / select_topic*     │    │
│  │  ├── assets.py         retrieve_methodology / match_cases / qa_knowledge     │    │
│  │  └── tool_skills.py    fetch_industry_news / monitor_competitor / visualize  │    │
│  │                                                                              │    │
│  │  *注：content.py / assets.py 现已全面接入 LLM：                               │    │
│  │      • generate_text: 平台 DNA + 方法论 + 审核规则 → LLM → 结构化文案          │    │
│  │      • generate_script: 分镜模板 + 时长估算 + 平台视频规范 → LLM → 完整脚本    │    │
│  │      • select_topic: 热点新闻 + LLM 批量生成推荐理由                           │    │
│  │      • match_cases: LLM 生成案例 + 模式分析                                    │    │
│  │      • qa_knowledge: LLM 基于方法论库回答专业问题                              │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  13 个独立 SSE MCP Server（skills/skill-*/main.py，transport="sse"）          │    │
│  │                                                                              │    │
│  │  策略层：                         创意层：                                    │    │
│  │  • skill-content-strategist       • skill-creative-studio                    │    │
│  │  • skill-matrix-commander         • skill-bulk-creative                      │    │
│  │  • skill-growth-hacker            • skill-compliance-officer*                │    │
│  │  • skill-knowledge-miner          • skill-community-manager                  │    │
│  │  • skill-sop-evolver              • skill-creative-studio                    │    │
│  │                                   • skill-data-analyst                       │    │
│  │  执行层：                         • skill-account-keeper                     │    │
│  │  • skill-rpa-executor             • skill-rpa-executor                       │    │
│  │                                                                              │    │
│  │  *注：skill-compliance-officer 现已接入：                                     │    │
│  │      • PlatformRegistry.audit_rules 自动预检                                 │    │
│  │      • 风险建议标注 [平台规范库] / [builtin] 来源                             │    │
│  │      • check_account_health 返回 platform_audit_categories                   │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          ▲
                                          │ 读取
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  Layer 4: 双库体系（知识资产层）—— 唯一真相源                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  平台规范库：data/platforms/*.yml                                             │    │
│  │  ├─ xiaohongshu_v2024.yml    → platform_id, content_dna, audit_rules        │    │
│  │  ├─ douyin_v2024.yml         → content_formats: 短视频/图文 长度/格式/标签   │    │
│  │  └─ bilibili_v2024.yml       → content_formats: 仅文字/图文/视频 技术规范    │    │
│  │                                                                              │    │
│  │  content_formats 扩展结构：                                                   │    │
│  │      • 图文：pic_num, title{max_chars}, content{max_chars}, tags{max_count} │    │
│  │      • 视频：video_duration, video_resolution, video_format                 │    │
│  │      • 仅文字：content_layout{paragraphs, lines_per_paragraph}              │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                          │                                           │
│                                          │ 读取                                       │
│                                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  方法论库：data/methodologies/*.yml                                           │    │
│  │  ├─ aida_advanced.yml        → AIDA 增强版（attention / desire）             │    │
│  │  ├─ positioning.yml          → 定位理论（differentiation）                    │    │
│  │  ├─ story_arc.yml            → 故事弧线（setup / climax / resolution）       │    │
│  │  ├─ trend_ride.yml           → 热点借势（trend_spotting / angle_bridge）     │    │
│  │  ├─ hook_story_offer.yml     → HSO（hook / story / offer）                   │    │
│  │  ├─ pas_framework.yml        → PAS（problem / agitation / solution）         │    │
│  │  ├─ big_idea.yml             → 大创意包装（insight / expression）             │    │
│  │  └─ what_why_how.yml         → 科普框架（what / why / how）                  │    │
│  │                                                                              │    │
│  │  统一规范：每套方法论均包含                                                  │    │
│  │      • steps：agent_role + skill_call + theory                               │    │
│  │      • prompt_templates：按 step_id 映射的 LLM 提示模板                      │    │
│  │      • applicable_scenarios + success_cases                                  │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  统一读取层：packages/knowledge-base/                                         │    │
│  │  • PlatformRegistry    → load(platform_id) / content_formats / audit_rules   │    │
│  │  • MethodologyRegistry → load(methodology_id) / find_best_match()            │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │  统一工具层：packages/lumina-skills/methodology_utils.py                      │    │
│  │  • resolve_methodology()          按 query/industry/goal 匹配               │    │
│  │  • build_methodology_prompt()     将 steps+templates 转为 LLM prompt 文本   │    │
│  │  • match_methodology_for_content() 按 topic 关键词智能推荐方法论              │    │
│  │  • list_available_methodologies() 返回真实存在的 methodology_id 列表         │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Agent 编排机制

### 执行模式

| 模式 | 意图 | Agent 组合 | 说明 |
|------|------|-----------|------|
| **PARALLEL** | diagnosis | data_analyst + content_strategist | 并行诊断账号 + 分析内容策略 |
| **PARALLEL** | traffic_analysis | data_analyst + growth_hacker | 并行流量漏斗分析 + 增长策略 |
| **SERIAL** | content_creation | creative_studio → compliance_officer | 先生成文案，再审查合规 |
| **SERIAL** | script_creation | creative_studio | 生成短视频脚本 |
| **MIXED** | matrix_setup | matrix_commander + account_keeper | 高优先级并行，低优先级串行 |

### 动态 Skill→Tool 映射

同一 Agent 在不同意图下自动调用不同的底层 Tool：

```python
# skill-creative-studio
content_creation → generate_text      # 写文案
script_creation  → generate_script    # 写脚本

# skill-data-analyst
diagnosis        → diagnose_account   # 账号诊断
traffic_analysis → analyze_traffic    # 流量分析
```

### 调用链路示例（诊断场景）

```
用户: "帮我诊断一下账号"
  ↓
MarketingOrchestra._classify_intent() → kind="diagnosis"
  ↓
_should_use_agent_team() → True（有 account_url）
  ↓
_run_agent_team()
  ├─ orchestrate("diagnosis") → AgentTeam[PARALLEL: data_analyst, content_strategist]
  └─ execute_team(team)
      ├─ _execute_agent(data_analyst)
      │   └─ skill_hub_client.call("diagnose_account", {...})
      │       └─ diagnose_account() → 基础诊断 / RPA 抓取
      └─ _execute_agent(content_strategist)
          └─ skill_hub_client.call("select_topic", {...})
              └─ select_topic() → get_client("select_topic").complete(prompt)
                  └─ LLM 返回推荐选题
```

---

## 双库驱动的工作原理

### 1. 平台规范库驱动示例

当用户请求为「小红书」生成文案时，系统会读取 `data/platforms/xiaohongshu_v2024.yml`：

```yaml
content_dna:
  - element: "hook_position"
    value: "0-3s"
  - element: "title_length"
    value: "12-20字推荐"
audit_rules:
  - category: "medical"
    forbidden_terms: ["疗效", "治疗", "治愈"]
content_formats:
  图文:
    title: { max_chars: 20 }
    content: { max_chars: 1000 }
    tags: { max_count: 10 }
```

这些信息会被注入到 `generate_text` / `generate_script` / `optimize_title` 的 prompt 中，并作为截断/限制的硬约束。

### 2. 方法论库驱动示例

当用户输入带有「痛点」「避坑」「怎么做」等关键词时，`match_methodology_for_content()` 会自动匹配 `pas_framework`：

```
方法论框架：痛点-激化-解决（pas_framework）
结构模板：
  - problem: 精准描述目标受众的一个具体痛点...
  - agitation: 放大不解决的代价...
  - solution: 给出可立即执行的解决方案...
执行步骤：
  - problem（理论：pain_point_resonance）[角色：creative]
  - agitation（理论：loss_aversion）[角色：creative]
  - solution（理论：instant_gratification）[角色：creative]
```

该文本会被完整拼接到 LLM prompt 的「方法论框架」段落中，指导文案按 PAS 结构生成。

---

## 快速开始

### 环境要求

- Python 3.11+
- (可选) Docker & Docker Compose

### 本地开发

```bash
# 1. 克隆仓库
git clone <repository-url>
cd lumina

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填写你的 LLM API Key（至少需要一个）
# DEEPSEEK_API_KEY=sk-xxx
# OPENAI_API_KEY=sk-xxx

# 4. 配置 LLM 池（编辑 infra/config/llm.yaml）
# 确保 default_llm 指向你已配置密钥的模型

# 5. 启动服务
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api/src
```

### Docker 启动

```bash
# 使用 Docker Compose（包含热重载）
docker compose -f docker-compose.local.yml up --build
```

### 验证安装

- 健康检查: http://127.0.0.1:8000/health
- API 文档: http://127.0.0.1:8000/docs
- 调试界面: http://127.0.0.1:8000/debug/chat/

---

## 项目结构

```
lumina/
├── apps/
│   ├── api/                 # FastAPI 主服务（接入层）
│   ├── orchestra/           # Layer2 编排中枢
│   │   ├── core.py          # MarketingOrchestra（意图路由 + SOP DAG + AgentTeam 调用）
│   │   ├── agent_orchestrator.py  # AgentOrchestrator（14 Agent + 3 种执行模式）
│   │   └── nlg.py           # 结构化结果转自然语言
│   ├── skill-hub/           # Layer3 MCP Skill Hub（streamable-http）
│   ├── intent/              # 意图识别引擎（纯逻辑库）
│   └── rpa/                 # 浏览器自动化（Playwright）
├── packages/
│   ├── lumina-skills/       # 原子 Skill 实现 + methodology_utils
│   │   ├── content.py       # generate_text / generate_script / select_topic（已接入LLM）
│   │   ├── diagnosis.py     # diagnose_account / analyze_traffic / detect_risk
│   │   ├── assets.py        # retrieve_methodology / match_cases / qa_knowledge（已接入LLM）
│   │   └── registry.py      # TOOL_REGISTRY（12 个工具注册）
│   ├── knowledge-base/      # PlatformRegistry + MethodologyRegistry
│   ├── llm-hub/             # LLM 池管理（多模型切换）
│   ├── skill-hub-client/    # Skill 调用客户端
│   ├── sop-engine/          # SOP DAG 编译器
│   ├── mcp-bridge/          # Node.js Bridge（OpenClaw 对接）
│   └── agent-core/          # Agent 基类与上下文
├── skills/                  # 13 个独立 SSE MCP Skill Server
│   ├── skill-creative-studio/
│   ├── skill-content-strategist/
│   ├── skill-bulk-creative/
│   ├── skill-compliance-officer/
│   ├── skill-data-analyst/
│   ├── skill-account-keeper/
│   ├── skill-matrix-commander/
│   ├── skill-growth-hacker/
│   ├── skill-knowledge-miner/
│   ├── skill-community-manager/
│   ├── skill-sop-evolver/
│   ├── skill-traffic-broker/
│   └── skill-rpa-executor/
├── config/
│   ├── agents.yaml          # 14 个 Agent 定义 + 编排规则 + 执行模式配置
│   ├── llm.yaml             # LLM 池与技能-模型分配
│   └── intent_rules.yaml    # 意图匹配规则
├── data/
│   ├── methodologies/       # 8 套方法论 YAML 配置
│   ├── platforms/           # 平台规范 YAML 配置
│   ├── credentials/         # 登录凭证存储
│   └── sessions/            # 会话数据
├── tests/                   # 测试套件
│   ├── integration/         # 端到端集成测试
│   │   └── test_e2e_agent_skill_llm.py  # Agent→Skill→LLM 完整链路测试
│   ├── test_agent_team.py   # AgentOrchestrator 单元测试
│   └── skills/              # Skill 单元测试
├── docs/                    # 架构文档
├── scripts/                 # 启动脚本
└── static/debug_chat/       # Web 调试界面
```

---

## 配置说明

### LLM 配置

编辑 `infra/config/llm.yaml` 配置模型池：

```yaml
llm_pool:
  deepseek-v3:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    api_base: ${DEEPSEEK_API_BASE:-https://api.deepseek.com}

  gpt-4o-mini:
    provider: openai
    model: gpt-4o-mini
    api_key: ${OPENAI_API_KEY}

default_llm: deepseek-v3

skill_config:
  debug_chat:
    llm: deepseek-v3
  generate_text:
    llm: deepseek-v3
```

### Agent 编排配置

编辑 `config/agents.yaml` 调整 Agent 定义和编排规则：

```yaml
single_account_agents:
  data_analyst:
    skills: [skill-data-analyst]
    triggers: [diagnosis, data_analysis, traffic_analysis]
    priority: 1

orchestration:
  intent_agent_map:
    diagnosis: [data_analyst, content_strategist]
    content_creation: [creative_studio, compliance_officer]
  execution_modes:
    parallel: [diagnosis, traffic_analysis]
    sequential: [content_creation, script_creation]
    mixed: [matrix_setup]
```

### 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 推荐 |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 可选 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | 可选 |
| `LLM_CONFIG_PATH` | LLM 配置文件路径 | 可选 |
| `LUMINA_PORT` | 服务端口（默认 8000） | 可选 |

---

## API 使用

### 营销中枢接口

```bash
curl -X POST http://127.0.0.1:8000/api/v1/marketing/hub \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "帮我诊断一下账号",
    "user_id": "user_001",
    "platform": "xiaohongshu",
    "context": {"account_url": "https://xiaohongshu.com/user/xxx"}
  }'
```

### MCP 接口

MCP 服务挂载在 `/mcp`，支持 Streamable HTTP 传输。

---

## 测试指南

### 运行全部测试

```bash
pytest tests/ -v
```

### 运行端到端集成测试（验证 Agent→Skill→LLM 链路）

```bash
pytest tests/integration/test_e2e_agent_skill_llm.py -v
```

覆盖场景：
- **PARALLEL 诊断**：data_analyst + content_strategist 并行执行
- **SERIAL 内容创作**：creative_studio → compliance_officer 串行流水线
- **MIXED 矩阵搭建**：高优先级并行 + 低优先级串行
- **Skill 直接 LLM 调用**：generate_text / generate_script / select_topic / match_cases / qa_knowledge
- **降级行为**：LLM 不可用时返回明确的降级提示

### 运行 Agent 编排测试

```bash
pytest tests/test_agent_team.py -v
```

### 运行 Skill 单元测试

```bash
pytest tests/skills/ -v
```

### 运行特定测试

```bash
# 仅测试脚本生成的 LLM 集成
pytest tests/skills/test_generate_script.py -v

# 仅测试流量分析 AgentTeam
pytest tests/integration/test_e2e_agent_skill_llm.py::TestAgentOrchestrationE2E::test_traffic_analysis_parallel -v
```

---

## 开发指南

### 添加新 Skill

1. 在 `packages/lumina-skills/src/lumina_skills/` 实现原子 Skill 函数
2. 在 `packages/lumina-skills/src/lumina_skills/registry.py` 注册到 TOOL_REGISTRY
3. 如需独立 SSE 服务，在 `skills/skill-<name>/` 新建 FastMCP 应用
4. 如需 LLM 支持，使用 `from llm_hub import get_client` 获取客户端并调用 `complete()`

### 添加新方法论

1. 在 `data/methodologies/<methodology_id>.yml` 创建 YAML
2. 确保包含 `steps` + `prompt_templates` + `applicable_scenarios`
3. 系统会自动通过 `MethodologyRegistry` 和 `methodology_utils` 分发到所有生成类 Skill

### 添加/修改平台规范

1. 编辑 `data/platforms/<platform>_v2024.yml`
2. 在 `content_dna`、`audit_rules`、`content_formats` 中补充规范
3. `PlatformRegistry` 会自动加载，所有 Skill 的生成/适配/审核行为会同步变化

### 添加新 Agent

1. 在 `config/agents.yaml` 的 `single_account_agents` / `matrix_agents` / `utility_agents` 中添加定义
2. 在 `orchestration.intent_agent_map` 中配置意图映射
3. 在 `orchestration.execution_modes` 中配置执行模式
4. 如需新的 Skill→Tool 映射，在 `AgentOrchestrator.SKILL_TOOL_MAP` 中添加

---

## 相关文档

- [架构文档](docs/ARCHITECTURE.md) - 系统架构设计
- [开发计划](Development_plan_v2.md) - 详细开发规划
- [Docker 部署](docs/DOCKER_DEPLOYMENT.md) - 生产部署指南
- [OpenClaw 集成](docs/INTEGRATION_OPENCLAW.md) - 与 OpenClaw 集成
- [本地测试指南](LOCAL_SETUP_GUIDE.md) - 保姆级本地环境搭建与测试

## 技术栈

- **Web 框架**: FastAPI
- **MCP 协议**: FastMCP（streamable-http + sse 双传输）
- **LLM 调用**: LiteLLM（支持 DeepSeek / OpenAI / Anthropic / 通义千问）
- **浏览器自动化**: Playwright
- **配置管理**: Pydantic + PyYAML
- **测试**: pytest + pytest-asyncio

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**注意**: 本项目正在积极开发中，API 可能会有变动。欢迎提交 Issue 和 PR！
