我将基于您提供的**OpenClaw 原生扩展 + Python Skill 层**混合架构方案，对原开发计划进行全面重构。新计划保留了 LLM Management Hub 的两步配置法、详细的 Skill 开发规范，同时采用更合理的 14 周开发周期。

```markdown
# AI 营销助手开发计划（OpenClaw 原生扩展架构 V3.0）

> 架构策略：保留 OpenClaw 原生能力（Node.js）+ Python MCP Skill 层  
> 核心变更：放弃移植方案，改为基于 OpenClaw 扩展 + MCP Bridge  
> 版本：V3.0  
> 日期：2026-03-28

---

## 📋 目录

1. [架构变更说明](#1-架构变更说明)
2. [项目概述](#2-项目概述)
3. [技术架构与选型](#3-技术架构与选型)
4. [开发阶段规划](#4-开发阶段规划)
5. [OpenClaw 扩展开发指南](#5-openclaw-扩展开发指南)
6. [Python Skill 开发规范](#6-python-skill-开发规范)
7. [LLM Management Hub 设计](#7-llm-management-hub-设计)
8. [里程碑与交付物](#8-里程碑与交付物)
9. [风险评估与应对](#9-风险评估与应对)
10. [团队配置建议](#10-团队配置建议)

---

## 1. 架构变更说明

### 1.1 架构对比：移植 vs 扩展

| 维度 | 原方案（移植到 Python） | 新方案（原生扩展） |
|------|---------------------|------------------|
| **核心框架** | Python 重写 OpenClaw | 保留 OpenClaw Node.js 原生 |
| **对话能力** | 需重新实现（风险高） | 立即可用（已验证） |
| **开发周期** | 36 周 | 14 周（缩短 60%） |
| **澄清机制** | 自行开发 | 原生支持 |
| **Skill 语言** | Python | Python（不变） |
| **主要工作** | 重写 Agent Runtime | 开发 MCP Bridge（2 周） |

### 1.2 新架构分层

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Layer A: OpenClaw 原生层 (Node.js)               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Gateway    │  │Agent Runtime │  │ Session Mgr  │              │
│  │   (Node.js)  │  │  (Node.js)   │  │  (Node.js)   │              │
│  │              │  │              │  │              │              │
│  │ • WebSocket  │  │ • ReAct循环  │  │ • 对话状态机 │              │
│  │ • 消息路由   │  │ • 工具选择   │  │ • 上下文管理 │              │
│  │ • 意图识别   │  │ • 澄清机制   │  │ • 记忆持久化 │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│         └─────────────────┴─────────────────┘                       │
│                           │                                         │
│                    ┌──────┴──────┐                                  │
│                    │  MCP Client │ (Node.js 扩展)                     │
│                    │  (新开发)    │                                  │
│                    └──────┬──────┘                                  │
└───────────────────────────┼─────────────────────────────────────────┘
                            │ MCP Protocol (SSE/HTTP)
┌───────────────────────────┼─────────────────────────────────────────┐
│                    Layer B: AI Core Service (Python)                │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    LLM Management Hub                            │ │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────────────┐  │ │
│  │  │  LLM Pool  │  │ Assignment   │  │      LLM Client        │  │ │
│  │  │            │  │   分配策略    │  │                        │  │ │
│  │  │ • gpt-4o   │  │             │  │ • 统一调用接口          │  │ │
│  │  │ • claude   │  │ • 显式指定   │  │ • Token 统计           │  │ │
│  │  │ • deepseek │  │ • 策略指派   │  │ • 故障转移             │  │ │
│  │  └────────────┘  └──────────────┘  └─────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                    │                                 │
│  ┌─────────────────────────────────┴─────────────────────────────┐   │
│  │              MCP Skill Hub (Python FastMCP)                  │   │
│  │                                                              │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │
│  │  │ 诊断类    │ │ 内容类    │ │ 资产类    │ │ 工具类    │        │   │
│  │  │ Skill    │ │ Skill    │ │ Skill    │ │ Skill    │        │   │
│  │  │          │ │          │ │          │ │          │        │   │
│  │  │•账号诊断  │ │•文案生成  │ │•方法论检索│ │•行业新闻  │        │   │
│  │  │•流量分析  │ │•脚本创作  │ │•案例匹配  │ │•竞品监测  │        │   │
│  │  │•风险评估  │ │•选题生成  │ │•知识库问答│ │•数据可视化│        │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 项目概述

### 2.1 项目目标

构建基于 **OpenClaw 原生扩展 + Python MCP Skill 层** 的 AI 营销助手：
- **核心框架**：直接使用 OpenClaw（保留 Agent Runtime、ReAct 循环、对话状态机）
- **业务层**：Python MCP Skill（诊断、内容生成、数据分析）
- **通信协议**：MCP (Model Context Protocol) 连接 Node.js 和 Python 层
- **数据隔离**：按 `user_id` 进行用户数据隔离

### 2.2 关键术语

| 术语 | 定义 | 变更说明 |
|------|------|---------|
| **OpenClaw Core** | Node.js 原生框架，包含 Gateway、Agent Runtime、Session | **【新】**不再移植，直接使用 |
| **MCP Bridge** | Node.js 层扩展，连接 OpenClaw 与 Python Skill | **【新】**新增组件 |
| **Skill** | Python 实现的 MCP Server，原子业务能力的封装 | **【不变】**仍用 Python |
| **Orchestrator** | OpenClaw 的 Agent Runtime（ReAct 循环） | **【新】**复用 OpenClaw 原生 |
| **Session State** | OpenClaw 的对话状态机（CLARIFYING/EXECUTING 等） | **【新】**复用 OpenClaw 原生 |

---

## 3. 技术架构与选型

### 3.1 整体架构详解

#### Layer A: OpenClaw 原生层（保留）

**不复用的组件（直接使用）：**
- **Gateway Server** (`src/gateway/server.js`): WebSocket 服务器，端口 18789
- **Session Manager** (`src/gateway/session.js`): 对话状态机（关键！解决澄清问题）
- **Agent Runtime** (`src/agent/runtime.js`): ReAct 循环实现（关键！）
- **Intent Engine** (`src/gateway/intent.js`): 意图识别（含澄清判断）
- **Memory Manager** (`src/memory/manager.js`): 对话记忆管理

**需要扩展的组件：**
- **MCP Bridge** (`src/skills/mcp-bridge.js`): 将 OpenClaw Tool 调用转为 MCP 请求

#### Layer B: Python Skill 层（新开发）

- **LLM Management Hub**: 统一管理多模型配置与分配
- **MCP Skill Hub**: FastMCP 实现的业务 Skill
- **Data Layer**: PostgreSQL + Redis（按 `user_id` 隔离）

### 3.2 技术栈选型

#### Layer A: OpenClaw 层

| 组件 | 技术 | 说明 | 变更 |
|------|------|------|------|
| **OpenClaw Core** | Node.js (官方仓库) | Fork 官方仓库，不做移植 | **【变更】**从"移植 Python"改为"直接使用" |
| **Gateway** | OpenClaw 原生 | WebSocket Server + Session Manager | **【不变】**保留 |
| **Agent Runtime** | OpenClaw 原生 | ReAct 循环 + 澄清机制 | **【不变】**保留 |
| **MCP Bridge** | Node.js (新开发) | 连接 OpenClaw 与 Python Skill | **【新增】** |
| **MCP SDK** | `@modelcontextprotocol/sdk` | 官方 Node.js SDK | **【新增】** |

#### Layer B: Python 层

| 组件 | 技术 | 说明 | 变更 |
|------|------|------|------|
| **Web 框架** | FastAPI | 提供 MCP Server HTTP/SSE 接口 | **【不变】** |
| **MCP SDK** | `fastmcp` / `mcp` | Python MCP 官方 SDK | **【不变】** |
| **LLM 框架** | LiteLLM | 多模型统一调用 | **【不变】** |
| **数据库** | PostgreSQL + Redis | 数据持久化（按 user_id 隔离） | **【不变】** |

### 3.3 MCP Bridge 设计

**核心职责**：将 OpenClaw 的 Tool 调用转换为 MCP 请求，转发到 Python 层。

```javascript
// src/skills/ai-marketing-bridge.js (Node.js 扩展)
const { Client } = require('@modelcontextprotocol/sdk');
const { HttpTransport } = require('@modelcontextprotocol/sdk/http');

