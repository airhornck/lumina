# Phase 3 SPEC：Skill 意图路由

> ⚠️ 本 SPEC §5 的 Orchestra 集成部分（_classify_intent 插入 Skill 意图判断）已决策退役，意图路由由 Hermes planner 承担；§6 Hermes Tool 注册部分仍然有效。详见 docs/specs/phase4_unified_planner_deprecation_spec.md。

> 文档版本：v1.1
> 日期：2026-07-07
> 依据：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` v1.2、`docs/LUMINA_HYBRID_RENOVATION_PLAN.md` 阶段 3

---

## 1. 目标

在 `MarketingOrchestra` 中增加统一 Skill 意图路由，使 `system-chat` 能够识别用户自然语言并调用三个垂直营销 Skill：

- **爆款榜单（TrendingRank）**：多平台爆款内容聚合与智能排序引擎
- **内容定位矩阵（ContentPositionMatrix）**：基于爆款分析的内容战略定位工具
- **每周决策快报（WeeklyOpsBrief）**：基于本周作品互动数据的运营决策分析引擎

---

## 2. Skill 接口契约

### 2.1 统一 Skill 接口

每个 Skill 必须实现以下入口：

```python
async def run(
    message: str,
    platform: str | None,
    context: dict[str, Any],
    history: list[dict[str, str]],
) -> str
```

返回：Markdown 或纯文本形式的回复字符串。

### 2.2 Skill 列表

| 中文名 | Skill ID | 文件路径 | 说明 |
|--------|----------|----------|------|
| 爆款榜单 | `trending_rank` / `content_ranking` | `apps/orchestra/src/orchestra/skills/trending_rank_skill.py` | 跨平台爆款内容聚合与排序 |
| 内容定位矩阵 | `content_position_matrix` / `positioning_matrix` | `apps/orchestra/src/orchestra/skills/content_position_matrix_skill.py` | 内容战略定位矩阵分析 |
| 每周决策快报 | `weekly_ops_brief` / `weekly_snapshot` | `apps/orchestra/src/orchestra/skills/weekly_ops_brief_skill.py` | 本周运营数据决策分析 |

> 注：代码实现保留历史兼容名 `content_ranking`、`positioning_matrix`、`weekly_snapshot`，对外意图识别同时支持新旧名称。

---

## 3. 意图识别规则

### 3.1 关键词匹配（规则层，优先）

```python
_TRENDING_RANK_KEYWORDS = re.compile(
    r"爆款榜单|查爆款|抖音热门|小红书爆款|B站trending|全网热点|"
    r"热门内容|趋势榜单|排行|TOP内容|热门视频|热门笔记|"
    r"内容方向榜单|排一下方向|TOP.?方向|方向优先级|内容方向怎么选|"
    r"帮我排.*方向|方向.*排序|内容方向.*排名",
    re.I,
)

_CONTENT_POSITION_MATRIX_KEYWORDS = re.compile(
    r"内容定位矩阵|定位矩阵|定位诊断|爆款定位分析|找差异化方向|"
    r"差异化定位|用矩阵帮我梳理|矩阵.*定位|梳理.*定位|"
    r"内容矩阵|分析内容定位",
    re.I,
)

