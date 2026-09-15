# Lumina 对话 API 对接文档（HTTP 协议版）

| 项目 | 内容 |
|---|---|
| 版本 | v3.0 |
| 日期 | 2026-07-26 |
| 适用范围 | 直接调用 HTTP 接口的前端 / 客户端 / 服务端 |
| Base URL | `http://<host>:<port>`（本地开发默认 `http://127.0.0.1:8000`） |

> **说明**：本文档为纯 HTTP API 协议真源，按 REST 端点、请求/响应字段、cURL 示例组织。如需 SDK 封装，可参考仓库内的 `static/sdk/luminaChatClient.js`。

---

## 1. 概述

### 1.1 能力一览

通过 3 个 HTTP 接口实现单对话窗口的完整闭环：**加载历史 → 继续对话 → （可选）加载更早 / 清除历史**。

| 能力 | 接口 | 响应形式 |
|---|---|---|
| 查询对话历史 | `GET /api/v1/services/{service}/memory` | 一次性 JSON |
| 发送消息（流式回复） | `POST /api/v1/services/{service}/stream` | SSE 流（`text/event-stream`） |
| 清除对话历史 | `DELETE /api/v1/services/{service}/memory` | 一次性 JSON |

- `{service}` 当前固定使用 `system-chat`（统一对外入口）。`cross-platform-content` 仍保留但非服务流核心。
- 以下独立服务流已下线，调用会返回 `410 Gone`：`content-ranking`、`positioning`、`weekly-snapshot`。

### 1.2 认证与信任边界

- 登录与鉴权由**平台侧**完成，**Lumina 不校验调用方身份**，无 Token、无签名。
- `user_id` 视为平台侧可信输入，Lumina 仅做透传与数据隔离。
- 前提：Lumina 服务仅暴露于内网/网关之后。任何知道 `user_id` 的请求方都能读取该用户历史，请确保 `user_id` 不可被遍历猜测。

### 1.3 ID 约定（必须遵守）

| 参数 | 取值规则 |
|---|---|
| `user_id` | 平台登录态下发的用户唯一标识，同一用户保持稳定 |
| `conversation_id` | **固定值 `"main"`**（单对话窗口形态，一个用户一条会话） |

---

## 2. 通用规范

### 2.1 基础信息

- **Base URL**：`http://<host>:<port>`（默认本地 `http://127.0.0.1:8000`）
- **协议**：HTTP/1.1 或 HTTP/2（SSE 需确保支持流式）
- **请求 Content-Type**：`application/json`
- **流式响应 Content-Type**：`text/event-stream; charset=utf-8`
- **字符编码**：UTF-8

### 2.2 `{service}` 取值

| 值 | 状态 | 说明 |
|---|---|---|
| `system-chat` | ✅ 当前唯一对外主入口 | Hermes Agent 统一执行引擎 |
| `cross-platform-content` | ✅ 保留 | 跨平台内容生成，SSE 事件契约与 `system-chat` 不同，见 §3.2.2 |
| `content-ranking` | ❌ 已下线 | 返回 `410 Gone` |
| `positioning` | ❌ 已下线 | 返回 `410 Gone` |
| `weekly-snapshot` | ❌ 已下线 | 返回 `410 Gone` |

### 2.3 通用错误

| HTTP 状态码 | 场景 |
|---|---|
| `400` | `service` 非法，或请求参数校验失败 |
| `410` | 请求已下线的服务（`content-ranking` / `positioning` / `weekly-snapshot`） |
| `422` | 缺少必填参数或参数类型/约束不满足（Pydantic 校验失败） |
| `500` | 服务端内部错误 |

---

## 3. 接口详情

### 3.1 查询对话历史 `GET /api/v1/services/{service}/memory`

**请求参数**

| 参数 | 位置 | 必填 | 类型 | 默认 | 说明 |
|---|---|---|---|---|---|
| `user_id` | query | 是 | string | — | 用户唯一标识，min_length=1 |
| `conversation_id` | query | 是 | string | — | 对话唯一标识，min_length=1 |
| `limit` | query | 否 | int | — | 取**最新** N 条（1-1000）；**不传则返回全部** |
| `offset` | query | 否 | int | `0` | 跳过最新 N 条（向更早翻页），仅在传 `limit` 时有意义 |
| `order` | query | 否 | string | `asc` | 返回顺序：`asc` 时间正序 / `desc` 时间倒序 |

> 分页语义为"最新优先"：`limit=50` 取最新 50 条；`limit=50&offset=50` 取再早的 50 条。无论何种分页，默认均按时间正序返回（`order` 仅翻转返回顺序，不影响"最新优先"的选取逻辑）。