class McpBridgeTool {
  constructor() {
    this.client = new Client({
      transport: new HttpTransport(process.env.PYTHON_MCP_URL)
    });
  }

  async execute(params, context) {
    // 将 OpenClaw 调用转发到 Python Skill
    const result = await this.client.callTool({
      name: params.skill_name,
      arguments: {
        ...params,
        user_id: context.session.user_id,
        session_id: context.session.id
      }
    });
    
    // 将 Python 结果转回 OpenClaw 格式
    return {
      type: 'skill_result',
      content: result.content,
      data: result.data
    };
  }
}

// OpenClaw 配置
module.exports = {
  name: 'ai_marketing_assistant',
  description: 'AI 营销助手 Python 层桥接',
  execute: (params, context) => new McpBridgeTool().execute(params, context),
  shouldActivate: (intent) => intent.category === 'marketing' || intent.category === 'casual_chat'
};
```

---

## 4. 开发阶段规划

### 4.1 总体时间线（14 周）

```
Week 1-2:   OpenClaw 环境准备 + Fork
Week 3-4:   MCP Bridge 开发
Week 5-10:  Python Skill 层开发（LLM Hub + 核心 Skills）
Week 11-12: 集成测试 + 对话体验优化
Week 13-14: 生产部署 + 监控
```

### 4.2 详细任务分解

#### 阶段一：OpenClaw 环境准备（Week 1-2）

**目标**：验证 OpenClaw 原生对话能力，确认澄清机制可用。

| 任务 | 负责人 | 输出物 | 关键验证点 |
|------|--------|--------|-----------|
| 1.1 Fork OpenClaw 仓库 | 架构师 | `vendor/openclaw/` | 保留 git 历史，便于后续同步 |
| 1.2 理解 OpenClaw 架构 | 架构师 | 架构文档 | 重点理解 Agent Runtime 和 Session State |
| 1.3 配置 Node.js 环境 | DevOps | 运行环境 | Node.js 18+，端口 18789 可用 |
| 1.4 验证原生对话能力 | 架构师 | 测试报告 | 测试"今天过得怎么样"是否能正确澄清而非返回 JSON |
| 1.5 设计 MCP Bridge 接口 | 架构师 | 接口文档 | 定义 Node.js 与 Python 通信协议（Tool 名称、参数格式） |

**验证清单：**
- [ ] OpenClaw Gateway 能在端口 18789 接收 WebSocket
- [ ] OpenClaw 能识别闲聊并主动提问（而非返回 JSON）
- [ ] Session 能正确保持对话状态（CLARIFYING → EXECUTING → COMPLETED）

#### 阶段二：MCP Bridge 开发（Week 3-4）

**目标**：建立 Node.js 与 Python 的双向通信通道。

| 任务 | 负责人 | 输出物 | 说明 |
|------|--------|--------|------|
| 2.1 开发 MCP Client (Node.js) | 后端工程师 | `packages/mcp-bridge/client.js` | 在 OpenClaw 中注册为 Tool |
| 2.2 实现请求转发 | 后端工程师 | Bridge 核心逻辑 | 将 OpenClaw 的 Tool 调用转发到 Python |
| 2.3 实现响应处理 | 后端工程师 | 响应处理器 | 将 Python 结果转回 OpenClaw 格式 |
| 2.4 错误处理与重试 | 后端工程师 | 错误处理模块 | Python 服务不可用时的降级策略 |
| 2.5 会话状态同步 | 后端工程师 | 状态同步机制 | 确保 Node.js Session ID 透传到 Python |

**核心代码示例（Node.js）：**

```javascript
// packages/mcp-bridge/index.js
const { Client } = require('@modelcontextprotocol/sdk');

