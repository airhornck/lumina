# 对话历史加载方案（单对话窗口 · 登录续聊 · 前端 SDK 封装）

| 项目 | 内容 |
|---|---|
| 版本 | v1.3 |
| 日期 | 2026-07-16 |
| 状态 | 方案已确认，待开发 |
| 关联文档 | [CONVERSATION_HISTORY_API.md](./CONVERSATION_HISTORY_API.md)（HTTP API 对接文档）、[CONVERSATION_HISTORY_API_HTTP.md](./CONVERSATION_HISTORY_API_HTTP.md)（已合并至 API 文档） |

---

## 1. 背景与目标

产品前端只有**一个对话窗口**。目标是：用户经平台侧登录后，前端一次请求即可加载对话历史，并在此基础上继续对话；刷新页面等同于重新加载一次历史。

### 已确认的需求边界

1. **认证在平台侧**。Lumina 不做登录/鉴权，仅接收前端传入的 `user_id` + 固定 `conversation_id`，视其为平台侧可信输入。
2. **历史不设 200 条上限，全量保留**；前端**每次刷新默认加载最新 50 条**，并提供**"加载更早"交互，每次多加载 50 条**。
3. **"一个接口"的诉求由前端 SDK 封装实现**（决策见 §4.1），后端 HTTP 接口保持现状。

---

## 2. 需求对齐

| # | 需求 | 验收口径 |
|---|---|---|
| R1 | 登录后一次请求加载历史并继续对话 | 前端用 `user_id` + 固定 `conversation_id` 调一次 `GET memory`（limit=50）返回**最新 50 条**并渲染；发消息走现有 SSE 接口，历史自动延续 |
| R2 | 历史不受 200 条限制 | 写入超过 200 条后最早消息仍存在、可被查询（不带 limit 返回全部）；对外接口契约向后兼容 |
| R3 | 对话、历史等能力对前端呈现为统一入口（SDK 为可选封装） | SDK（`LuminaChatClient`）覆盖 历史加载 / 发送消息 / 清除历史；**不强制接入**——调用方也可按协议真源直接对接 HTTP 接口，两种方式完全等价 |
| R4 | "加载更早"交互 | 前端提供"加载更早"入口（点击/滚动触发），每次多加载 50 条并 prepend 渲染，直至 `hasMore=false` |

### 现有接口结论

**现有接口主体零改动**：`GET /api/v1/services/{service}/memory` 本就返回指定会话消息；`POST /api/v1/services/{service}/stream` 每轮自动读历史、写回新消息。R1 的落地依赖 **ID 约定** + memory 接口**新增分页参数**（支撑"默认 50 条"策略，向后兼容）；R3 由 **SDK 封装**实现。

---

## 3. 现状关键事实（开发依据）

| 事实 | 位置 |
|---|---|
| 历史存储于 PostgreSQL `chat_messages` 表，按 `(user_id, conversation_id)` 隔离，追加写入 | `apps/api/src/chat_debug/memory_postgres.py` |
| 每次 INSERT 后执行 `DELETE ... OFFSET 200` 滚动删除最旧消息 | `memory_postgres.py:154-167` |
| 内存降级实现同样有 200 条截断 | `apps/api/src/chat_debug/memory.py:42-43` |
| 服务级隔离：存储键为 `{conversation_id}::{service}` | `apps/api/src/services/memory_service.py:17-18` |
| 聊天链路每轮 `list_messages()` 全量读历史，再切最近 24 条注入 LLM | `apps/api/src/services/handlers/system_chat.py:44-52` |
| `GET memory` 返回 `{user_id, conversation_id, service, count, messages[]}` | `apps/api/src/services/router.py:96-114` |
| 无鉴权，`user_id` 为客户端自报字符串 | `apps/api/src/api/main.py`（CORS 全开，无认证依赖） |

---

## 4. 总体方案

### 4.1 方案决策：单接口诉求的落地方式

"对话、历史合并为一个接口"有三种做法，已对比评估：

| 方案 | 做法 | 评估 |
|---|---|---|
| **A. 前端封装 SDK** ✅ | 后端保持 GET/POST/DELETE 三个接口，前端封装 `LuminaChatClient` 统一入口 | 前端体验 = 一个模块三个方法；后端零改动零风险；业界标准做法 |
| B. 同路径多方法 | `GET/POST/DELETE /api/v1/chat` 共用一个路径 | 调用次数不减少，仅 URL 变少；要么破坏性改路径，要么维护双路径，收益≈0 |
| C. 单端点全 SSE | stream 接口加 `include_history` / `load_only` 模式 | 一个端点两种行为模式，协议、校验、文档、测试全面复杂化；调用次数仍不减少 |

