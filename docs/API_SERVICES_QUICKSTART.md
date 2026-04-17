# Lumina 服务 API 快速接入指南

> 目标：让外部开发者在 5 分钟内完成首个流式 API 调用。

---

## 1. 拿到 Base URL

```
http://localhost:8000
```

确认服务已启动：
```bash
curl http://localhost:8000/health
```

---

## 2. 统一请求体（4 个接口都一样）

```json
{
  "user_id": "u_abc123",
  "conversation_id": "c_xyz789",
  "message": "帮我排一下美妆赛道的内容方向优先级",
  "platform": "xiaohongshu",
  "context": {},
  "mode": "case"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `user_id` | 是 | 用户唯一标识 |
| `conversation_id` | 是 | 对话唯一标识 |
| `message` | 是 | 用户当前输入 |
| `platform` | 否 | 如 `xiaohongshu`、`douyin` |
| `context` | 否 | 仅 `system-chat` 会透传给编排层 |
| `mode` | 否 | **仅 `positioning` 必填**：`case` / `matrix` |

---

## 3. 四个接口端点

| 能力 | 端点 |
|------|------|
| 系统对话（编排 API） | `POST /api/v1/services/system-chat/stream` |
| 内容方向榜单 | `POST /api/v1/services/content-ranking/stream` |
| 定位服务 | `POST /api/v1/services/positioning/stream` |
| 每周决策快照 | `POST /api/v1/services/weekly-snapshot/stream` |

全部返回 **SSE 流**（`text/event-stream`）。

---

## 4. 第一个 curl 示例

```bash
curl -N -X POST http://localhost:8000/api/v1/services/content-ranking/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u_001",
    "conversation_id": "c_001",
    "message": "帮我排一下内容方向优先级"
  }'
```

返回示例：
```text
data: {"type": "start", "service": "content-ranking"}

data: {"type": "delta", "text": "本周"}

data: {"type": "delta", "text": " TOP 3 方向为："}

data: {"type": "done", "full_length": 128}
```

> `-N` 参数让 curl 禁用输出缓冲，确保实时看到流式内容。

---

## 5. JavaScript 快速接入

```javascript
async function chat(service, payload) {
  const res = await fetch(`/api/v1/services/${service}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

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

      const ev = JSON.parse(line.slice(5).trim());
      if (ev.type === "delta") {
        console.log(ev.text);      // 追加到 UI
      } else if (ev.type === "done") {
        console.log("流结束");
      } else if (ev.type === "error") {
        console.error(ev.message);
      }
    }
  }
}

// 使用示例
chat("content-ranking", {
  user_id: "u_001",
  conversation_id: "c_001",
  message: "帮我排一下内容方向",
});
```

---

## 6. 记忆管理（隔离查询与清空）

隔离维度：**`user_id` + `conversation_id` + `service`**。

```bash
# 查询某服务的记忆
curl "http://localhost:8000/api/v1/services/content-ranking/memory?user_id=u_001&conversation_id=c_001"

# 清空某服务的记忆
curl -X DELETE "http://localhost:8000/api/v1/services/content-ranking/memory?user_id=u_001&conversation_id=c_001"
```

---

## 7. 常见错误速查

| 现象 | 原因 | 解决 |
|------|------|------|
| `LLM Hub 未初始化` | `infra/config/llm.yaml` 缺失或格式错误 | 检查配置文件 |
| `无法获取 debug_chat 客户端` | `llm.yaml` 未配置 `debug_chat` | 检查 `skill_config` 节点 |
| `缺少 API Key` | 环境变量未设置 | 设置 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` |
| `HTTP 400` | `service` 不存在 或 `mode` 错误 | 检查 URL 与 `mode` 值 |

---

## 8. 调试前端

浏览器直接访问：
```
http://localhost:8000/debug/chat
```

前端已对接 4 个新 API，支持服务切换、定位子模式切换、记忆隔离查看与清空。
