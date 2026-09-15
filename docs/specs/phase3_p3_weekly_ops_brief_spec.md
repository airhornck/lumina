# Phase 3 P3 SPEC：WeeklyOpsBrief 多源数据与 3P 报告

> 文档版本：v1.0
> 日期：2026-07-07
> 依据：`docs/specs/phase3_skill_intent_routing_spec.md`

---

## 1. 目标

为 **每周决策快报（WeeklyOpsBrief）Skill** 实现多源数据接入与 3P 结构报告生成。

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

### 2.2 数据来源

| 来源 | 优先级 | 说明 |
|------|--------|------|
| context.metrics / context.contents | 1 | 用户显式传入本周数据 |
| 第三方 API（Redfox / 新榜 / 蝉妈妈） | 2 | 需配置 API Key |
| 模拟数据 | 3 | 无真实数据时，用于展示报告结构 |

### 2.3 数据字段

```python
{
    "contents": [
        {
            "title": "...",
            "content_type": "图文/视频",
            "platform": "xiaohongshu",
            "published_at": "2026-07-01T12:00:00",
            "metrics": {
                "views": 10000,
                "likes": 500,
                "comments": 50,
                "collections": 100,
                "shares": 20,
            }
        }
    ]
}
```

---

## 3. 输出边界

### 3.1 报告结构（3P）

```text
# 📊 每周决策快报（Week of 2026.06.30 - 2026.07.07）

## 1. PROGRESS（本周表现）
- 发布量：X篇
- 总曝光：XXX万
- 总互动：XXX万
- 平均互动率：X.X%
- 爆款率：X/X = XX%
- 粉丝净增：+XXX

### 内容类型表现矩阵
| 内容类型 | 发布量 | 平均互动率 | 爆款数 |
|----------|--------|------------|--------|
| 教程干货 | 3 | 8.2% | 2 |

### 本周 TOP3 爆款
1. 《标题》... 互动率 XX%

## 2. PROBLEMS（问题识别）
- 产品测评类互动率低于均值
- 周末发布效果差

## 3. PLANS（下周策略）
- 选题：加码教程干货
- 发布：周二/周四 20:30
- 封面：增加对比型封面
- 投放：TOP1 内容追加加热
```

---

## 4. 业务规则

### 4.1 核心指标

- 互动率 = `(likes + comments×2 + collections×1.5 + shares×3) / views`
- 爆款率 = 互动率 > 5% 的内容占比
- 粉丝转化效率 = 新增粉丝 / 总曝光

### 4.2 时间范围

默认本周（当前日期往前 7 天），可通过 context 指定。

### 4.3 问题识别规则

- 某类型平均互动率低于总体均值 30% → 内容问题
- 某时段平均互动率低于总体均值 30% → 发布时间问题
- 收藏率高但评论率低 → 互动结构问题

### 4.4 策略建议规则

- 找出表现最好的内容类型 → 加码
- 找出表现最差的内容类型 → 暂停或减少
- TOP1 爆款 → 追加投放
- 收藏率 > 10% 但曝光不足 → 加热

---

## 5. 安全合规

- 无真实数据时明确标注"模拟数据"
- 不伪造具体数字
- 用户传入数据按 user_id 隔离

---

## 6. 接口兼容性

- 不修改统一接口协议
- Skill 输出保持 Markdown 格式
