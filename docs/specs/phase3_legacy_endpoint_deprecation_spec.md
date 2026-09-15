# Phase 3 SPEC：原独立端点废弃策略

> 文档版本：v1.0
> 日期：2026-07-07
> 依据：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` v1.2、`docs/LUMINA_HYBRID_RENOVATION_PLAN.md` 阶段 3

---

## 1. 目标

按过渡期策略下线原独立服务流端点：

- `POST /api/v1/services/content-ranking/stream`
- `POST /api/v1/services/positioning/stream`
- `POST /api/v1/services/weekly-snapshot/stream`

---

## 2. 废弃策略

### 2.1 过渡期（建议 ≤ 2 周）

当 `LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=false` 时：

- 原独立端点继续可用
- 响应头增加 `Deprecation: true`
- 响应体中增加 `deprecation_notice` 字段提示迁移

### 2.2 最终下线

当 `LUMINA_UNIFIED_SYSTEM_CHAT_ONLY=true` 时：

- 对 `content-ranking`、`positioning`、`weekly-snapshot` 返回 HTTP `410 Gone`
- 响应体：

```json
{
  "detail": "This endpoint is deprecated. Please use POST /api/v1/services/system-chat/stream with natural language intent."
}
```

### 2.3 允许保留的服务

- `system-chat`：统一入口，必须保留
- `cross-platform-content`：如业务需要可保留，但建议后续也收敛到统一接口

---

## 3. 记忆 API 处理

原 `/api/v1/services/{service}/memory`（`service=content-ranking/positioning/weekly-snapshot`）：

- 过渡期：保留查询/删除能力
- 最终下线：返回 `410 Gone`

---

## 4. 错误码

| 场景 | 状态码 | 响应 |
|------|--------|------|
| 访问已废弃端点（最终下线模式） | 410 | `{"detail": "..."}` |
| 访问无效 service | 400 | 保持现有 |
| 统一接口参数校验失败 | 422 | 保持现有 |

---

## 5. 兼容性声明

- 统一接口 `POST /api/v1/services/system-chat/stream` 的协议保持不变
- 废弃端点的最终下线通过 Feature Flag 控制，支持秒级回滚
