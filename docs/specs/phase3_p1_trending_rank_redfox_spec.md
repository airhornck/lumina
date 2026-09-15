# Phase 3 P1 SPEC：TrendingRank 红狐数据 API 接入

> 文档版本：v1.0
> 日期：2026-07-07
> 依据：`docs/specs/phase3_skill_intent_routing_spec.md`

---

## 1. 目标

为 **爆款榜单（TrendingRank）Skill** 接入红狐数据 API（Redfox），实现真实跨平台爆款数据采集，并保留 RPA fallback 路径。

---

## 2. 输入边界

### 2.1 Skill 入口

```python
async def run(
    message: str,
    platform: str | None,
    context: dict[str, Any],
    history: list[dict[str, str]],
) -> str
```

### 2.2 从 message 解析的参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 关键词 | string | 否 | 如"护肤"、"美妆"、"职场" |
| 平台 | string | 否 | douyin/xiaohongshu/bilibili/multi |
| 时间窗口 | string | 否 | 24h/7d/30d，默认 7d |
| 排序维度 | string | 否 | likes/comments/collections/shares/engagement，默认 engagement |
| 数量 | int | 否 | 默认 10，最大 50 |

---

## 3. 输出边界

### 3.1 Redfox 客户端返回结构

```python
{
    "ok": True,
    "data_source": "redfox",
    "items": [
        {
            "rank": 1,
            "title": "...",
            "author": "...",
            "platform": "douyin",
            "url": "https://...",
            "published_at": "2026-07-01T12:00:00",
            "metrics": {
                "likes": 12000,
                "comments": 800,
                "collections": 1500,
                "shares": 400,
                "views": 100000,
            },
            "engagement_rate": 0.157,
            "tags": ["护肤", "早C晚A"],
        }
    ],
    "expanded_keywords": ["护肤", "skincare", "成分党", "平价护肤"],
    "hot_keywords": ["早C晚A", "敏感肌", "成分党"],
}
```

### 3.2 Skill 输出

Markdown 表格 + 爆款特征摘要 + 趋势词云。

---

## 4. 业务规则

### 4.1 Redfox 配置

```bash
REDFOX_API_BASE_URL=https://api.redfox.example.com/v1
REDFOX_API_KEY=your_api_key
REDFOX_TIMEOUT_SECONDS=15
```

当 `REDFOX_API_KEY` 未配置或 API 调用失败时，自动降级到 RPA `fetch_trending_topics`。

### 4.2 关键词泛化

使用 LLM 将用户关键词扩展为同义词/近义词/行业黑话。扩展数量 ≤ 10 个。

### 4.3 互动率计算

```text
engagement_rate = (likes×1 + comments×3 + collections×2 + shares×4) / views
```

当 views 缺失时，使用 `likes × 10` 估算。

### 4.4 去重规则

同一标题相似度 ≥ 85%（基于 difflib.SequenceMatcher）视为重复，保留互动率最高的一条。

### 4.5 平台映射

| 用户输入 | Redfox platform |
|----------|----------------|
| 抖音 / douyin | douyin |
| 小红书 / xiaohongshu | xiaohongshu |
| B站 / bilibili | bilibili |
| 多平台 / 全网 / 不填 | multi |

---

## 5. 安全合规

- API Key 从环境变量读取，禁止硬编码
- 请求超时 15 秒，超时后降级
- 用户输入长度限制 100 字符
- 不对用户展示原始 API 错误详情

---

## 6. 错误处理

| 场景 | 行为 |
|------|------|
| Redfox 未配置 | 降级到 RPA fetch_trending_topics |
| Redfox 超时/5xx | 降级到 RPA fetch_trending_topics |
| Redfox 返回空数据 | 返回提示 + LLM 基于关键词生成通用榜单 |
| RPA 也失败 | 返回纯 LLM 生成的榜单，并标注数据来源 |

---

## 7. 接口兼容性

- 不修改 `POST /api/v1/services/system-chat/stream` 接口协议
- Skill 输出保持 Markdown 格式