class OpenClawMcpBridge {
  constructor(pythonMcpUrl) {
    this.client = new Client({
      transport: new HttpTransport(pythonMcpUrl)
    });
  }

  async executeSkill(skillName, params, sessionContext) {
    try {
      const result = await this.client.callTool({
        name: skillName,
        arguments: {
          ...params,
          _context: {
            user_id: sessionContext.user_id,
            session_id: sessionContext.session_id,
            memory: sessionContext.memory
          }
        }
      });
      
      return {
        success: true,
        data: result
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        fallback: 'AI 服务暂时不可用，请稍后重试'
      };
    }
  }
}
```

#### 阶段三：Python Skill 层开发（Week 5-10）

**目标**：构建 LLM Management Hub 和 5 个核心 Skill。

**Week 5-6：LLM Hub + 基础框架**

| 任务 | 负责人 | 输出物 |
|------|--------|--------|
| 3.1 Python MCP Server 框架 | 架构师 | `apps/api/main.py` (FastAPI + FastMCP) |
| 3.2 LLM Hub 配置中心 | 后端工程师 | `packages/llm-hub/config.py` (两步配置法) |
| 3.3 LLM Provider 适配器 | 后端工程师 | OpenAI/Claude/DeepSeek 适配 |
| 3.4 用户数据隔离层 | 后端工程师 | `user_id` 透传与数据隔离实现 |

**Week 7-10：核心 Skills 开发**

| Skill 类型 | Skill 名称 | 负责人 | LLM 分配策略 |
|-----------|-----------|--------|-------------|
| **诊断类** | skill-account-diagnosis | 算法工程师 | `deepseek-r1` (推理模型) |
| **诊断类** | skill-traffic-analysis | 算法工程师 | `deepseek-v3` |
| **内容类** | skill-text-generator | 算法工程师 | `claude-sonnet` (创意能力) |
| **内容类** | skill-topic-selection | 算法工程师 | `gpt-4o` |
| **资产类** | skill-methodology-retrieval | 后端工程师 | `gpt-4o-mini` (低成本) |

**Skill 开发示例（Python）：**

```python
# skills/skill-account-diagnosis/main.py
from fastmcp import FastMCP
from llm_hub import get_client

