# Lumina - AI 营销助手

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Lumina 是一个面向小红书、抖音等内容平台的 AI 营销助手，采用四层架构设计（OpenClaw 基座 → 多 Agent 中枢 → MCP Skill Hub → 双库体系），提供账号诊断、流量分析、内容生成、选题建议等核心能力。

## 核心特性

- **账号基因诊断** - 分析账号定位、内容DNA、健康度评分
- **流量结构分析** - 曝光/互动漏斗分析、掉粉原因诊断
- **内容智能生成** - 文案、标题、短视频脚本创作
- **选题方向建议** - 基于行业画像的个性化选题推荐
- **平台规范检查** - 风险检测、合规审核、敏感词过滤
- **方法论 SOP** - AIDA、增长黑客等可配置化营销框架

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: 双库体系（知识资产层）                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │  方法论库    │ │  平台规范库  │ │  用户策略记忆│             │
│  │ (AIDA/定位/  │ │ (小红书/抖音 │ │ (效果数据驱动│             │
│  │  增长黑客等) │ │  /B站等)     │ │  进化)       │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: MCP Skill Hub（原子能力执行层）- FastMCP 实现          │
│  ┌──────────┬──────────┬──────────┬──────────────────┐          │
│  │ 诊断类   │ 内容类   │ 资产类   │ 工具类           │          │
│  ├──────────┼──────────┼──────────┼──────────────────┤          │
│  │账号诊断  │文案生成  │方法论检索│行业新闻抓取      │          │
│  │流量分析  │脚本创作  │案例匹配  │竞品监测          │          │
│  │风险评估  │选题生成  │知识库问答│数据可视化        │          │
│  └──────────┴──────────┴──────────┴──────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              ↑ MCP Protocol
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2: 多 Agent 中枢（编排决策层）- Python                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  SOP 编排引擎（DAG 执行器）                                │  │
│  │  • 加载方法论 → 编译为 DAG → 调度 Agent → 调用 Skill Hub  │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  多 Agent 协作系统（Blackboard 架构）                       │  │
│  │  诊断Agent → 策略Agent → 创意Agent → 审核Agent             │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↑ HTTP API
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: 接入层（FastAPI）                                      │
│  • REST API /api/v1/marketing/hub                               │
│  • MCP Streamable HTTP /mcp                                     │
│  • WebSocket 调试界面 /debug/chat/                              │
└─────────────────────────────────────────────────────────────────┘
```

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

# 4. 启动服务
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

## 项目结构

```
lumina/
├── apps/
│   ├── api/              # FastAPI 主服务（接入层）
│   ├── orchestra/        # Layer2 编排中枢
│   ├── skill-hub/        # Layer3 MCP Skill Hub
│   ├── intent/           # 意图识别引擎
│   └── rpa/              # 浏览器自动化
├── packages/
│   ├── lumina-skills/    # 原子 Skill 实现
│   ├── knowledge-base/   # 方法论库 + 平台规范库
│   ├── llm-hub/          # LLM 池管理
│   ├── skill-hub-client/ # Skill 调用客户端
│   ├── sop-engine/       # SOP DAG 编译器
│   └── agent-core/       # Agent 基类与上下文
├── data/
│   ├── methodologies/    # 方法论 YAML 配置
│   └── platforms/        # 平台规范 YAML 配置
├── infra/
│   └── config/
│       └── llm.yaml      # LLM 模型配置
├── tests/                # 测试套件
├── docs/                 # 架构文档
├── scripts/              # 启动脚本
└── static/debug_chat/    # Web 调试界面
```

## 配置说明

### LLM 配置

编辑 `infra/config/llm.yaml` 配置模型：

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

# 默认模型
default_llm: deepseek-v3

# Skill 级别模型分配
skill_config:
  debug_chat:
    llm: deepseek-v3
  generate_text:
    llm: deepseek-v3
```

### 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | 推荐 |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 可选 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | 可选 |
| `LLM_CONFIG_PATH` | LLM 配置文件路径 | 可选 |
| `LUMINA_PORT` | 服务端口（默认 8000） | 可选 |

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

## 开发指南

### 添加新 Skill

1. 在 `packages/lumina-skills/src/lumina_skills/` 实现 Skill 函数
2. 在 `packages/lumina-skills/src/lumina_skills/registry.py` 注册
3. 更新 `apps/skill-hub/src/skill_hub_app/factory.py` 挂载到 MCP

### 运行测试

```bash
# 运行所有测试
pytest tests -v

# 运行特定测试
pytest tests/test_marketing_hub.py -v
```

## 相关文档

- [架构文档](docs/ARCHITECTURE.md) - 系统架构设计
- [开发计划](Development_plan_v2.md) - 详细开发规划
- [Docker 部署](docs/DOCKER_DEPLOYMENT.md) - 生产部署指南
- [OpenClaw 集成](docs/INTEGRATION_OPENCLAW.md) - 与 OpenClaw 集成

## 技术栈

- **Web 框架**: FastAPI
- **MCP 协议**: FastMCP
- **LLM 调用**: LiteLLM
- **配置管理**: Pydantic + PyYAML
- **测试**: pytest + pytest-asyncio

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**注意**: 本项目正在积极开发中，API 可能会有变动。欢迎提交 Issue 和 PR！