**响应字段**

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_id` | string | 用户唯一标识 |
| `conversation_id` | string | 对话唯一标识 |
| `service` | string | 服务名称 |
| `count` | int | 本次返回的消息条数 |
| `messages` | array\<object\> | 消息列表 |
| `messages[].role` | string | `user` / `assistant` / `system` |
| `messages[].content` | string | 消息内容 |
| `messages[].ts` | string | 创建时间，ISO 8601（UTC） |
| `messages[].capability` | string，可选 | 产生该消息的能力标识，无则缺省 |
| `total` | int | 该会话消息总数 |
| `has_more` | bool | 是否还有更早的消息（`offset + count < total`） |

**示例 1：页面加载（最新 50 条）**

```bash
curl "http://127.0.0.1:8000/api/v1/services/system-chat/memory?user_id=u_10086&conversation_id=main&limit=50"
```

```json
{
  "user_id": "u_10086",
  "conversation_id": "main",
  "service": "system-chat",
  "count": 50,
  "messages": [
    { "role": "user", "content": "帮我写一篇小红书种草笔记", "ts": "2026-07-15T08:30:00+00:00" },
    { "role": "assistant", "content": "好的，这是为你生成的笔记……", "ts": "2026-07-15T08:30:12+00:00" }
  ],
  "total": 1320,
  "has_more": true
}
```

**示例 2：加载更早（第 2 页）**

```bash
curl "http://127.0.0.1:8000/api/v1/services/system-chat/memory?user_id=u_10086&conversation_id=main&limit=50&offset=50"
```

**示例 3：无历史（首次使用）**

```json
{
  "user_id": "u_10086",
  "conversation_id": "main",
  "service": "system-chat",
  "count": 0,
  "messages": [],
  "total": 0,
  "has_more": false
}
```

---

### 3.2 发送消息 `POST /api/v1/services/{service}/stream`（SSE）

**请求体字段**

| 字段 | 必填 | 类型 | 约束 | 说明 |
|---|---|---|---|---|
| `user_id` | 是 | string | 1-128 字符 | 用户唯一标识 |
| `conversation_id` | 是 | string | 1-128 字符 | 固定约定值，如 `"main"` |
| `message` | 是 | string | 1-32000 字符 | 用户当前输入 |
| `platform` | 否 | string | — | 平台上下文，如 `xiaohongshu` / `douyin` |
| `context` | 否 | object | — | 业务上下文（行业、指标、DNA 等），默认 `{}`；仅 `system-chat` 会透传给 Hermes 引擎 |
| `mode` | 否 | string | — | 已下线，无需传入 |
| `stream_format` | 否 | int | `1` 或 `2` | 缺省读请求头 `X-Lumina-Stream-Format`；均未指定则默认 `1`。`system-chat` 实际产出 v2 格式 |

> 服务端自动读取该会话历史作为模型上下文（最近 24 条），**前端无需也不应重复传历史**。

**请求示例**

```bash
curl -N -X POST "http://127.0.0.1:8000/api/v1/services/system-chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u_10086","conversation_id":"main","message":"改成更口语化的风格","platform":"xiaohongshu"}'
```

#### 3.2.1 `system-chat` SSE 事件流（v2）

响应为 `text/event-stream`，每条事件格式为 `data: {json}\n\n`（`\n\n` 为帧分隔符）。事件按以下顺序出现：

```
start → thinking_delta* / tool_start* / tool_complete* / assistant_delta*
      → export_link* / compliance_report? → done