mcp = FastMCP("account_diagnosis")

@mcp.tool()
async def diagnose_account(user_id: str, platform: str, account_url: str) -> dict:
    """
    诊断账号表现（被 OpenClaw 通过 MCP 调用）
    
    Args:
        user_id: 用户ID（数据隔离）
        platform: 平台类型（xiaohongshu/douyin）
        account_url: 账号链接
    """
    # 1. 获取 LLM Client（根据配置自动选择模型）
    llm = get_client(skill_name="account_diagnosis")
    
    # 2. 获取用户历史数据（按 user_id 隔离）
    user_history = await get_user_history(user_id)
    
    # 3. 执行诊断逻辑
    analysis = await analyze_traffic_data(account_url, user_history)
    
    # 4. 生成诊断报告
    report = await llm.complete(
        f"基于以下数据生成诊断报告：{analysis}",
        temperature=0.3
    )
    
    return {
        "diagnosis_result": report,
        "metrics": analysis,
        "recommendations": generate_recommendations(analysis)
    }

if __name__ == "__main__":
    mcp.run(transport="sse")  # Server-Sent Events 供 Node.js 连接
```

#### 阶段四：集成与优化（Week 11-12）

| 任务 | 负责人 | 输出物 | 说明 |
|------|--------|--------|------|
| 4.1 Node.js + Python 联调 | 全团队 | 集成测试报告 | 验证完整链路（用户输入 → OpenClaw → MCP → Python → 返回） |
| 4.2 对话体验优化 | 算法工程师 | 体验优化报告 | 重点优化澄清问题质量（OpenClaw 原生能力调优） |
| 4.3 性能压测 | DevOps | 压测报告 | 测试 MCP 通信延迟（目标 < 200ms） |
| 4.4 故障转移测试 | DevOps | 测试报告 | Python 层故障时 OpenClaw 的降级表现 |

#### 阶段五：生产部署（Week 13-14）

| 任务 | 负责人 | 输出物 |
|------|--------|--------|
| 5.1 Docker 化（Node.js + Python） | DevOps | `docker-compose.yml` |
| 5.2 K8s 部署模板 | DevOps | Helm Charts |
| 5.3 监控告警 | DevOps | Prometheus + Grafana 配置 |
| 5.4 文档编写 | 全团队 | API 文档、部署手册 |

---

## 5. OpenClaw 扩展开发指南

### 5.1 代码仓库结构

```
ai-marketing-assistant/
├── apps/
│   ├── api/                    # Python FastAPI + MCP Server
│   │   ├── main.py
│   │   └── skills/             # Python Skills 注册
│   └── worker/                 # Python 异步任务
├── packages/
│   ├── mcp-bridge/             # Node.js MCP Bridge（新开发）
│   │   ├── index.js
│   │   └── client.js
│   └── llm-hub/                # Python LLM Hub
│       ├── config.py
│       └── client.py
├── vendor/
│   └── openclaw/               # Fork 的 OpenClaw 代码
│       ├── src/
│       │   ├── gateway/        # 直接使用
│       │   ├── agent/          # 直接使用
│       │   └── skills/         # 扩展 MCP Bridge
│       └── package.json
├── skills/                     # Python MCP Skills
│   ├── skill-account-diagnosis/
│   ├── skill-text-generator/
│   └── ...
└── docker-compose.yml
```

### 5.2 OpenClaw 配置修改

```javascript
// vendor/openclaw/config/config.js
module.exports = {
  gateway: {
    port: 18789,
    websocket: true
  },
  
  // 注册我们的 MCP Bridge
  skills: [
    require('../../packages/mcp-bridge'),  // AI 营销助手 Bridge
    // ... 其他原生 Skill
  ],
  
  // 关键配置：澄清机制（解决您的核心痛点）
  agent: {
    enableClarification: true,      // 启用澄清问题
    maxClarificationRounds: 3,      // 最多 3 轮澄清
    clarificationThreshold: 0.6,    // 置信度低于 0.6 时触发澄清
    defaultSkill: 'ai_marketing_assistant'
  },
  
  session: {
    storage: 'redis',               // 使用 Redis 持久化
    redis: {
      host: process.env.REDIS_HOST,
      port: 6379
    },
    ttl: 3600                       // 1 小时过期
  }
};
```

### 5.3 对话状态机（OpenClaw 原生）

**OpenClaw 原生支持的状态（您不再需要自己实现）：**

```
用户输入："今天过得怎么样"

    ↓