**决策：方案 A。**"一个接口"是前端使用体感问题，在前端层解决；后端"一次性 JSON 读取"与"长连接流式写入"的接口边界保持不动。

### 4.2 改动清单

| 层 | 改动内容 | 性质 | 阶段 |
|---|---|---|---|
| 前端 | 交付 `LuminaChatClient` SDK（`static/sdk/luminaChatClient.js`，参考实现见 SDK 文档 §4），封装 历史/对话/清除；`loadHistory` **默认拉取最新 50 条** | **新增交付物** | Phase 1 |
| 前端/平台侧 | `user_id` 取登录态；`conversation_id` 按固定约定生成 | 约定落地，无后端改动 | Phase 1 |
| 存储层（PG） | 删除 200 条滚动删除逻辑，纯追加 | 后端改动 | Phase 1 |
| 存储层（内存降级） | 截断上限放大（200 → 10000），防内存失控 | 后端改动 | Phase 1 |
| 存储层（内部方法） | `list_messages` 增加 `limit`/`offset`（最新优先语义）；新增 `count_messages` | 后端改动，不改对外接口 | Phase 1 |
| memory 接口 | 新增 `limit`/`offset`/`order` 查询参数 + 响应新增 `total`/`has_more`（支撑默认 50 条加载） | **向后兼容扩展** | Phase 1 |
| 聊天链路 | `list_messages(limit=24)`，每轮只读最近 24 条注入 LLM | 后端改动，不改对外接口 | Phase 1 |
| stream 接口 / SSE 契约 | 不动 | — | — |
| 前端 UI | **"加载更早消息"交互**：点击/滚动触发 `loadHistory({ offset })`，每次多加载 50 条 | 新增 | Phase 1 |

### 4.3 为什么"内部 limit"必须随去截断一起做

聊天链路每轮都全量读出会话历史再切 24 条。200 条封顶时无所谓；去掉上限后，重度用户每发一句话都会从 DB 拉取数千条记录再丢弃 99%，造成明显的 IO 浪费。给内部 `list_messages` 加 `limit` 后，DB 层只取最新 24 条，每轮读取量与历史总量脱钩。同一套 limit/offset 机制同时支撑 memory 接口的分页。

---

## 5. 详细设计

### 5.1 ID 约定（R1 核心，纯约定）

```
user_id         = 平台登录态下发的用户唯一标识（Lumina 不校验、仅透传）
conversation_id = 固定值，SDK 默认 "main"
```

- 单窗口形态下，一个用户在 `system-chat` 下只有一条会话，与现有存储模型天然匹配。
- 存储键实际为 `{conversation_id}::{service}`，即使未来接入第二个 service，同一 `conversation_id` 也不会串历史。
- 该约定已内置进 SDK 默认值，前端只需传 `userId`。

### 5.2 运行时流程（SDK 视角）

**页面加载 / 刷新（恰好一次加载请求，默认最新 50 条）**

```js
const chat = new LuminaChatClient({ userId });        // userId 来自平台登录态
const { messages, total, hasMore } = await chat.loadHistory();  // 默认 limit=50
messages.forEach(m => renderBubble(m.role, m.content, m.ts));
// 首次使用返回空数组；hasMore=true 时可展示"加载更早消息"入口
```

**加载更早消息（每次多加载 50 条，Phase 1）**

```js
let loadedCount = messages.length;
let hasMoreEarlier = hasMore;

async function loadEarlier() {
  if (!hasMoreEarlier) return;
  const earlier = await chat.loadHistory({ offset: loadedCount });  // 再取 50 条
  renderBefore(earlier.messages);          // prepend 到列表顶部
  loadedCount += earlier.messages.length;
  hasMoreEarlier = earlier.hasMore;        // false 时隐藏"加载更早"入口
}
```

> 注意：翻页基于"最新优先 offset"，若翻页期间会话产生了新消息，可能出现个别重复气泡，前端按 `ts` 去重即可。

**发送消息（SSE 流式）**

```js
await chat.send("帮我写一篇小红书种草笔记", {
  onDelta:      (text) => appendToBubble(text),       // 回复增量
  onExportLink: (info) => renderExportCard(info),     // 内容导出卡片
  onCompliance: (r)    => renderCompliance(r),        // 合规报告
  onDone:       ()     => finalizeBubble(),
  onError:      (err)  => showToast(err.message),
});
```

**清除历史**

```js
await chat.clear();                                   // → DELETE memory
```