（异常路径：error，出现后流结束；* 表示可出现 0 到多次）
```

| 事件 type | 字段 | 说明 | 前端处理建议 |
|---|---|---|---|
| `start` | `service`, `stream_format`(=2), `request_id` | 流开始 | 可忽略或展示请求标识 |
| `thinking_delta` | `text` | 模型思考过程增量（可多次） | 可忽略，或展示"思考中" |
| `tool_start` | `tool`, `args` | 工具调用开始（可多次） | 可选展示"正在调用 xx 工具" |
| `tool_complete` | `tool`, `ok`, `elapsed_ms` | 工具调用完成 | 可选展示 |
| `assistant_delta` | `text` | **回复文本增量**（多次，拼接即完整回复） | **必须处理**：追加渲染气泡 |
| `export_link` | `format`(="html"), `url`, `platform`, `variant`, `title`, `summary`, `platform_required_content` | 内容导出链接（0 到多个） | 建议渲染为下载卡片 |
| `compliance_report` | `risk_level`, `risk_categories`, `violations`, `suggestion`, `format`(="markdown"), `report_md` | 合规报告（0 或 1 次） | 建议展示风险提示 |
| `done` | `service`, `request_id`, `full_length`, `conversation_id`, `usage`, `reply_ms`, `payload` | **流正常结束** | **必须处理**：结束加载态 |
| `error` | `service`, `request_id`, `message` | **流异常结束** | **必须处理**：提示失败 |

`done.usage` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `prompt_tokens` | int | 本轮 prompt tokens |
| `completion_tokens` | int | 本轮 completion tokens |
| `total_tokens` | int | 本轮总 tokens |

`done.payload` 结构（仅在有导出/合规时出现）：

```json
{
  "has_content": true,
  "content_urls": [
    {
      "format": "html",
      "url": "/static/content/xxx.html",
      "platform": "xiaohongshu",
      "variant": "图文",
      "title": "...",
      "summary": "...",
      "platform_required_content": null
    }
  ],
  "compliance": {
    "risk_level": "low",
    "risk_categories": ["none"],
    "violations": [],
    "suggestion": "...",
    "report_md": "..."
  }
}
```

**SSE 示例**

```text
data: {"type": "start", "service": "system-chat", "stream_format": 2, "request_id": "550e8400-e29b-41d4-a716-446655440000"}

data: {"type": "thinking_delta", "text": "用户希望更口语化"}

data: {"type": "assistant_delta", "text": "好嘞"}

data: {"type": "assistant_delta", "text": "，我帮你改得更像聊天~"}

data: {"type": "done", "service": "system-chat", "request_id": "550e8400-e29b-41d4-a716-446655440000", "full_length": 18, "conversation_id": "main", "usage": {"prompt_tokens": 120, "completion_tokens": 8, "total_tokens": 128}, "reply_ms": 1200, "payload": {}}
```

#### 3.2.2 `cross-platform-content` SSE 事件流

`cross-platform-content` 不使用 v2 事件体系，而是按平台分块推送：

```
start → platform_chunk* / warning* / error* → done
```

| 事件 type | 字段 | 说明 |
|---|---|---|
| `start` | `service`, `platforms` | 开始生成 |
| `platform_chunk` | `platform`, `content` | 单个平台内容生成完毕 |
| `warning` | `platform`, `warnings` | 合规扫描命中敏感词 |
| `error` | `platform`, `message` | 某平台生成失败（不影响其他平台） |
| `done` | `total_platforms`, `full_length` | 全部完成 |

`content` 字段说明见 [4.22_API_REFERENCE.md](./4.22_API_REFERENCE.md) §3.5。

---

### 3.3 清除对话历史 `DELETE /api/v1/services/{service}/memory`

**请求参数**

| 参数 | 位置 | 必填 | 说明 |
|---|---|---|---|
| `user_id` | query | 是 | 用户唯一标识 |
| `conversation_id` | query | 是 | 对话唯一标识 |

**响应**

```json
{ "ok": true, "cleared": true, "service": "system-chat" }
```

**示例**

```bash
curl -X DELETE "http://127.0.0.1:8000/api/v1/services/system-chat/memory?user_id=u_10086&conversation_id=main"
```

---

## 4. SSE 流式解析实现指南

### 4.1 为什么不能用 EventSource

浏览器原生 `EventSource` 只支持 GET 请求，而本接口是 POST。需要用 `fetch` + `ReadableStream` 手动解析。

### 4.2 JavaScript 参考实现（`system-chat`）

```javascript
/**
 * 发送消息并流式接收回复
 * @param {string} baseUrl   Lumina 服务地址，如 "http://127.0.0.1:8000"
 * @param {string} userId    平台登录态用户 ID
 * @param {string} message   用户输入
 * @param {object} handlers  事件处理：onDelta(text) 必填，其余可选
 * @param {AbortSignal} signal 可选，用于"停止生成"
 */
