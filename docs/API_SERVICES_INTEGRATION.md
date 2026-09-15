# Lumina 统一服务 API 对接文档

> **版本**：v2.0  
> **日期**：2026-07-26  
> **适用范围**：Lumina 对外服务层统一入口  
> **Base URL**：`http://<host>:<port>`（本地开发默认 `http://127.0.0.1:8000`）

> **说明**：本文档按 HTTP API 方式组织，描述当前有效的服务端点、请求/响应字段与 cURL 示例。历史 4 个独立服务流已收敛为 `system-chat` 统一入口；已下线服务调用会返回 `410 Gone`。

---

## 1. 接口概述

### 1.1 当前服务能力

| 中文能力名 | Service ID | 端点 | 说明 |
|-----------|------------|------|------|
| 系统对话（统一入口） | `system-chat` | `POST /api/v1/services/system-chat/stream` | Hermes Agent 唯一执行引擎；爆款榜单、定位矩阵、每周决策快报等能力以 Skill / Agent 形式通过自然语言意图唤起 |
| 跨平台内容生成 | `cross-platform-content` | `POST /api/v1/services/cross-platform-content/stream` | 直接编排 LLM + PlatformRegistry + MethodologyRegistry，按平台分块返回 |
| ~~内容方向榜单~~ | ~~`content-ranking`~~ | ~~`POST /api/v1/services/content-ranking/stream`~~ | ❌ 已下线，返回 `410 Gone` |
| ~~定位服务~~ | ~~`positioning`~~ | ~~`POST /api/v1/services/positioning/stream`~~ | ❌ 已下线，返回 `410 Gone` |
| ~~每周决策快照~~ | ~~`weekly-snapshot`~~ | ~~`POST /api/v1/services/weekly-snapshot/stream`~~ | ❌ 已下线，返回 `410 Gone` |

### 1.2 核心特性

- **统一对外入口**：所有对话类能力统一收敛到 `system-chat`，通过自然语言意图调用底层 Skill / Agent。
- **统一请求体**：`POST /stream` 端点共用 `ServiceStreamRequest` 结构。
- **记忆隔离**：按 `(user_id, conversation_id, service)` 三元组隔离，不同用户、不同对话、不同服务之间互不串扰。
- **记忆管理 API**：支持按 service 查询与清空记忆。

### 1.3 认证与信任边界

- 登录与鉴权由**平台侧**完成，**Lumina 不校验调用方身份**，无 Token、无签名。
- `user_id` 视为平台侧可信输入，Lumina 仅做透传与数据隔离。
- 前提：Lumina 服务仅暴露于内网/网关之后。

---

## 2. 通用规范

### 2.1 基础信息

- **Base URL**：`http://<host>:<port>`（默认本地 `http://127.0.0.1:8000`）
- **协议**：HTTP/1.1 或 HTTP/2（SSE 需确保支持流式）
- **Content-Type**：`application/json`（请求） / `text/event-stream; charset=utf-8`（流式响应）
- **字符编码**：UTF-8

### 2.2 统一请求体 `ServiceStreamRequest`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | `string` | 是 | 用户唯一标识，长度 1-128 |
| `conversation_id` | `string` | 是 | 对话唯一标识，长度 1-128 |
| `message` | `string` | 是 | 用户当前输入，长度 1-32000 |
| `platform` | `string` | 否 | 平台上下文，如 `xiaohongshu`、`douyin` |
| `context` | `object` | 否 | 业务上下文；仅 `system-chat` 会透传给 Hermes 引擎 |
| `mode` | `string` | 否 | 已下线，无需传入 |
| `stream_format` | `int` | 否 | `1` 或 `2`；缺省读请求头 `X-Lumina-Stream-Format`；均未指定默认 `1`。`system-chat` 实际产出 v2 格式 |

### 2.3 ID 约定

| 参数 | 取值规则 |
|---|---|
| `user_id` | 平台登录态下发的用户唯一标识 |
| `conversation_id` | 单对话窗口形态建议固定为 `"main"` |

---

## 3. 服务流式对话 `POST /api/v1/services/{service}/stream`

### 3.1 `system-chat`（统一入口）

#### 端点

```http
POST /api/v1/services/system-chat/stream
```

#### 功能

Hermes Agent 为唯一执行引擎，走理解 → 规划 → 工具调用 → 回复链路。爆款榜单、定位矩阵、每周决策快报等能力已通过 Skill / Agent 挂载，前端只需发送自然语言即可唤起。

#### 请求示例

```bash
curl -N -X POST http://localhost:8000/api/v1/services/system-chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u_abc123",
    "conversation_id": "main",
    "message": "帮我诊断一下账号",
    "platform": "xiaohongshu",
    "context": {
      "industry": "美妆",
      "account_url": "https://xiaohongshu.com/user/profile/xxx"
    }
  }'
```