┌─────────────┐
│    IDLE     │ ← 初始状态
│    空闲     │
└──────┬──────┘
       │
       ▼
┌─────────────┐     置信度低或信息不足
│  CLARIFYING │ ← "请问你是想了解账号诊断，还是内容创作？"
│   澄清中    │
└──────┬──────┘
       │
       ▼ (用户回复："诊断账号")
┌─────────────┐
│  PLANNING   │ ← Agent Runtime 生成执行计划
│   规划中    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  EXECUTING  │ ← 调用 Python Skill（通过 MCP Bridge）
│   执行中    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  COMPLETED  │ ← 返回结果给用户
│   已完成    │
└─────────────┘
```

---

## 6. Python Skill 开发规范

### 6.1 Skill 目录结构

```
skills/skill-{name}/
├── SKILL.md                    # OpenClaw 风格 Skill 定义（元信息）
├── pyproject.toml              # Python 项目配置
├── src/
│   └── skill_{name}/
│       ├── __init__.py
│       ├── main.py            # MCP Server 入口
│       ├── prompts.py         # Prompt 模板
│       └── utils.py           # 工具函数
├── tests/
│   └── test_skill.py
└── Dockerfile                 # 独立容器化（可选）
```

### 6.2 SKILL.md 规范（兼容 OpenClaw）

```markdown
---
name: text_generator
version: 1.0.0
description: 基于营销定位生成各平台文案内容
author: AI Marketing Team
tags: [generation, content, marketing]
llm_config:
  strategy: explicit
  model: claude-sonnet
  temperature: 0.8