async function streamChat(baseUrl, userId, message, handlers = {}, { signal } = {}) {
  const res = await fetch(`${baseUrl}/api/v1/services/system-chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, conversation_id: "main", message }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  const dispatch = (ev) => {
    if (ev.type === "assistant_delta") handlers.onDelta?.(ev.text);
    else if (ev.type === "thinking_delta") handlers.onThinking?.(ev.text);
    else if (ev.type === "tool_start") handlers.onToolStart?.(ev.tool, ev.args);
    else if (ev.type === "tool_complete") handlers.onToolComplete?.(ev.tool, ev.ok, ev.elapsed_ms);
    else if (ev.type === "export_link") handlers.onExportLink?.(ev);
    else if (ev.type === "compliance_report") handlers.onCompliance?.(ev);
    else if (ev.type === "done") handlers.onDone?.(ev);
    else if (ev.type === "error") handlers.onError?.(new Error(ev.message), ev);
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
await streamChat("http://127.0.0.1:8000", "u_10086", inputText, {
  onDelta: (text) => { draft += text; updateBubble(draft); },
  onDone:  ()     => finalizeBubble(),
  onError: (err)  => showToast(err.message),
});
```

### 4.3 解析要点

| 要点 | 说明 |
|---|---|
| 帧分隔符 | `\n\n`（两个换行）；网络传输可能把一帧切开，必须用 buffer 拼包后再分帧 |
| 行前缀 | 只处理以 `data:` 开头的行，取第 5 个字符后的内容 JSON 解析 |
| 坏帧容错 | JSON 解析失败的帧直接忽略，不要中断流 |
| 取消 | 传 `AbortSignal`，用于"停止生成"按钮；取消会抛 `AbortError`，静默处理即可 |
| 多事件行 | 一帧可能含多行 `data:`，逐行处理 |

---

## 5. "加载更早"翻页实现

每次多加载 50 条，prepend 到列表顶部：

```javascript
let loadedCount = messages.length;   // 首次 GET memory 后初始化
let hasMore = firstPage.has_more;

async function loadEarlier() {
  if (!hasMore) return;
  const r = await fetch(
    `${baseUrl}/api/v1/services/system-chat/memory?user_id=${userId}&conversation_id=main&limit=50&offset=${loadedCount}`
  );
  const data = await r.json();
  prependBubbles(data.messages);            // 渲染到列表顶部
  loadedCount += data.messages.length;
  hasMore = data.has_more;                  // false 时隐藏"加载更早"入口
}
```

> 翻页基于"最新优先 offset"，若翻页期间会话产生了新消息，可能出现个别重复气泡，前端按 `ts` 去重即可。

---

## 6. 错误处理

| 场景 | 行为 | 建议处理 |
|---|---|---|
| `GET/DELETE memory` 收到非 2xx | 请求失败 | try/catch，提示重试 |
| `POST stream` 收到非 2xx（流未开始） | 请求失败 | try/catch |
| 流式过程中服务端 `error` 事件 | 流异常结束 | 终止当前气泡渲染，提示失败 |
| 流式过程中网络断开 | fetch 抛错 | 同上 |
| 用户主动取消 | 传 `AbortSignal`，抛 `AbortError` | 静默处理，用于"停止生成"按钮 |
| SSE 坏帧 | 忽略，继续解析后续帧 | 无需处理 |

---

## 7. 与旧调试接口的对应关系

| 旧接口/元素 | 新接口/元素 |
|---|---|
| `POST /api/v1/debug/chat/stream` | `POST /api/v1/services/system-chat/stream` |
| `GET /api/v1/debug/chat/memory` | `GET /api/v1/services/system-chat/memory` |
| `DELETE /api/v1/debug/chat/memory` | `DELETE /api/v1/services/system-chat/memory` |
| `capability=system_chat` | `service=system-chat` |
| `capability=content_direction_ranking` | 已下线，返回 `410` |
| `capability=positioning_case_library` | 已下线，返回 `410` |
| `capability=content_positioning_matrix` | 已下线，返回 `410` |
| `capability=weekly_decision_snapshot` | 已下线，返回 `410` |
| `hub_context` | 统一改为 `context`（仅 `system-chat` 透传） |

---

## 8. 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v1.0 | 2026-07-16 | 初版：HTTP 接口文档（memory / stream / delete） |
| v2.0 | 2026-07-16 | 重构为 SDK 对接文档：`LuminaChatClient` 统一封装；底层 HTTP 协议移至 §5 |
| v2.1 | 2026-07-16 | 刷新加载策略改为默认最新 50 条；`loadHistory` 返回 `{messages, total, hasMore}` |
| v2.2 | 2026-07-16 | "加载更早"交互转为正式需求；SSE v2 事件体系落地 |
| v2.3 | 2026-07-16 | 明确 SDK 与直接 HTTP 两种接入方式并存 |
| **v3.0** | **2026-07-26** | **本文档重新定位为纯 HTTP API 协议真源**：移除 SDK 封装内容，按 REST 端点、字段、cURL 示例重新组织；`system-chat` 为唯一对外主入口，已下线服务统一返回 `410`；`cross-platform-content` 保留并补充其 SSE 事件说明 |
