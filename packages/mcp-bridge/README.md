# Lumina MCP Bridge（Node 侧说明）

`Development_plan_v2` 中的 **Layer1 MCP Bridge** 在本仓库实现为 OpenClaw 插件，而非独立 npm 包：

- 路径：`vendor/openclaw/extensions/lumina-ai-marketing/`
- 注册工具名：**`marketing_intelligence_hub`**
- HTTP：`POST {LUMINA_PYTHON_URL}/api/v1/marketing/hub`

若需独立 Node 模块，可将 `index.ts` 中的 `executeMarketingHub` 逻辑抽离到本目录并发布为内部包。