input_schema:
  content_type: {type: string, enum: [post, script, copy]}
  topic: {type: string}
  platform: {type: string}
output_schema:
  title: {type: string}
  content: {type: string}
  hashtags: {type: array, items: {type: string}}
timeout: 30
---

# 使用说明

## 调用示例
...
```

### 6.3 Skill 实现模板

```python
# skills/skill-text-generator/src/skill_text_generator/main.py
from fastmcp import FastMCP
from pydantic import BaseModel
from llm_hub import get_client
from typing import Optional

mcp = FastMCP("text_generator")

class TextInput(BaseModel):
    content_type: str
    topic: str
    platform: str
    tone: Optional[str] = "professional"
    user_id: str  # 用于数据隔离

class TextOutput(BaseModel):
    title: str
    content: str
    hashtags: list[str]

@mcp.tool()
async def generate_text(args: TextInput) -> TextOutput:
    """
    生成营销文案（被 OpenClaw 通过 MCP 调用）
    """
    # 1. 获取 LLM（根据 SKILL.md 配置自动路由）
    llm = get_client(skill_name="text_generator")
    
    # 2. 获取用户画像（按 user_id 隔离）
    profile = await get_user_profile(args.user_id)
    
    # 3. 构造 Prompt
    prompt = build_prompt(args, profile)
    
    # 4. 调用 LLM
    response = await llm.complete(prompt)
    
    # 5. 解析结果
    result = parse_response(response)
    
    return TextOutput(**result)

if __name__ == "__main__":
    mcp.run(transport="sse")
```

---

## 7. LLM Management Hub 设计

采用**"先建池，后分配"**的两步配置法。

### 7.1 配置结构

```yaml
# config/llm.yaml

# ========== 第一步：配置 LLM 池 ==========
llm_pool:
  claude-sonnet:
    provider: anthropic
    model: claude-3-5-sonnet-20241022
    api_key: ${ANTHROPIC_API_KEY}
    temperature: 0.5
    max_tokens: 8192
    tags: ["high-quality", "reasoning"]
    cost_per_1k_input: 0.003
    cost_per_1k_output: 0.015
    
  deepseek-v3:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    tags: ["cheap", "fast"]
    
  deepseek-r1:
    provider: deepseek
    model: deepseek-reasoner
    tags: ["reasoning", "cheap"]
    
  gpt-4o-mini:
    provider: openai
    model: gpt-4o-mini
    tags: ["cheap", "fast"]

# ========== 第二步：配置分配策略 ==========
default_llm: "deepseek-v3"

skill_config:
  # 文案生成：显式指定 Claude（创意能力强）
  text_generator:
    llm: "claude-sonnet"
    temperature: 0.8
    
  # 账号诊断：显式指定推理模型
  account_diagnosis:
    llm: "deepseek-r1"
    
  # 内容改写：使用成本优先策略
  content_rewrite:
    strategy: "cost_aware"
    
  # 竞品监测：使用延迟优先策略
  competitor_monitor:
    strategy: "latency_first"
