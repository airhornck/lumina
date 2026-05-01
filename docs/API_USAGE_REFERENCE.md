# Token 用量查询接口文档

> **版本**: v1.0  
> **日期**: 2026-04-30  
> **基础 URL**: `http://localhost:8000`  
> **适用范围**: `/api/v1/usage/*`

---

## 目录

1. [统一查询接口](#1-统一查询接口)
2. [累计摘要（兼容接口）](#2-累计摘要兼容接口)
3. [按天明细（兼容接口）](#3-按天明细兼容接口)
4. [通用规范](#4-通用规范)
5. [错误码说明](#5-错误码说明)

---

## 1. 统一查询接口

### 1.1 接口概述

推荐使用此接口查询用户 LLM Token 用量。通过参数控制返回粒度：
- 仅传 `user_id` → 返回累计摘要
- 同时传日期范围 → 返回摘要 + 按天明细

| 项目 | 说明 |
|------|------|
| **接口地址** | `GET /api/v1/usage/stats` |
| **Content-Type** | `application/json` |
| **认证方式** | 无需认证（当前阶段） |

### 1.2 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `user_id` | string | **是** | 用户唯一标识 |
| `start_date` | string | 否 | 查询起始日期，格式 `YYYY-MM-DD`；必须与 `end_date` 同时提供或同时省略 |
| `end_date` | string | 否 | 查询结束日期，格式 `YYYY-MM-DD`；必须与 `start_date` 同时提供或同时省略 |

### 1.3 请求示例

**仅查累计摘要**

```bash
curl -X GET "http://localhost:8000/api/v1/usage/stats?user_id=u_001"
```

**查摘要 + 按天明细**

```bash
curl -X GET "http://localhost:8000/api/v1/usage/stats?\
user_id=u_001&start_date=2026-04-01&end_date=2026-04-30"
```

### 1.4 响应结构（仅 user_id）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "u_001",
    "summary": {
      "total_prompt_tokens": 15234,
      "total_completion_tokens": 8932,
      "total_tokens": 24166,
      "call_count": 42
    },
    "daily": null
  }
}
```

### 1.5 响应结构（带日期范围）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "u_001",
    "summary": {
      "total_prompt_tokens": 15234,
      "total_completion_tokens": 8932,
      "total_tokens": 24166,
      "call_count": 42
    },
    "daily": [
      {
        "date": "2026-04-28",
        "prompt_tokens": 1200,
        "completion_tokens": 800,
        "total_tokens": 2000,
        "call_count": 5
      },
      {
        "date": "2026-04-29",
        "prompt_tokens": 3000,
        "completion_tokens": 1500,
        "total_tokens": 4500,
        "call_count": 8
      }
    ],
    "start_date": "2026-04-01",
    "end_date": "2026-04-30"
  }
}
```

### 1.6 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | integer | `0` 表示成功，非零表示异常 |
| `message` | string | 状态描述 |
| `data` | object | 用量数据 |
| `data.user_id` | string | 用户唯一标识 |
| `data.summary` | object | 累计用量摘要 |
| `data.summary.total_prompt_tokens` | integer | 累计输入 token 数 |
| `data.summary.total_completion_tokens` | integer | 累计输出 token 数 |
| `data.summary.total_tokens` | integer | 累计总 token 数 |
| `data.summary.call_count` | integer | 累计调用次数 |
| `data.daily` | array \| null | 按天明细；未传日期范围时为 `null` |
| `data.daily[].date` | string | 日期 `YYYY-MM-DD` |
| `data.daily[].prompt_tokens` | integer | 当日输入 token 数 |
| `data.daily[].completion_tokens` | integer | 当日输出 token 数 |
| `data.daily[].total_tokens` | integer | 当日总 token 数 |
| `data.daily[].call_count` | integer | 当日调用次数 |
| `data.start_date` | string | 查询起始日期（仅传日期范围时存在） |
| `data.end_date` | string | 查询结束日期（仅传日期范围时存在） |

---

## 2. 累计摘要（兼容接口）

> ⚠️ 此接口为兼容保留，推荐使用 `/stats`。

### 2.1 接口概述

| 项目 | 说明 |
|------|------|
| **接口地址** | `GET /api/v1/usage/summary` |

### 2.2 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `user_id` | string | **是** | 用户唯一标识 |

### 2.3 响应结构

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "u_001",
    "total_prompt_tokens": 15234,
    "total_completion_tokens": 8932,
    "total_tokens": 24166,
    "call_count": 42
  }
}
```

---

## 3. 按天明细（兼容接口）

> ⚠️ 此接口为兼容保留，推荐使用 `/stats`。

### 3.1 接口概述

| 项目 | 说明 |
|------|------|
| **接口地址** | `GET /api/v1/usage/daily` |

### 3.2 请求参数

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `user_id` | string | **是** | 用户唯一标识 |
| `start_date` | string | **是** | 查询起始日期 `YYYY-MM-DD` |
| `end_date` | string | **是** | 查询结束日期 `YYYY-MM-DD` |

### 3.3 响应结构

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "u_001",
    "start_date": "2026-04-01",
    "end_date": "2026-04-30",
    "daily": [
      {
        "date": "2026-04-28",
        "prompt_tokens": 1200,
        "completion_tokens": 800,
        "total_tokens": 2000,
        "call_count": 5
      }
    ]
  }
}
```

---

## 4. 通用规范

### 4.1 返回格式统一约定

所有 `/api/v1/usage/*` 接口遵循统一包装格式：

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

### 4.2 查询限制

| 限制项 | 值 | 说明 |
|--------|-----|------|
| 最大日期范围 | 90 天 | `end_date - start_date > 90` 时返回 400 |
| 日期顺序 | `start_date <= end_date` | 否则返回 400 |
| 日期成对 | 同时提供或同时省略 | 只传一个时返回 400 |

### 4.3 与积分体系对接建议

```python
# 示例：基于用量扣减积分
resp = requests.get("/api/v1/usage/stats", params={"user_id": user_id})
data = resp.json()["data"]
total_tokens = data["summary"]["total_tokens"]
# 积分扣减逻辑...
```

---

## 5. 错误码说明

### 5.1 REST 接口错误码

| HTTP 状态码 | `code` | 含义 | 处理建议 |
|-------------|--------|------|---------|
| 200 | `0` | 成功 | — |
| 400 | — | 参数错误 | 检查 `user_id` / `start_date` / `end_date` 是否符合规范 |
| 500 | — | 服务端内部错误 | 查看服务端日志 |

### 5.2 常见参数错误

| 错误信息 | 原因 |
|---------|------|
| `start_date 和 end_date 必须同时提供或同时省略` | 只传了其中一个日期参数 |
| `end_date 不能早于 start_date` | 日期顺序颠倒 |
| `查询时间范围不能超过 90 天` | 日期跨度超过 90 天 |

---

## 附录

### 关联文档

| 文档 | 说明 |
|------|------|
| [CORE_ARCHITECTURE.md](./CORE_ARCHITECTURE.md) | 架构约束与扩展指南 |
| [4.22_API_REFERENCE.md](./4.22_API_REFERENCE.md) | Demo 工作台接口文档 |