_WEEKLY_OPS_BRIEF_KEYWORDS = re.compile(
    r"每周决策快报|本周快报|运营周报|决策报告|本周复盘|下周策略|"
    r"每周决策快照|本周决策|决策快照|周报整理|整理本周运营决策|"
    r"本周运营决策|运营周报",
    re.I,
)
```

### 3.2 LLM 语义兜底（可选）

当关键词未命中但用户表达与榜单/矩阵/快报强相关时，可由轻量级 LLM 进行二次判断。阶段 3 先实现关键词路由，语义兜底作为 P2 优化。

---

## 4. Skill 详细设计

### 4.1 Skill 1：爆款榜单（TrendingRank）

**定位**：多平台爆款内容聚合与智能排序引擎。

**核心能力**：
- 跨平台（抖音、B站、小红书）爆款内容采集
- 关键词搜索 + 互动数据排序 + 平台榜单查看
- 支持按时间窗口（24h/7d/30d）、垂类分类筛选

**输入参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 关键词 | string | 是 | 支持泛化扩展，如"护肤"→["skincare","成分党","平价护肤","敏感肌","早C晚A"] |
| 平台 | string | 否 | 抖音/B站/小红书/多平台聚合 |
| 时间窗口 | string | 否 | 24h/7d/30d/自定义 |
| 排序维度 | string | 否 | 点赞/评论/收藏/转发/综合互动率 |

**数据源**：
- 主数据源：红狐数据 API（Redfox）
  - 抖音：douyin-search → 热门作品搜索
  - 小红书：xiaohongshu-weeklytop → 7日爆款 TOP50
  - B站：bilibili-hot API（或自建爬虫）
- 辅助数据源：抖音指数、新榜/蝉妈妈/飞瓜、创作者服务中心

**处理流程**：
1. 关键词泛化（LLM 扩展同义词/近义词/行业黑话）
2. 数据标准化（统一字段：标题/作者/互动数/发布时间/链接）
3. 互动率计算：`综合互动率 = (点赞×1 + 评论×3 + 收藏×2 + 转发×4) / 播放量`
4. 去重与聚合（同一内容多平台分发识别）
5. 多维度加权排序

**输出**：
- 结构化榜单（JSON/Markdown 表格）
- 爆款特征摘要（LLM 生成：为什么这条爆了？）
- 趋势词云图（高频关键词提取）
- 可导出：CSV/Excel/飞书多维表格

**触发词**：查爆款榜单、抖音热门、小红书爆款、B站 trending、全网热点、内容方向榜单、排一下方向。

---

### 4.2 Skill 2：内容定位矩阵（ContentPositionMatrix）

**定位**：基于爆款分析的内容战略定位工具，将任意内容映射到"内容定位矩阵"中，识别其竞争位置与差异化机会。

**核心能力**：
- 输入单篇内容（URL/文本/截图），分析其在内容生态中的定位
- 构建"内容定位矩阵"：横轴（专业度）× 纵轴（娱乐度）× 颜色（互动强度）
- 识别内容空白区（Blue Ocean）与红海竞争区
- 输出差异化定位建议

**矩阵模型**：

```text
                    高娱乐度
                       │
    ┌──────────────────┼──────────────────┐
    │   娱乐消遣区      │     viral爆款区    │
    │  (轻松/搞笑/猎奇) │  (高专业+高娱乐)   │
    │                  │                  │
低专业度 ──────────────┼────────────────── 高专业度
    │                  │                  │
    │   日常分享区      │    知识干货区     │
    │  (生活记录/随拍)  │  (教程/测评/科普)  │
    │                  │                  │
    └──────────────────┼──────────────────┘
                    低娱乐度

    颜色维度：互动强度
    ─ 深红：超高互动（>10%）
    ─ 橙色：高互动（5%-10%）
    ─ 黄色：中等互动（2%-5%）
    ─ 灰色：低互动（<2%）
