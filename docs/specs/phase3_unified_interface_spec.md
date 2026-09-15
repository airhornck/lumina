# Phase 3 SPEC：统一服务流接口

> 文档版本：v1.0
> 日期：2026-07-07
> 依据：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` v1.2、`docs/LUMINA_HYBRID_RENOVATION_PLAN.md` 阶段 3

---

## 1. 目标

将对外服务流收敛为单一入口 `POST /api/v1/services/system-chat/stream`，承载系统对话及内容方向榜单、定位矩阵、每周决策快照三个 Skill 化能力。

---

## 2. 输入边界

### 2.1 接口

```http
POST /api/v1/services/system-chat/stream
Content-Type: application/json
Accept: text/event-stream
```

### 2.2 请求体

复用 `ServiceStreamRequest`：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 长度 1-128 |
| `conversation_id` | string | 是 | 长度 1-128 |
| `message` | string | 是 | 长度 1-32000，用户自然语言输入 |
| `platform` | string | 否 | 平台上下文 |
| `context` | object | 否 | 业务上下文，透传给 Orchestra |
| `mode` | string | 否 | 子模式，定位矩阵场景可取值 `case` / `matrix` |
| `stream_format` | int | 否 | 1=v1 SSE；2=v2 |

### 2.3 极端边界条件

- `message` 为空或纯空白 → 返回 422
- `message` 超长（>32000） → 返回 422
- `user_id` / `conversation_id` 缺失或空 → 返回 422
- `stream_format` 不为 1/2 → 返回 422

---

## 3. 输出边界

### 3.1 SSE 事件流

统一接口输出 SSE 与现有 `system-chat` 保持一致。

**v1 格式**：
```text
data: {"type": "start", "service": "system-chat", "via": "marketing_orchestra"}
data: {"type": "delta", "text": "..."}
data: {"type": "done", "full_length": 1024}
```

**v2 格式**：
```text
data: {"type": "start", "service": "system-chat", "stream_format": 2, "request_id": "..."}
data: {"type": "assistant_delta", "text": "..."}
data: {"type": "done", "service": "system-chat", "request_id": "...", "full_length": 1024, "payload": {"layer": "orchestra", "mode": "dynamic", "intent": {"kind": "content_ranking"}, "hub": {...}, "reply": "..."}}
```

### 3.2 错误输出

```json
{"type": "error", "message": "..."}
```

---

## 4. 业务规则

### 4.1 Skill 唤起规则

统一接口通过用户 `message` 中的关键词或意图识别，路由到对应 Skill：

| 能力 | 意图 kind | 关键词示例 |
|------|-----------|------------|
| 爆款榜单（TrendingRank） | `trending_rank` / `content_ranking` | "查爆款榜单"、"抖音热门"、"小红书爆款"、"B站 trending"、"全网热点"、"内容方向榜单"、"排一下方向" |
| 内容定位矩阵（ContentPositionMatrix） | `content_position_matrix` / `positioning_matrix` | "分析内容定位"、"内容矩阵"、"定位诊断"、"爆款定位分析"、"找差异化方向"、"定位矩阵" |
| 每周决策快报（WeeklyOpsBrief） | `weekly_ops_brief` / `weekly_snapshot` | "生成本周快报"、"运营周报"、"决策报告"、"本周复盘"、"下周策略"、"每周决策快照" |

### 4.2 路由优先级

1. 寒暄/致谢/告别 → `conversation`
2. 明确 Skill 关键词 → 对应 Skill
3. 其他营销意图 → 原有 Orchestra 逻辑
4. 默认 → `conversation`

### 4.3 记忆规则

- 统一使用 `service="system-chat"` 读写记忆
- Skill 执行前后的 user/assistant 消息均存入 system-chat 记忆
- 原 `content-ranking` / `positioning` / `weekly-snapshot` 记忆只读，不再写入

---

## 5. 安全合规

- Skill 只能调用 `llm_hub` 生成文本，禁止执行任意代码或访问外部网络
- 用户输入必须校验长度与类型
- 记忆读写必须按 `user_id` 隔离

---

## 6. 接口兼容性声明

- 统一接口路径、请求参数、响应 JSON、SSE 事件类型、错误码与现有 `system-chat` 保持一致
- 新增 `intent.kind` 取值（`content_ranking`、`positioning_matrix`、`weekly_snapshot`）为可选扩展，不影响旧逻辑
