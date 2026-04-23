# Lumina 本地环境搭建与测试指南（保姆级）

本文档手把手教你从零开始搭建 Lumina 项目的本地开发环境，并运行所有测试验证安装正确性。**不需要 Docker，纯本地 Python 环境即可**。

---

## 目录

1. [前置要求](#1-前置要求)
2. [克隆项目](#2-克隆项目)
3. [创建虚拟环境](#3-创建虚拟环境)
4. [安装依赖](#4-安装依赖)
5. [配置 LLM（关键步骤）](#5-配置-llm关键步骤)
6. [安装 Playwright 浏览器](#6-安装-playwright-浏览器)
7. [验证基础环境](#7-验证基础环境)
8. [运行测试](#8-运行测试)
9. [启动服务](#9-启动服务)
10. [常见问题排查](#10-常见问题排查)

---

## 1. 前置要求

### 必需

| 软件 | 版本要求 | 用途 | 验证命令 |
|------|---------|------|---------|
| **Python** | 3.11+ | 项目运行环境 | `python --version` |
| **Git** | 任意 | 代码版本管理 | `git --version` |
| **pip** | 23.0+ | 包管理 | `pip --version` |

### 推荐（非必需）

| 软件 | 用途 |
|------|------|
| **VS Code** | 代码编辑 + 调试 |
| **PowerShell 7** 或 **Git Bash** | Windows 下更友好的终端体验 |

### 检查 Python 版本

```bash
# Windows
python --version
# 应输出 Python 3.11.x 或更高

# 如果 python 命令不可用，尝试
py --version
```

如果 Python 版本低于 3.11，请从 [python.org](https://www.python.org/downloads/) 下载安装最新版。**安装时务必勾选 "Add Python to PATH"**。

---

## 2. 克隆项目

```bash
# 使用 HTTPS
git clone https://github.com/your-org/lumina.git

# 或使用 SSH
git clone git@github.com:your-org/lumina.git

# 进入项目目录
cd lumina
```

**验证**：项目根目录下应有以下文件/文件夹：

```
lumina/
├── apps/
├── packages/
├── skills/
├── config/
├── data/
├── tests/
├── pyproject.toml
├── README.md
└── .env.example
```

---

## 3. 创建虚拟环境

**强烈建议使用虚拟环境**，避免与系统 Python 包冲突。

### Windows (PowerShell)

```powershell
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
.venv\Scripts\Activate.ps1

# 如果提示执行策略错误，先运行：
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Windows (CMD)

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**验证虚拟环境已激活**：命令行提示符前应有 `(.venv)` 前缀：

```
(.venv) PS D:\project\lumina>
```

---

## 4. 安装依赖

确保虚拟环境已激活，然后运行：

```bash
# 安装项目本身 + 所有依赖 + 开发依赖
pip install -e ".[dev]"
```

这个命令会：
- 安装 `pyproject.toml` 中列出的所有运行时依赖（FastAPI、Pydantic、LiteLLM 等）
- 安装开发依赖（pytest、pytest-asyncio）
- 将项目本身以可编辑模式安装，方便修改代码后即时生效

**安装过程可能需要 2-5 分钟**，取决于网络速度。

### 验证安装

```bash
# 检查关键包是否安装成功
python -c "import fastapi; print(f'FastAPI {fastapi.__version__}')"
python -c "import pydantic; print(f'Pydantic {pydantic.__version__}')"
python -c "import litellm; print('LiteLLM OK')"
python -c "import playwright; print('Playwright OK')"
```

所有命令应输出版本号或 "OK"，没有报错。

---

## 5. 配置 LLM（关键步骤）

Lumina 依赖 LLM 进行内容生成。你可以选择以下任一方式配置：

### 方式 A：使用 DeepSeek（推荐，国内可用）

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/) 注册账号
2. 创建 API Key（通常是 `sk-` 开头）
3. 复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

4. 编辑 `.env` 文件，填入你的 API Key：

```bash
# Windows
notepad .env

# macOS / Linux
nano .env
```

```env
DEEPSEEK_API_KEY=sk-your-actual-key-here
```

### 方式 B：使用 OpenAI

```env
OPENAI_API_KEY=sk-your-openai-key-here
```

### 方式 C：同时使用多个模型（高级）

```env
DEEPSEEK_API_KEY=sk-your-deepseek-key
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-your-anthropic-key
```

### 配置 LLM 池

编辑 `infra/config/llm.yaml`（如不存在则创建）：

```yaml
llm_pool:
  deepseek-v3:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    api_base: https://api.deepseek.com
    temperature: 0.7
    max_tokens: 2000
    timeout: 60

default_llm: deepseek-v3

skill_config:
  generate_text:
    llm: deepseek-v3
  generate_script:
    llm: deepseek-v3
  select_topic:
    llm: deepseek-v3
```

**如果不配置 LLM**：系统仍能运行，但所有 LLM 驱动的 Skill 会返回降级内容（带有 "服务暂时不可用" 的明确提示）。

---

## 6. 安装 Playwright 浏览器

Playwright 用于 RPA 浏览器自动化（账号抓取、二维码登录等）。

```bash
# 安装 Chromium 浏览器
playwright install chromium

# 如果要测试抖音/小红书抓取，可能需要额外安装
playwright install-deps chromium
```

**注意**：`install-deps` 在 Windows 上可能需要管理员权限，且不是必需的。如果后续运行 RPA 测试报错缺少依赖，再执行此步骤。

---

## 7. 验证基础环境

在运行完整测试之前，先进行几个快速验证：

### 7.1 验证 Python 路径配置

```bash
python -c "
import sys
for p in sys.path[:5]:
    print(p)
"
```

确认输出中包含项目源码路径，如 `apps/orchestra/src`、`packages/lumina-skills/src` 等。

### 7.2 验证关键模块导入

```bash
python -c "
from orchestra.core import MarketingOrchestra
from orchestra.agent_orchestrator import AgentOrchestrator
from skill_hub_client import SkillHubClient
from llm_hub import get_client
print('所有核心模块导入成功！')
"
```

### 7.3 验证配置加载

```bash
python -c "
from orchestra.agent_orchestrator import AgentOrchestrator
orch = AgentOrchestrator()
print(f'Agent 数量: {len(orch.agents)}')
print(f'意图映射: {list(orch.intent_agent_map.keys())}')
print(f'执行模式: {{k: v.value for k, v in orch.execution_modes.items()}}')
"
```

预期输出：

```
Agent 数量: 14
意图映射: ['diagnosis', 'content_creation', 'script_creation', ...]
执行模式: {'diagnosis': 'parallel', 'traffic_analysis': 'parallel', 'content_creation': 'serial', ...}
```

---

## 8. 运行测试

测试分为三个层级，建议按顺序执行：

### 8.1 第一层：端到端集成测试（验证完整链路）

这是最推荐的测试，**不需要真实 LLM API Key**（使用 Mock LLM），验证 Agent 编排 → Skill 调用 → LLM 交互的完整链路。

```bash
pytest tests/integration/test_e2e_agent_skill_llm.py -v
```

**预期结果**：17 个测试全部通过。

```
TestAgentOrchestrationE2E::test_diagnosis_parallel_with_llm PASSED
TestAgentOrchestrationE2E::test_content_creation_serial_with_llm PASSED
TestAgentOrchestrationE2E::test_script_creation_serial_with_llm PASSED
TestAgentOrchestrationE2E::test_traffic_analysis_parallel PASSED
TestAgentOrchestrationE2E::test_matrix_setup_mixed PASSED
TestSkillToLLMInvocation::test_select_topic_invokes_llm PASSED
TestSkillToLLMInvocation::test_generate_text_invokes_llm PASSED
TestSkillToLLMInvocation::test_generate_script_invokes_llm PASSED
TestSkillToLLMInvocation::test_match_cases_invokes_llm PASSED
TestSkillToLLMInvocation::test_qa_knowledge_invokes_llm PASSED
TestAgentSkillMapping::test_diagnosis_maps_to_correct_agents PASSED
TestAgentSkillMapping::test_content_creation_maps_to_correct_agents PASSED
TestAgentSkillMapping::test_script_creation_maps_to_correct_agents PASSED
TestAgentSkillMapping::test_traffic_analysis_maps_to_correct_agents PASSED
TestAgentSkillMapping::test_execution_modes_loaded_from_yaml PASSED
TestFallbackBehavior::test_generate_text_fallback_when_llm_unavailable PASSED
TestFallbackBehavior::test_generate_script_fallback_when_llm_unavailable PASSED
```

### 8.2 第二层：Agent 编排单元测试

```bash
pytest tests/test_agent_team.py -v
```

**预期结果**：约 10+ 个测试通过（具体数量随版本变化）。

### 8.3 第三层：Skill 单元测试

```bash
pytest tests/skills/ -v
```

**预期结果**：所有脚本生成相关的 LLM 集成测试通过。

### 8.4 运行全部测试

```bash
pytest tests/ -v
```

**注意**：完整测试套件中可能包含 RPA/Playwright 相关测试，这些测试在 Windows 上可能因 asyncio 管道清理产生无害的警告信息，不影响测试结果。

---

## 9. 启动服务

### 9.1 启动 API 服务

```bash
# 确保在项目根目录，且虚拟环境已激活
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir apps/api/src
```

服务启动后，访问以下地址验证：

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:8000/health | 健康检查，应返回 `{"status":"ok"}` |
| http://127.0.0.1:8000/docs | Swagger API 文档 |
| http://127.0.0.1:8000/debug/chat/ | Web 调试聊天界面 |

### 9.2 测试 API 接口

使用 curl 或 Postman 测试营销中枢接口：

```bash
# 账号诊断（需要配置 LLM 才能生成完整结果）
curl -X POST http://127.0.0.1:8000/api/v1/marketing/hub \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "帮我诊断一下账号",
    "user_id": "test_001",
    "platform": "xiaohongshu",
    "context": {
      "account_url": "https://www.xiaohongshu.com/user/demo123"
    }
  }'
```

```bash
# 内容生成（需要配置 LLM）
curl -X POST http://127.0.0.1:8000/api/v1/marketing/hub \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "帮我写一篇小红书种草文案",
    "user_id": "test_002",
    "platform": "xiaohongshu"
  }'
```

```bash
# 脚本生成（需要配置 LLM）
curl -X POST http://127.0.0.1:8000/api/v1/marketing/hub \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "帮我写一个60秒的短视频脚本",
    "user_id": "test_003",
    "platform": "douyin"
  }'
```

**未配置 LLM 时的行为**：所有接口都会正常返回，但 LLM 驱动的部分会带有 "服务暂时不可用" 的降级提示。这是预期行为，不代表安装失败。

---

## 10. 常见问题排查

### Q1: `pip install -e ".[dev]"` 报错

**现象**：

```
ERROR: Could not build wheels for xxx
```

**解决**：

```bash
# 升级 pip、setuptools、wheel
pip install --upgrade pip setuptools wheel

# 重新安装
pip install -e ".[dev]"
```

### Q2: `ModuleNotFoundError: No module named 'orchestra'`

**现象**：运行测试时报模块找不到。

**原因**：pytest 的 `pythonpath` 配置未生效，或虚拟环境未激活。

**解决**：

```bash
# 确认虚拟环境已激活
which python  # macOS/Linux
where python  # Windows

# 确认路径中包含项目源码
python -c "import sys; print('\n'.join(sys.path))"

# 手动运行测试时指定路径
pytest tests/ --pythonpath="apps/orchestra/src;packages/lumina-skills/src" -v
```

### Q3: Windows 上 pytest 报 `ValueError: I/O operation on closed pipe`

**现象**：测试通过后出现警告：

```
PytestUnraisableExceptionWarning: Exception ignored while calling deallocator ...
ValueError: I/O operation on closed pipe
```

**原因**：Python 3.11+ 在 Windows 上的 asyncio Proactor 事件循环清理问题，与 Playwright 子进程有关。

**解决**：这是**无害的警告**，不影响测试结果。可以忽略，或通过以下方式抑制：

```bash
pytest tests/ -v -W ignore::pytest.PytestUnraisableExceptionWarning
```

### Q4: LLM 调用报错 `No API key provided`

**现象**：测试或 API 调用时返回降级内容（"服务暂时不可用"）。

**解决**：

1. 确认 `.env` 文件存在且包含有效的 API Key
2. 确认 `infra/config/llm.yaml` 中 `api_key` 使用 `${ENV_VAR}` 语法引用了正确的环境变量
3. 确认运行前加载了环境变量（某些 IDE 需要重启才能读取新的 `.env`）

```bash
# 验证环境变量已加载
python -c "import os; print(os.getenv('DEEPSEEK_API_KEY', 'NOT SET'))"
```

### Q5: Playwright `browser_type.launch()` 报错

**现象**：RPA 相关测试报错浏览器找不到。

**解决**：

```bash
# 重新安装浏览器
playwright install chromium

# 如果仍报错，尝试安装系统依赖（Windows 可能需要管理员权限）
playwright install-deps
```

### Q6: `ImportError: cannot import name 'get_client' from 'llm_hub'`

**现象**：导入 llm_hub 时报错。

**解决**：

```bash
# 确认 llm-hub 包已安装
pip list | findstr llm-hub  # Windows
pip list | grep llm-hub     # macOS/Linux

# 如果未安装，手动安装
pip install -e packages/llm-hub
```

### Q7: 测试超时

**现象**：运行全部测试时某些测试卡住不动。

**原因**：RPA/Playwright 测试尝试真实启动浏览器，耗时较长。

**解决**：

```bash
# 只运行核心测试（排除 RPA）
pytest tests/integration/ tests/test_agent_team.py tests/skills/ -v

# 或使用超时限制
pytest tests/ -v --timeout=60
```

---

## 附录 A：VS Code 推荐配置

在项目根目录创建 `.vscode/settings.json`：

```json
{
  "python.defaultInterpreterPath": "./.venv/Scripts/python.exe",
  "python.analysis.extraPaths": [
    "apps/api/src",
    "apps/orchestra/src",
    "apps/rpa/src",
    "packages/llm-hub/src",
    "packages/knowledge-base/src",
    "packages/lumina-skills/src",
    "packages/skill-hub-client/src",
    "packages/sop-engine/src"
  ],
  "python.testing.pytestArgs": ["tests"],
  "python.testing.unittestEnabled": false,
  "python.testing.pytestEnabled": true
}
```

---

## 附录 B：快速测试清单

每次修改代码后，运行以下命令快速验证：

```bash
# 1. 端到端测试（最全面，约 15 秒）
pytest tests/integration/test_e2e_agent_skill_llm.py -v

# 2. Agent 编排测试（约 5 秒）
pytest tests/test_agent_team.py -v

# 3. Skill 单元测试（约 10 秒）
pytest tests/skills/ -v
```

全部通过后，可以提交代码。

---

## 附录 C：项目配置文件速查

| 文件 | 作用 | 是否需要修改 |
|------|------|------------|
| `.env` | API Key、数据库密码等敏感信息 | ✅ 必须 |
| `infra/config/llm.yaml` | LLM 模型池配置 | ✅ 推荐 |
| `config/agents.yaml` | Agent 定义与编排规则 | 可选 |
| `config/intent_rules.yaml` | 意图匹配规则 | 可选 |
| `data/platforms/*.yml` | 平台规范（DNA/审核/格式） | 按需 |
| `data/methodologies/*.yml` | 方法论框架 | 按需 |

---

**如有其他问题，请提交 Issue 或在 README 中查找相关文档链接。**
