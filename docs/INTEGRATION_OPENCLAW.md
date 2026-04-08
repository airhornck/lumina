# Lumina × OpenClaw 联调说明（Development_plan_v2）

## 架构

1. **OpenClaw**（`vendor/openclaw`）：对话、Session、ReAct。  
2. **扩展** `extensions/lumina-ai-marketing`：注册唯一工具 **`marketing_intelligence_hub`** → `POST {LUMINA_PYTHON_URL}/api/v1/marketing/hub`。  
3. **Python**（`apps/api` + `apps/orchestra` + `packages/lumina-skills`）：编排层根据意图调用 **Skill Hub**（同进程 `SkillHubClient`）；FastMCP 同时在 **`/mcp`** 暴露相同工具集。

### OpenClaw 侧「意图闸」（Layer1）

OpenClaw **没有**独立的 `intent.category` / `shouldActivate` API；模型的「意图」主要体现在 **是否选择调用某个 tool**。本仓库在扩展里实现了 **调用 Python 之前的轻量闸**（与编排层离题规则对齐）：

- 文件：`vendor/openclaw/extensions/lumina-ai-marketing/intent-gate.ts`  
- 行为：命中明显**生活/离题**（天气、笑话、吃饭等）且句内**无营销锚点**时，**不发起 HTTP**，直接返回 `source: openclaw_intent_gate` + `reply` / `agent_note`，由主模型按说明自行回答用户。  
- 关闭闸（调试）：环境变量 **`LUMINA_DISABLE_INTENT_GATE=1`**（仅 Gateway 进程需设置）。  
- **寒暄（如「你好」）仍会请求 Python**，由编排层 `conversation` 处理；与闸规则一致（闸只挡离题，不挡寒暄）。

## 启动顺序

1. `python -m uvicorn api.main:app --app-dir apps/api/src --port 8000`  
2. `GET /health`  
3. 启动 OpenClaw Gateway（参见 vendor 内文档）。

## 环境变量

| 变量 | 作用 |
|------|------|
| `LUMINA_PYTHON_URL` | Bridge 请求的 API 根 URL，默认 `http://127.0.0.1:8000` |
| `LLM_CONFIG_PATH` | 默认 `infra/config/llm.yaml` |
| `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / `ANTHROPIC_API_KEY` | 与 `llm.yaml` 占位符一致 |

## 工具参数（`marketing_intelligence_hub`）

- **user_input**（必填）：用户当前轮文本  
- **user_id**：可选，默认 `anonymous`  
- **platform**：如 `xiaohongshu`、`douyin`、`bilibili`  
- **session_history**：可选，最近消息摘要列表  
- **context**：可选，如 `metrics`、`industry`、`account_url`、`content_dna` 等，会并入编排上下文  

## 启用插件与工具

```json
{
  "plugins": {
    "entries": {
      "lumina-ai-marketing": {
        "enabled": true
      }
    }
  }
}
```

若使用 **`tools.allow`** 白名单，请**追加** `marketing_intelligence_hub`（并保留其他必需工具）。详见 vendor 内 `docs/tools/plugin.md`、`docs/plugins/agent-tools.md` 与 [Plugins](https://docs.openclaw.ai/tools/plugin)。
