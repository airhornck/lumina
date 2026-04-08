# 本地开发

对齐 **[Development_plan_v2.md](../Development_plan_v2.md)**。

Docker + 热加载 + LLM 密钥：见 **[DOCKER_LOCAL.md](DOCKER_LOCAL.md)**。

## 运行统一 API（编排 + MCP 挂载）

```bash
cd d:\project\lumina
pip install -e ".[dev]"
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 --app-dir apps/api/src
```

- 根目录 `.env` 由 `api.main` 加载；双库 YAML 位于 `data/methodologies/`、`data/platforms/`（相对仓库根目录解析）。

## 单独调试 MCP（stdio）

```bash
python -m skill_hub_app
```

（需已 `pip install -e .`，且 `PYTHONPATH` 与安装布局一致。）

## 调试对话页（流式 + 四能力）

启动 API 后访问：**http://127.0.0.1:8000/debug/chat/**

- 能力：**系统对话（编排 API）** + 四个专项（`内容方向榜单` / `定位决策案例库` / `内容定位矩阵` / `每周决策快照`）；`capability` id 见 `/api/v1/debug/chat/capabilities`
- 后端：`POST /api/v1/debug/chat/stream`（SSE）、`GET/DELETE /api/v1/debug/chat/memory`；系统对话能力 id 为 `system_chat`，可选 **`hub_context`**（与 `/api/v1/marketing/hub` 的 `context` 一致，勿用字段名 `context`）。
- 编排 API `POST /api/v1/marketing/hub` 与 `system_chat` 流式结果中，除 `hub` / `sop` 外新增顶层 **`reply`**：面向用户的自然语言说明（NLG）；无 LLM Key 时为模板兜底。
- **意图**：默认落到 **`conversation`**（自然对话），只有显式「方法论库/框架/AIDA/增长黑客…」等才走 **`general`→方法论检索**；天气/闲聊等会走对话并拒答无关话题（无 Key 时有模板兜底）。

### OpenClaw 侧「意图过滤」如何实现？

OpenClaw **没有**示例里的 `shouldActivate` / `intent.category` 钩子；实际做法是 **工具描述 +（可选）扩展内前置判断**。

本项目已在扩展中增加 **Layer1 意图闸**（`intent-gate.ts`）：在 `fetch` Python 之前拦截明显离题输入，详见 [INTEGRATION_OPENCLAW.md](INTEGRATION_OPENCLAW.md)。Python 编排层仍保留兜底（直连 API / 调试页）。

- **可选**：在 Agent **系统提示**中再次强调「生活类问题不要调 `marketing_intelligence_hub`」；调试用 `LUMINA_DISABLE_INTENT_GATE=1`。
- LLM：在 `llm.yaml` 的 `skill_config.debug_chat` 指定模型，并配置对应环境变量密钥

## 与 OpenClaw 联调

见 [INTEGRATION_OPENCLAW.md](INTEGRATION_OPENCLAW.md)。

## 测试

```bash
pytest tests -q
```