SDK 参考实现见 `static/sdk/luminaChatClient.js`；底层 HTTP 协议真源见 [CONVERSATION_HISTORY_API.md](./CONVERSATION_HISTORY_API.md)。

### 5.3 后端改动点（Phase 1）

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `apps/api/src/chat_debug/memory_postgres.py` | `append()` 内 154-167 行 | 删除 `DELETE ... OFFSET $3` 语句，INSERT 后不再裁剪 |
| 2 | `apps/api/src/chat_debug/memory.py` | 42-43 行 | 截断上限 `max_messages_per_conv` 默认值 200 → 10000（仅降级路径安全阀） |
| 3 | `apps/api/src/chat_debug/memory_postgres.py` | `list_messages()` | 增加 `limit: int \| None = None`、`offset: int = 0`；传入 limit 时 SQL 改为 `ORDER BY created_at DESC, id DESC LIMIT $3 OFFSET $4`，取回后在代码内反转为正序返回；不传 limit 保持现有全量正序语义 |
| 4 | `apps/api/src/chat_debug/memory.py` | `list_messages()` | 同步增加 `limit`/`offset`（从尾部切片），保持两实现签名与语义一致 |
| 5 | `memory_postgres.py` / `memory.py` | 新增 `count_messages(user_id, conversation_id)` | `SELECT COUNT(*)` / `len()`，用于响应 `total` |
| 6 | `apps/api/src/services/router.py` | `get_memory()` 96-114 行 | 新增 query 参数 `limit`（可选）、`offset`（默认 0）、`order`（默认 asc）；`MemoryResponse` 增加 `total`、`has_more` 字段；`has_more = (offset + count) < total` |
| 7 | `apps/api/src/services/handlers/system_chat.py` | 44 行 | 聊天链路调用改传 `limit=24` |

> 说明：`ServiceMemoryStore`（`memory_service.py`）需同步透传 `limit`/`offset`/`count_messages`。无需改表、无需数据迁移，历史数据不受影响（仅停止删除）。
>
> **分页语义**：`limit`/`offset` 采用"最新优先"模型——`limit=50` 取最新 50 条；`offset=50` 跳过最新 50 条（即向更早翻一页）；返回默认按时间正序（`order=asc`），`order=desc` 仅翻转返回顺序。**不带任何参数 = 返回全部（保持现有行为，向后兼容）。**

### 5.4 Phase 2（可选）：数据归档

分页能力（limit/offset/order + total/has_more）与"加载更早"交互均已在 **Phase 1** 落地（§5.2）。Phase 2 仅剩：

- 数据归档策略（视单会话数据量增长情况再定，当前无需）。

---

## 6. 最新接口与字段（最终形态）

> 前端可按 SDK 封装或直接按 HTTP 协议对接；完整协议见 [CONVERSATION_HISTORY_API.md](./CONVERSATION_HISTORY_API.md)。

### 6.1 SDK 接口（前端唯一入口）

| 方法 | 签名 | 说明 | 底层接口 |
|---|---|---|---|
| 构造 | `new LuminaChatClient({ userId, conversationId="main", baseUrl="", service="system-chat", platform=null, context={} })` | 初始化客户端 | — |
| 加载历史 | `loadHistory({ limit=50, offset=0 } = {}) → Promise<{ messages, total, hasMore }>` | 页面加载/刷新调一次，默认最新 50 条 | GET memory |
| 发送消息 | `send(message, callbacks, {signal}) → Promise<void>` | SSE 流式；callbacks 见下 | POST stream |
| 清除历史 | `clear() → Promise<{ok, cleared, service}>` | 清空该会话 | DELETE memory |

`send` 的 callbacks：`onEvent(evt)（原始事件透传，调试用）/ onStart / onThinking(text) / onToolStart(tool,args) / onToolComplete(tool,ok,elapsedMs) / onDelta(text) / onExportLink(info) / onCompliance(report) / onDone(result) / onError(err)`，与 SSE 事件一一对应。

### 6.2 底层 HTTP 接口（协议真源，SDK 已封装，前端一般不直接调用）

**`GET /api/v1/services/{service}/memory`**

| 项 | 内容 |
|---|---|
| 请求 | query：`user_id`（必）、`conversation_id`（必）；`limit`/`offset`/`order`（可选，不传=返回全部） |
| 响应 | `{user_id, conversation_id, service, count, messages[{role, content, ts, capability?}], total, has_more}` |

**`POST /api/v1/services/{service}/stream`**（SSE，不变）

