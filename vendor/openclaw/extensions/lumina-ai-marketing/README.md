# Lumina Marketing Intelligence Hub（OpenClaw 扩展）

**Development_plan_v2 · Layer1**：注册工具 **`marketing_intelligence_hub`**，转发到 Lumina Python：

`POST {LUMINA_PYTHON_URL}/api/v1/marketing/hub`

## Layer1 意图闸

`intent-gate.ts`：明显离题（天气、笑话等）且无营销关键词时**不请求 Python**，返回 `openclaw_intent_gate` 供主模型直接答用户。与 Python `orchestra/core.py` 离题正则保持同步。

- `LUMINA_DISABLE_INTENT_GATE=1` — 关闭闸（仅 OpenClaw Gateway 进程）

## 环境变量

- `LUMINA_PYTHON_URL` — 默认 `http://127.0.0.1:8000`

## OpenClaw 启用

启用插件 `lumina-ai-marketing`，若使用 `tools.allow`，加入 **`marketing_intelligence_hub`**。

## 开发

目录位于 `vendor/openclaw/extensions/lumina-ai-marketing`。在 `vendor/openclaw` 根目录执行 `pnpm install` 后随 workspace 被发现。