#### SSE 事件流（v2）

```
start → thinking_delta* / tool_start* / tool_complete* / assistant_delta*
      → export_link* / compliance_report? → done
（异常路径：error，出现后流结束）
```

| 事件 type | 字段 | 说明 |
|---|---|---|
| `start` | `service`, `stream_format`(=2), `request_id` | 流开始 |
| `thinking_delta` | `text` | 模型思考过程增量 |
| `tool_start` | `tool`, `args` | 工具调用开始 |
| `tool_complete` | `tool`, `ok`, `elapsed_ms` | 工具调用完成 |
| `assistant_delta` | `text` | 回复文本增量 |
| `export_link` | `format`, `url`, `platform`, `variant`, `title`, `summary`, `platform_required_content` | 内容导出链接 |
| `compliance_report` | `risk_level`, `risk_categories`, `violations`, `suggestion`, `format`, `report_md` | 合规报告 |
| `done` | `service`, `request_id`, `full_length`, `conversation_id`, `usage`, `reply_ms`, `payload` | 流正常结束 |
| `error` | `service`, `request_id`, `message` | 流异常结束 |

`done.payload` 结构（仅在有导出/合规时出现）：`{ has_content?: bool, content_urls?: array, compliance?: object }`。

#### 典型 SSE 返回

```text
data: {"type": "start", "service": "system-chat", "stream_format": 2, "request_id": "..."}

data: {"type": "tool_start", "tool": "diagnose_account", "args": {"platform": "xiaohongshu"}}

data: {"type": "tool_complete", "tool": "diagnose_account", "ok": true, "elapsed_ms": 1200}

data: {"type": "assistant_delta", "text": "根据诊断"}

data: {"type": "assistant_delta", "text": "，你的账号目前..."}

data: {"type": "done", "service": "system-chat", "request_id": "...", "full_length": 256, "conversation_id": "main", "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}, "reply_ms": 2300, "payload": {}}
```

---

### 3.2 `cross-platform-content`

#### 端点

```http
POST /api/v1/services/cross-platform-content/stream
```

#### 功能

接收选题种子或用户描述，按平台分块返回适合小红书、抖音、B站等的差异化内容版本。

#### 请求示例

```bash
curl -N -X POST http://localhost:8000/api/v1/services/cross-platform-content/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u123",
    "conversation_id": "c456",
    "message": "生成职场穿搭内容",
    "context": {
      "target_platforms": ["xiaohongshu", "douyin", "bilibili"],
      "content_type": "图文",
      "industry": "职场"
    }
  }'
```

#### SSE 事件流

```
start → platform_chunk* / warning* / error* → done
```

| 事件 type | 字段 | 说明 |
|---|---|---|
| `start` | `service`, `platforms` | 开始生成 |
| `platform_chunk` | `platform`, `content` | 单个平台内容生成完毕，`platform` 可能为 `"master"` 或具体平台 |
| `warning` | `platform`, `warnings` | 合规扫描命中敏感词 |
| `error` | `message` | 生成失败 |
| `done` | `total_platforms`, `full_length`, `payload` | 全部完成 |

详细 `content` 字段说明见 [4.22_API_REFERENCE.md](./4.22_API_REFERENCE.md) §3.5。

---

## 4. 记忆管理 API

### 4.1 隔离模型

记忆在服务端按 **三元组** 隔离：

```
(user_id, conversation_id, service)
```

### 4.2 查询记忆

```http
GET /api/v1/services/{service}/memory?user_id={uid}&conversation_id={cid}
```

支持分页参数 `limit` / `offset` / `order`，详见 [CONVERSATION_HISTORY_API.md](./CONVERSATION_HISTORY_API.md) §3.1。

#### 响应示例

```json
{
  "user_id": "u_abc123",
  "conversation_id": "main",
  "service": "system-chat",
  "count": 4,
  "messages": [
    { "role": "user", "content": "帮我排一下方向", "ts": "2026-07-15T05:00:00+00:00" },
    { "role": "assistant", "content": "本周 TOP 3 方向为...", "ts": "2026-07-15T05:00:05+00:00" }
  ],
  "total": 4,
  "has_more": false
}
```

### 4.3 清空记忆

```http
DELETE /api/v1/services/{service}/memory?user_id={uid}&conversation_id={cid}
```

#### 响应示例

```json
{
  "ok": true,
  "cleared": true,
  "service": "system-chat"
}
```

---

## 5. 客户端对接指南

### 5.1 对接 checklist

1. **维护两个 ID**：`user_id`（用户级）和 `conversation_id`（对话级），切换任一 ID 即视为不同上下文。
2. **统一使用 `system-chat`**：所有对话类能力走 `POST /api/v1/services/system-chat/stream`。
3. **SSE 解析必须兼容分片**：同一条事件可能跨多次 `read()`，需用缓冲区按 `\n\n` 分割。
4. **不传历史**：服务端自动读取最近 24 条作为上下文，前端无需重复上传历史。
5. **`context` 校验**：发起前建议做 `JSON.parse` 校验，避免服务端报 422。

