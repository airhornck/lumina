# Lumina 统一服务 API 对接文档

> 版本：v1.0  
> 适用范围：对外服务层 4 个独立流式 API（System Chat / Content Ranking / Positioning / Weekly Snapshot）

---

## 1. 接口概述

Lumina 将原有调试页中的 5 项能力封装为 **4 个独立对外 API**，全部支持 **SSE（Server-Sent Events）流式返回**，并通过统一协议提供服务。

| 中文能力名 | Service ID | 端点 | 说明 |
|-----------|------------|------|------|
| 系统对话（编排 API） | `system-chat` | `POST /api/v1/services/system-chat/stream` | 复用 `MarketingOrchestra`，走意图路由 + Skill Hub |
| 内容方向榜单 | `content-ranking` | `POST /api/v1/services/content-ranking/stream` | 专项 system prompt + LLM 流式 |
| 定位服务 | `positioning` | `POST /api/v1/services/positioning/stream` | 子模式 `case`（案例库）/ `matrix`（矩阵） |
| 每周决策快照 | `weekly-snapshot` | `POST /api/v1/services/weekly-snapshot/stream` | 专项 system prompt + LLM 流式 |

### 核心特性
- **统一请求体**：所有 `/stream` 端点共用同一 `ServiceStreamRequest` 结构。
- **统一 SSE 协议**：事件格式完全一致，前端/客户端解析逻辑可复用。
- **记忆隔离**：按 `(user_id, conversation_id, service)` 三元组隔离，不同用户、不同对话、不同服务之间互不串扰。
- **记忆管理 API**：支持按 service 查询与清空记忆。

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
| `platform` | `string` | 否 | 平台上下文，如 `xiaohongshu`、`douyin`、`bilibili` |
| `context` | `object` | 否 | 业务上下文；仅 `system-chat` 会透传给 `MarketingOrchestra` |
| `mode` | `string` | 否 | **仅 `positioning` 必填**：`case`（案例库）或 `matrix`（矩阵） |

### 2.3 统一 SSE 响应格式

流式接口返回 `text/event-stream`，每条事件以 `data: <json>\n\n` 格式推送。

| 事件类型 `type` | 字段 | 说明 |
|----------------|------|------|
| `start` | `service`, `via?`, `mode?` | 服务开始处理 |
| `delta` | `text` | 文本流式片段 |
| `done` | `full_length` | 流结束，返回完整文本长度 |
| `error` | `message` | 服务端或模型异常 |

#### SSE 事件示例

```text
data: {"type": "start", "service": "content-ranking"}

data: {"type": "delta", "text": "本周"}

data: {"type": "delta", "text": " TOP 3 方向为："}

data: {"type": "done", "full_length": 256}
```

> **注意**：客户端解析时应按 `\n\n` 分割行，再提取 `data:` 后的 JSON；不要依赖单次 `read()` 即拿到完整事件。

---

## 3. API 详细说明

### 3.1 系统对话（编排 API）

#### 端点
```http
POST /api/v1/services/system-chat/stream
```

#### 功能
复用 `MarketingOrchestra.process(...)`，内部完成意图分类 → SOP 编排 / 动态 Skill 调用 → 自然语言回复生成。返回结果为 JSON 序列化后的字符串，以 SSE 分片下发。

#### 请求示例
```bash
curl -N -X POST http://localhost:8000/api/v1/services/system-chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u_abc123",
    "conversation_id": "c_xyz789",
    "message": "帮我诊断一下账号",
    "platform": "xiaohongshu",
    "context": {
      "industry": "美妆",
      "account_url": "https://xiaohongshu.com/user/profile/xxx"
    }
  }'
```

#### 典型 SSE 返回
```text
data: {"type": "start", "service": "system-chat", "via": "marketing_orchestra"}

data: {"type": "delta", "text": "{\n  \"ok\": true,\n  \"layer\": \"orchestra\",\n  ...}"}

data: {"type": "done", "full_length": 1024}
```

---

### 3.2 内容方向榜单

#### 端点
```http
POST /api/v1/services/content-ranking/stream
```

#### 功能
基于专项 system prompt，帮助用户梳理、排序、对比可选的内容方向，输出可执行的「方向榜单」结构。

#### 请求示例
```bash
curl -N -X POST http://localhost:8000/api/v1/services/content-ranking/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u_abc123",
    "conversation_id": "c_xyz789",
    "message": "帮我排一下美妆赛道的内容方向优先级",
    "platform": "xiaohongshu"
  }'
```

---

### 3.3 定位服务

#### 端点
```http
POST /api/v1/services/positioning/stream
```

#### 功能
通过 `mode` 字段在「定位决策案例库」与「内容定位矩阵」之间切换：
- `mode=case`：用案例化方式帮助用户做定位决策，输出可选方案对比、Slogan 建议。
- `mode=matrix`：用矩阵思维组织内容定位，优先输出 Markdown 表格 + 解读。

#### 请求示例（案例库）
```bash
curl -N -X POST http://localhost:8000/api/v1/services/positioning/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u_abc123",
    "conversation_id": "c_xyz789",
    "message": "给我一个差异化的定位方案",
    "platform": "xiaohongshu",
    "mode": "case"
  }'
```

#### 请求示例（矩阵）
```bash
curl -N -X POST http://localhost:8000/api/v1/services/positioning/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u_abc123",
    "conversation_id": "c_xyz789",
    "message": "用矩阵帮我梳理一下内容定位",
    "platform": "douyin",
    "mode": "matrix"
  }'
```

---

### 3.4 每周决策快照

#### 端点
```http
POST /api/v1/services/weekly-snapshot/stream
```