| 项 | 内容 |
|---|---|
| 请求体 | `{user_id(1-128), conversation_id(1-128), message(1-32000), platform?, context?, mode?, stream_format?}` |
| SSE 事件 | `start → thinking_delta*/tool_start*/tool_complete*/assistant_delta* → export_link*/compliance_report? → done`；异常：`error` |

**`DELETE /api/v1/services/{service}/memory`**（不变）

| 项 | 内容 |
|---|---|
| 请求 | query：`user_id`（必）、`conversation_id`（必） |
| 响应 | `{ok, cleared, service}` |

---

## 7. 兼容性说明

| 调用方 | 影响 |
|---|---|
| 现有前端（debug_chat） | 无影响；HTTP 层不传分页参数仍返回全部；新增响应字段（total/has_more）可安全忽略 |
| 平台侧新前端（SDK 接入） | 引入 SDK + 传 `userId` 即可完成对接；`loadHistory()` 默认即最新 50 条 |
| 平台侧新前端（直接 HTTP 接入） | 不需要 SDK；按接口文档 §5 协议真源对接即可，接口契约与 SDK 方案完全一致 |
| SDK 返回值说明 | 文档 v2.0 中 `loadHistory()` 返回数组，v2.1 起调整为 `{ messages, total, hasMore }`；SDK 尚未落地，无存量影响 |

---

## 8. 风险与边界

1. **信任边界**：Lumina 不校验 `user_id`，任何知道 `user_id` 的请求方都能读取该用户全部历史。前提是 Lumina 仅部署于内网/网关之后，由平台侧完成鉴权；若未来直接对公网暴露，需补签名校验（不在本期范围）。
2. **多端同登**：同一 `user_id` 多设备同时对话时，消息按时间交错进同一条会话，单窗口产品下可接受。
3. **模型记忆 ≠ 界面历史**：无论界面加载多少条，LLM 每轮只看最近 24 条（Hermes 引擎内部另有 token 阈值压缩兜底）。本期不变。
4. **SDK 维护**：SDK 参考实现随文档交付，后续 SSE 协议或分页扩展变更时需同步更新 SDK 与文档。

---

## 9. 验收标准

- [ ] 前端通过 SDK `loadHistory()` 一次请求返回**最新 50 条**（不足 50 条返回全部），`total`/`hasMore` 正确，刷新页面即恢复对话
- [ ] 前端"加载更早"交互每次多加载 50 条并正确 prepend 渲染，`hasMore=false` 后入口隐藏（分页语义正确）
- [ ] 通过 SDK `send()` 继续对话，SSE 各事件回调正常触发，历史自动延续
- [ ] 连续写入超过 200 条后，最早消息仍存在（不带 limit 调 `GET memory` 可返回全部）
- [ ] 聊天链路每轮 DB 读取量不随历史总量增长（内部 `limit` 生效）
- [ ] 前端业务代码不直接拼装 HTTP 请求，仅依赖 SDK
- [ ] 不带分页参数的老调用方行为不变

---

## 10. 阶段计划

| 阶段 | 内容 | 依赖 |
|---|---|---|
| Phase 1 | 存储层去截断；`list_messages` limit/offset + `count_messages`；memory 接口分页参数 + `total`/`has_more`；聊天链路 limit=24；交付 SDK（`loadHistory` 默认 50 条）；前端"加载更早"交互（每次 +50 条）；文档更新 | 无 |
| Phase 2（可选） | 数据归档策略（视数据量再定） | Phase 1 完成 |

---

## 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v1.0 | 2026-07-16 | 初版：ID 约定；历史取消 200 条上限；分页后置 |
| v1.1 | 2026-07-16 | 新增方案决策（§4.1）：单接口诉求由前端 SDK 封装落地；改动清单、流程、接口章节同步调整为 SDK 视角 |
| v1.2 | 2026-07-16 | 每次刷新默认加载**最新 50 条**：memory 分页参数（`limit`/`offset`/`order` + `total`/`has_more`）由 Phase 2 前置到 Phase 1；SDK `loadHistory` 默认 `limit=50`，返回结构调整为 `{messages, total, hasMore}`；Phase 2 缩减为可选 UI 增强 |
| v1.3 | 2026-07-16 | **"加载更早"交互纳入 Phase 1**（新增 R4）：每次多加载 50 条（offset 翻页 + prepend 渲染）；补充翻页去重注意事项；Phase 2 仅剩数据归档（可选） |
| v1.4 | 2026-07-16 | 明确 SDK 为**可选封装**：两种接入方式（SDK / 直接 HTTP）并存且等价，业务前端可不接入 SDK，按协议真源直接对接 HTTP 接口 |