### 5.2 JavaScript 对接示例（Fetch + SSE）

```javascript
async function streamChat(service, payload, handlers = {}, { signal } = {}) {
  const res = await fetch(`/api/v1/services/${service}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  const dispatch = (ev) => {
    if (ev.type === "assistant_delta") handlers.onDelta?.(ev.text);
    else if (ev.type === "done") handlers.onDone?.(ev);
    else if (ev.type === "error") handlers.onError?.(new Error(ev.message), ev);
    else if (ev.type === "export_link") handlers.onExportLink?.(ev);
    else if (ev.type === "compliance_report") handlers.onCompliance?.(ev);
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of block.split("\n")) {
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (!payload) continue;
          try { dispatch(JSON.parse(payload)); } catch { /* 忽略坏帧 */ }
        }
      }
    }
  } catch (e) {
    if (e?.name !== "AbortError") handlers.onError?.(e);
  }
}

// 使用示例
let draft = "";
await streamChat("system-chat", {
  user_id: "u_001",
  conversation_id: "main",
  message: "帮我诊断一下账号",
  platform: "xiaohongshu",
}, {
  onDelta: (text) => { draft += text; updateBubble(draft); },
  onDone:  ()     => finalizeBubble(),
  onError: (err)  => showToast(err.message),
});
```

---

## 6. 错误码与处理

### 6.1 HTTP 状态码

| 状态码 | 场景 | 建议处理 |
|--------|------|----------|
| `200` | 正常返回（流式或非流式） | 按 SSE 或 JSON 解析 |
| `400` | `service` 不存在 / 请求体校验失败 | 检查 URL 与请求体字段 |
| `410` | 请求已下线的服务（`content-ranking` / `positioning` / `weekly-snapshot`） | 改用 `system-chat` 统一入口 |
| `422` | Pydantic 校验失败（如 `message` 为空、`context` 不是对象） | 检查请求体格式与类型 |
| `500` | 服务端内部异常 | 查看服务端日志排查 |

### 6.2 SSE `error` 事件常见原因

| 错误信息 | 原因 | 解决方式 |
|---------|------|----------|
| `LLM Hub 未初始化` | `infra/config/llm.yaml` 缺失或格式错误 | 检查配置文件路径与内容 |
| `无法获取 LLM 客户端` | `llm.yaml` 中未配置对应 skill | 检查 `llm.yaml` 的 `skill_config` 节点 |
| `LLM 客户端缺少 API Key` | 环境变量未设置对应 Key | 设置 `DEEPSEEK_API_KEY` 或对应 Key |
| `Hermes engine error: ...` | Hermes 引擎内部异常 | 查看服务端详细堆栈 |

---

## 7. 服务启动与验证

### 7.1 启动服务

```bash
python -m uvicorn api.main:app --app-dir apps/api/src --port 8000 --reload
```

### 7.2 健康检查

```bash
curl http://localhost:8000/health
```

### 7.3 快速 curl 验证

```bash
# 1. 查询记忆（应为空）
curl "http://localhost:8000/api/v1/services/system-chat/memory?user_id=u1&conversation_id=main"

# 2. 发起流式对话
curl -N -X POST http://localhost:8000/api/v1/services/system-chat/stream \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","conversation_id":"main","message":"hello"}'

# 3. 清除记忆
curl -X DELETE "http://localhost:8000/api/v1/services/system-chat/memory?user_id=u1&conversation_id=main"
```

---

## 8. 关联文档

| 文档 | 说明 |
|------|------|
| [CONVERSATION_HISTORY_API.md](./CONVERSATION_HISTORY_API.md) | 对话历史 HTTP API 详细说明（memory / stream / delete） |
| [4.22_API_REFERENCE.md](./4.22_API_REFERENCE.md) | Demo 工作台接口文档（定位矩阵、本周榜单、跨平台内容生成） |
| [LUMINA_BUSINESS_SOURCE_OF_TRUTH.md](./LUMINA_BUSINESS_SOURCE_OF_TRUTH.md) | 业务真源与 Skill / Agent 挂载说明 |

---

## 9. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v1.0 | 2026-04 | 初版：4 个独立对外服务流 API |
| v1.1 | 2026-05 | 标记为废弃，建议前端使用 SDK 文档 |
| **v2.0** | **2026-07-26** | **重新激活为 HTTP API 文档**：4 个独立服务流收敛为 `system-chat` 统一入口；移除 SDK 引用；按 REST 端点、字段、cURL 示例重新组织；已下线服务统一返回 `410 Gone` |