#### 功能
将用户本周（或指定期）在内容/增长上的决策整理成「快照」，结构包含摘要、TOP 3 决策/实验、指标、下一步、需要数据。

#### 请求示例
```bash
curl -N -X POST http://localhost:8000/api/v1/services/weekly-snapshot/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u_abc123",
    "conversation_id": "c_xyz789",
    "message": "帮我整理本周的内容运营决策快照",
    "platform": "xiaohongshu"
  }'
```

---

## 4. 记忆隔离与记忆管理 API

### 4.1 隔离模型

记忆在服务端按 **三元组** 隔离：

```
(user_id, conversation_id, service)
```

- 不同 `user_id`：记忆完全隔离
- 同一 `user_id`、不同 `conversation_id`：记忆完全隔离
- 同一 `user_id` + 同一 `conversation_id`、不同 `service`：记忆也完全隔离

### 4.2 查询记忆

```http
GET /api/v1/services/{service}/memory?user_id={uid}&conversation_id={cid}
```

#### 响应示例
```json
{
  "user_id": "u_abc123",
  "conversation_id": "c_xyz789",
  "service": "content-ranking",
  "count": 4,
  "messages": [
    { "role": "user", "content": "帮我排一下方向", "ts": "2026-04-15T05:00:00Z" },
    { "role": "assistant", "content": "本周 TOP 3 方向为...", "ts": "2026-04-15T05:00:05Z" }
  ]
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
  "service": "content-ranking"
}
```

---

## 5. 前端/客户端对接指南

### 5.1 对接 checklist

1. **维护两个 ID**：`user_id`（用户级）和 `conversation_id`（对话级），切换任一 ID 即视为不同上下文。
2. **按 service 切换端点**：发送前拼接 URL `/api/v1/services/{service}/stream`。
3. **SSE 解析必须兼容分片**：同一条事件可能跨多次 `read()`，需用缓冲区按 `\n\n` 分割。
4. **positioning 必须传 mode**：`case` 或 `matrix`，建议 UI 上以下拉框提供切换。
5. **system-chat 的 context 校验**：发起前建议做 `JSON.parse` 校验，避免服务端报 422。

### 5.2 JavaScript 对接示例（Fetch + SSE）

```javascript
async function streamChat(service, payload) {
  const res = await fetch(`/api/v1/services/${service}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (!line.startsWith("data:")) continue;

      const event = JSON.parse(line.slice(5).trim());
      switch (event.type) {
        case "start":
          console.log("开始", event.service, event.via);
          break;
        case "delta":
          console.log("收到片段:", event.text);
          break;
        case "done":
          console.log("完成，长度:", event.full_length);
          break;
        case "error":
          console.error("错误:", event.message);
          break;
      }
    }
  }
}

// 调用示例
streamChat("content-ranking", {
  user_id: "u_001",
  conversation_id: "c_001",
  message: "帮我排一下内容方向",
  platform: "xiaohongshu",
});
```

### 5.3 与旧调试接口的对应关系

| 旧接口/元素 | 新接口/元素 |
|------------|------------|
| `POST /api/v1/debug/chat/stream` | `POST /api/v1/services/{service}/stream` |
| `GET /api/v1/debug/chat/memory` | `GET /api/v1/services/{service}/memory` |
| `DELETE /api/v1/debug/chat/memory` | `DELETE /api/v1/services/{service}/memory` |
| `capability=system_chat` | `service=system-chat` |
| `capability=content_direction_ranking` | `service=content-ranking` |
| `capability=positioning_case_library` | `service=positioning` + `mode=case` |
| `capability=content_positioning_matrix` | `service=positioning` + `mode=matrix` |
| `capability=weekly_decision_snapshot` | `service=weekly-snapshot` |
| `hub_context` | 统一改为 `context`（仅 system-chat） |

---

## 6. 错误码与处理

### HTTP 状态码

| 状态码 | 场景 | 建议处理 |
|--------|------|----------|
| `200` | 正常返回（流式或非流式） | 按 SSE 或 JSON 解析 |
| `400` | `service` 不存在 / `mode` 非法 / 请求体校验失败 | 检查 URL 与请求体字段 |
| `422` | Pydantic 校验失败（如 `message` 为空、`context` 不是对象） | 检查请求体格式与类型 |
| `500` | 服务端内部异常（如 LLM Hub 未初始化、模型调用失败） | 查看服务端日志排查 |

### SSE `error` 事件常见原因

| 错误信息 | 原因 | 解决方式 |
|---------|------|----------|
| `LLM Hub 未初始化` | `infra/config/llm.yaml` 缺失或格式错误 | 检查配置文件路径与内容 |
| `无法获取 debug_chat 客户端` | `llm.yaml` 中未配置 `debug_chat` 的 skill_config | 检查 `llm.yaml` 的 `skill_config` 节点 |
| `debug_chat 客户端缺少 API Key` | 环境变量未设置对应 Key | 设置 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` |
| `system_chat orchestra failed` | 编排层内部异常 | 查看服务端详细堆栈 |

---

## 7. 服务启动与验证

### 启动服务
```bash
python -m uvicorn api.main:app --app-dir apps/api/src --port 8000 --reload
```

### 健康检查
```bash
curl http://localhost:8000/health
```

### 快速 curl 验证
```bash
# 1. 查询记忆（应为空）
curl "http://localhost:8000/api/v1/services/system-chat/memory?user_id=u1&conversation_id=c1"

# 2. 发起流式对话
curl -N -X POST http://localhost:8000/api/v1/services/content-ranking/stream \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","conversation_id":"c1","message":"hello"}'
```