```

### 7.2 调用代码示例

```python
from llm_hub import get_client

# 方式 1：Skill 自动根据配置获取
llm = get_client(skill_name="text_generator")
# 根据配置，这会返回 claude-sonnet

# 方式 2：显式指定（临时覆盖）
llm = get_client(llm_name="gpt-4o")

# 方式 3：使用策略
llm = get_client(strategy="cost_aware")
```

---

## 8. 里程碑与交付物

| 里程碑 | 时间 | 交付物 | 变更说明 |
|--------|------|--------|----------|
| **M1** | Week 2 | OpenClaw 运行环境 | **【变更】**验证原生对话能力（澄清机制） |
| **M2** | Week 4 | MCP Bridge 连通 | **【新增】**Node.js-Python 通道验证 |
| **M3** | Week 10 | 5 个核心 Skill | **【不变】**Python 层完成 |
| **M4** | Week 12 | 完整对话体验 | **【新增】**重点验收澄清机制（非 JSON 返回） |
| **GA** | Week 14 | 生产发布 | **【缩短】**提前 22 周 |

---

## 9. 风险评估与应对

| 风险 | 影响 | 应对策略 |
|------|------|---------|
| **OpenClaw 与 Python 通信延迟** | 中 | 使用 SSE 长连接，本地部署时走 Unix Socket；目标 < 200ms |
| **OpenClaw 社区支持** | 低 | Fork 后自主维护，核心代码稳定；仅做配置层扩展 |
| **Node.js 团队不熟悉** | 中 | 仅修改配置层（`config.js` + Bridge），不动核心逻辑 |
| **状态同步复杂** | 中 | 明确边界：Node.js 管对话状态，Python 管业务数据；只透传 `user_id` 和 `session_id` |
| **MCP 协议变更** | 低 | 封装 SDK，隔离协议细节 |

---

## 10. 团队配置建议

### 10.1 核心团队（精简版）

| 角色 | 人数 | 主要职责 |
|------|------|---------|
| **架构师** | 1 | OpenClaw 架构理解、MCP Bridge 设计、技术决策 |
| **Node.js 后端** | 1 | MCP Bridge 开发、OpenClaw 配置扩展 |
| **Python 后端** | 2 | LLM Hub、MCP Skills、数据层开发 |
| **算法工程师** | 1 | Skill 提示词优化、LLM 策略调优 |
| **DevOps** | 1 | 双栈部署（Node.js + Python）、监控 |

### 10.2 关键技能要求

- **架构师**：理解 OpenClaw 源码（Node.js），设计分布式系统
- **Node.js 后端**：熟悉 WebSocket、异步编程、MCP 协议
- **Python 后端**：FastAPI、异步编程、PostgreSQL/Redis
- **算法工程师**：LLM 提示工程、多模型调优

---

## 附录

### A. 新旧方案对比总结

| 维度 | 原方案（移植） | 新方案（扩展） |
|------|---------------|---------------|
| **对话体验** | 36 周后可能仍无法澄清 | 第 2 周即可验证澄清能力 |
| **技术债务** | 高（需维护移植代码） | 低（官方代码 + 扩展） |
| **开发周期** | 36 周 | 14 周 |
| **团队要求** | 强 Node.js + Python 全栈 | Python 为主 + 1 名 Node.js |
| **主要风险** | 移植不完整导致能力丢失 | 跨语言通信延迟（可控） |

### B. 参考资源

- [OpenClaw GitHub](https://github.com/openclaw/openclaw)
- [MCP 官方文档](https://modelcontextprotocol.io/)
- [FastMCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

---

*本文档基于"OpenClaw 原生扩展架构"重新编制，开发周期从 36 周缩短至 14 周，同时保留了原计划的 LLM Management Hub 和 Python Skill 生态。*
```