```

**输入参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 内容输入 | string | 是 | URL/文本/截图（OCR） |
| 垂类 | string | 否 | 美妆/数码/家居/职场/健身... |
| 对标账号 | list | 否 | 3-5 个竞品账号做对比 |

**分析维度**：
- 标题语义分析（情绪词/数字/痛点/悬念识别）
- 正文结构分析（信息密度、段落长度、emoji 使用）
- 视觉分析（封面类型：对比/数字/人物/清单/痛点）
- 话题标签分析（精准度/热度/竞争度）
- 专业度评分（1-10）：信息密度、专业术语、数据/案例、行业深度
- 娱乐度评分（1-10）：情绪激发、叙事张力、视觉冲击力、互动引导
- 互动强度计算（实际数据或同类内容预测）

**输出**：
- 定位坐标（专业度 X, 娱乐度 Y, 互动强度 Z）
- 矩阵可视化图（ASCII/PNG/SVG）
- 定位诊断报告与差异化策略建议（3 条可执行方向）

**触发词**：分析内容定位、内容矩阵、定位诊断、爆款定位分析、找差异化方向、定位矩阵。

---

### 4.3 Skill 3：每周决策快报（WeeklyOpsBrief）

**定位**：基于本周作品互动数据的运营决策分析引擎，自动生成 actionable 的运营策略报告。

**核心能力**：
- 自动采集本周发布作品的互动数据
- 多维度分析（内容类型/发布时间/互动结构/粉丝增长）
- 识别爆款因子与失败模式
- 输出下周运营策略建议（选题/发布/互动/投放）

**报告框架（3P 结构）**：

```text
┌─────────────────────────────────────────────────────────┐
│  📊 每周决策快报（Week of YYYY.MM.DD - YYYY.MM.DD）      │
├─────────────────────────────────────────────────────────┤
│  1. PROGRESS（本周表现）                                  │
│  ├── 核心指标仪表盘                                       │
│  ├── 内容类型表现矩阵                                     │
│  ├── 发布时间热力分析                                     │
│  └── 本周 TOP3 爆款拆解                                   │
├─────────────────────────────────────────────────────────┤
│  2. PROBLEMS（问题识别）                                  │
│  ├── 内容问题                                             │
│  ├── 发布时间问题                                         │
│  └── 互动结构问题                                         │
├─────────────────────────────────────────────────────────┤
│  3. PLANS（下周策略）                                     │
│  ├── 选题策略                                             │
│  ├── 发布策略                                             │
│  ├── 内容优化建议                                         │
│  └── 投放建议                                             │
└─────────────────────────────────────────────────────────┘
```

**输入参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 数据源 | string | 否 | 自有账号 API / 第三方数据 / 手动导入 |
| 时间范围 | string | 否 | 本周/上周/自定义 |
| 平台 | string | 否 | 小红书/抖音/B站 |

**核心指标**：
- 互动率 = `(点赞 + 评论×2 + 收藏×1.5 + 转发×3) / 曝光`
- 爆款率 = 互动率 > 5% 的内容占比
- 粉丝转化效率 = 新增粉丝 / 总曝光
- 内容衰减系数 = 发布后 72h 互动占比

**输出**：
- Markdown 报告（可直接复制到飞书/Notion）
- 可视化图表（趋势折线图/类型分布饼图/时间热力图）
- 飞书多维表格自动推送（P2）

**触发词**：生成本周快报、运营周报、决策报告、本周复盘、下周策略、每周决策快照、整理本周决策。

---

## 5. Orchestra 集成

### 5.1 `_classify_intent` 扩展

在 `_classify_intent` 中，于寒暄/闲聊判断之后、其他营销意图之前插入 Skill 意图判断：

```python
if _TRENDING_RANK_KEYWORDS.search(t):
    return {"kind": "trending_rank", "sop_id": None}
if _CONTENT_POSITION_MATRIX_KEYWORDS.search(t):
    return {"kind": "content_position_matrix", "sop_id": None}
if _WEEKLY_OPS_BRIEF_KEYWORDS.search(t):
    return {"kind": "weekly_ops_brief", "sop_id": None}
```

### 5.2 `run_dynamic` 扩展

`run_dynamic` 中对 `trending_rank`、`content_position_matrix`、`weekly_ops_brief`（及历史兼容名 `content_ranking`、`positioning_matrix`、`weekly_snapshot`）调用对应 Skill。

---

## 6. Hermes 集成

### 6.1 Tool 注册

在 `apps/api/src/services/hermes_tools.py` 中注册：

- `lumina_trending_rank`
- `lumina_content_position_matrix`
- `lumina_weekly_ops_brief`

历史兼容名 `lumina_content_ranking`、`lumina_positioning_matrix`、`lumina_weekly_snapshot` 可保留或映射到新 Tool。

### 6.2 Tool Handler

每个 Tool Handler 调用对应 Skill 的 `run` 方法，返回 JSON 字符串。

---

## 7. Feature Flag

```bash
LUMINA_ENABLE_TRENDING_RANK_SKILL=true
LUMINA_ENABLE_CONTENT_POSITION_MATRIX_SKILL=true
LUMINA_ENABLE_WEEKLY_OPS_BRIEF_SKILL=true

# 历史兼容
LUMINA_ENABLE_CONTENT_RANKING_SKILL=true
LUMINA_ENABLE_POSITIONING_MATRIX_SKILL=true
LUMINA_ENABLE_WEEKLY_SNAPSHOT_SKILL=true
```

---

## 8. 验收标准

- [ ] 关键词命中时返回对应 `intent.kind`
- [ ] Skill 返回的文本被包装为 `system-chat` SSE 格式
- [ ] Feature Flag 关闭时，对应关键词不触发 Skill
- [ ] Hermes 路径可识别并调用对应 Tool
- [ ] 三个 Skill 的详细设计文档已同步到 SPEC 与改造计划
