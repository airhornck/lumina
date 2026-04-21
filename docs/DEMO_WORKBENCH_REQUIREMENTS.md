# Demo 创作工作台需求文档

> **状态**: 待评审  
> **版本**: v3.1（开发完成 — RPA 真实数据 + LLM 增强，全部 4 Phase 已验证）  
> **日期**: 2026-04-21  
> **范围**: `/demo` 页面三大核心能力：定位矩阵 → 本周榜单 → 跨平台内容生成  
> **核心约束**: **只扩展、不侵入**。所有实现严格通过核心架构暴露的扩展点接入，不修改任何稳定核心层的内部逻辑。具体约束见 [CORE_ARCHITECTURE.md](./CORE_ARCHITECTURE.md)

---

## 1. 产品概述

### 1.1 用户场景

运营人员打开 `/demo` 页面，完成一次完整的"从定位洞察到内容产出"的工作流：

1. **看定位**：查看自己在"专业独特性 × 市场需求度"矩阵中的位置，获取定位反馈与行动建议
2. **选选题**：浏览系统推荐的本周热门选题榜单，按适配度或热度排序
3. **去改写**：选中某个选题，一键生成适合小红书、抖音、B站等多个平台的差异化内容版本

### 1.2 用户旅程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐
│  ① 定位矩阵  │ ──► │  ② 本周榜单  │ ──► │  ③ 跨平台内容生成   │
│  (我在哪)    │     │ (写什么)    │     │ (怎么写+多平台适配) │
│             │     │             │     │                     │
│ x, y 坐标   │     │ id/name/    │     │ 小红书/抖音/B站版本 │
│ feedback    │     │ fit_score/  │     │                     │
│ suggestion  │     │ title_templates│  │                     │
└─────────────┘     └──────┬──────┘     └─────────────────────┘
                           │
                           │ "去改写" 按钮
                           ▼
                    透传选题数据：
                    - topic_id, name
                    - angles, title_templates
                    - user_position (x, y)
```

**数据流转关系**
- 定位矩阵的输出 → 影响榜单排序权重（越契合定位的选题适配度越高）
- 榜单条目的字段 → 作为内容生成的"选题种子"输入
- 三者共享同一套用户画像上下文

---

## 2. 架构约束（新增）

### 2.1 不触碰的稳定核心层

根据 [CORE_ARCHITECTURE.md](./CORE_ARCHITECTURE.md)，以下模块**只复用、不修改**：

| 层级 | 文件/模块 | 约束说明 |
|------|----------|---------|
| **API 接入层** | `apps/api/src/api/main.py` | 只新增 `include_router` 一行，不改 lifespan、CORS、健康检查 |
| **API 接入层** | `apps/api/src/services/models.py` | 不修改 `ServiceStreamRequest` 字段，业务变体走 `context` |
| **服务流层** | `apps/api/src/services/router.py` | 只新增 handler 分支 + `ALLOWED_SERVICES` 注册，不改分发逻辑 |
| **服务流层** | `apps/api/src/services/memory_service.py` | 只调用现有 `append/list_messages/clear`，不改键格式 |
| **编排层** | `apps/orchestra/src/orchestra/core.py` | 不修改 `process()` / `_classify_intent()` / `run_sop()` |
| **编排层** | `apps/orchestra/src/orchestra/router.py` | 不改 `/hub` 端点和 `MarketingHubBody` |
| **基础设施层** | `packages/llm-hub/` | 只调用 `get_client()` / `complete()` / `stream_completion()`，不改 Hub 初始化 |
| **基础设施层** | `packages/knowledge-base/` | 只读 `PlatformRegistry.load()` / `MethodologyRegistry.load()`，不改 Registry 逻辑 |
| **基础设施层** | `packages/sop-engine/` | 不修改 `compile_methodology_dag()` |
| **数据配置层** | `data/platforms/*.yml` | 只读，不删改现有平台规范结构 |
| **数据配置层** | `data/methodologies/*.yml` | 只读，不删改现有方法论结构 |
| **数据配置层** | `config/*.yaml` | 按需新增条目，不删改现有配置结构 |
| **Skill 层** | `skills/skill-*/` | **本次不调用、不修改**。`skills/` 下独立 MCP Server 未被主 API 打通，属于架构缺口，不在本次需求范围 |

### 2.2 允许的业务扩展点

| 扩展点 | 本次使用方式 |
|--------|-------------|
| **新增 REST Router** | 新建 `apps/api/src/api/demo_router.py`，`main.py` 中 `include_router` |
| **新增 SSE Service Handler** | 新建 `services/handlers/cross_platform_content.py`，`services/router.py` 中注册 |
| **通过 `context` 扩展字段** | `ServiceStreamRequest.context` 中传递 `seed_topic`、`user_position`、`target_platforms` |
| **通过 `llm_hub` 调用 LLM** | 直接调用 `get_client()` + `complete()` / `stream_completion()` |
| **通过 `PlatformRegistry` 读取规范** | 只读调用 `load(platform_id)` 获取 `content_dna` / `audit_rules` / `content_formats` |
| **通过 `MethodologyRegistry` 读取方法论** | 只读调用 `find_best_match()` / `load()` 获取方法论 prompt |

---

## 3. 现状分析

### 3.1 已有能力（复用，不改动）

| 模块 | 已有能力 | 位置 | 本需求如何使用 |
|------|---------|------|--------------|
| **LLM Hub** | 统一的 LLM 调用与流式输出 | `packages/llm-hub/` | 三个模块直接调用 `get_client()` 生成结构化数据 |
| **平台规范库** | 已定义小红书/抖音/B站的 content_dna / audit_rules / content_formats | `data/platforms/*.yml` | 三个模块只读复用，注入 LLM Prompt |
| **方法论库** | 内容方法论匹配（AIDA / hook-story-offer 等） | `packages/knowledge-base/` | 内容生成模块只读复用，匹配最佳方法论 |
| **服务流接口** | 已有 SSE 服务流框架：`POST /api/v1/services/{service}/stream` | `apps/api/src/services/router.py` | 内容生成模块注册为新增 service |
| **会话记忆** | `ServiceMemoryStore` 提供 `append/list_messages/clear` | `apps/api/src/services/memory_service.py` | 内容生成模块接入多轮对话记忆 |

> **注意**：本次不依赖 `apps/orchestra/` 的意图识别和编排，也不依赖 `skills/skill-*/` 的独立 MCP Server。定位矩阵、本周榜单、跨平台内容生成三个模块直接在 API 层实现，底层只调用 `llm_hub` + `knowledge-base`。

### 3.2 关键缺失（本次需补齐）

| 缺失项 | 影响 | 严重程度 |
|--------|------|---------|
| 无定位矩阵 REST 接口 | 前端 `/demo` 页面无法展示坐标图 | 🔴 高 |
| 无本周榜单 REST 接口 | 前端 `/demo` 页面无法展示选题表格 | 🔴 高 |
| 无跨平台内容生成 SSE 接口 | 无法通过统一服务流消费多平台生成结果 | 🔴 高 |
| 无 LLM 语义级平台改写逻辑 | 各平台版本如果只是截断会缺乏风格差异 | 🔴 高 |
| 输出结构不统一 | 前端难以标准化渲染 | 🟡 中 |

> **已解决（RPA 链路打通）**：
> 
> | 缺失项 | 解决方式 | 状态 |
> |--------|---------|------|
> | 榜单数据来源不真实 | 通过 `fetch_trending_topics` RPA 抓取抖音/小红书/B站真实热门话题 | ✅ 已打通 |
> | 小红书需要登录 | 通过 Cookie 登录（`data/credentials/xiaohongshu_cookies.txt`） | ✅ 已验证 |

---

## 4. 需求范围

### 4.1 In Scope

- **定位矩阵接口**：返回用户坐标 `(x, y)` + 定位反馈 + 行动建议
- **本周榜单接口**：返回选题列表（支持排序、分页），含选题元数据与扩展字段
- **跨平台内容生成接口**：接收自然语言或选题种子，SSE 流式返回多平台适配内容
- **用户画像上下文共享**：三个模块共用 `industry/stage/platform/goal/pain_point`
- **榜单到内容生成的数据透传**："去改写"按钮携带选题数据进入生成流程

### 4.2 Out of Scope

- 自动发布到各平台（RPA 执行，需 `skill-rpa-executor` 后续串联）
- 图片/视频的实际生成（仅输出内容文案与素材建议）
- ~~真实热点数据采集与持久化~~（已通过 RPA 抓取实现，见 8.2 实现策略）
- 用户级账号矩阵管理（多账号选择，后续由 `skill-matrix-commander` 支持）
- **修改任何稳定核心层的内部逻辑**（见 2.1 清单）
- **打通 `skills/` 独立 MCP Server 与主 API 的调用链路**（属于架构缺口，不在本次需求范围）

---

## 5. 系统架构

### 5.1 核心原则：扩展而非改造

现有四层架构保持不变：

```
Layer 1: OpenClaw (外部网关)
Layer 2: Orchestra (意图 + 编排)  ← 本次不经过此层
Layer 3: Skill Hub (MCP Skills)   ← 本次不经过此层
Layer 4: LLM Hub + 知识库         ← 直接调用
```

本次只在 **API 接入层** 新增扩展点，**绕过 Orchestra 和独立 Skill**，直接在 Handler 中编排 LLM 调用：

```
apps/api/src/api/main.py
├── /api/v1/services/*            (已有，不变)
│   └── POST /cross-platform-content/stream  ← 新增注册
├── /api/v1/marketing/*           (已有，不变，本次不走)
└── /api/v1/demo/*                ← 新增 Router (本周榜单 + 定位矩阵)
```

### 5.2 系统交互图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端 /demo 页面                                 │
├──────────────┬──────────────┬───────────────────────────────────────────────┤
│  定位矩阵     │  本周榜单     │              跨平台内容生成                      │
│  (坐标图)     │  (表格+排序)  │              (生成中动画 + 结果卡片)              │
└──────┬───────┴──────┬───────┴───────────────────────┬───────────────────────┘
       │              │                               │
       │ GET          │ GET                           │ POST SSE
       ▼              ▼                               ▼
┌──────────────┐ ┌──────────────┐         ┌─────────────────────────────┐
│ /api/v1/demo/│ │ /api/v1/demo/│         │  services/router.py         │
│ position-    │ │ weekly-      │         │  (ALLOWED_SERVICES 新增)     │
│ matrix       │ │ rankings     │         └─────────────┬───────────────┘
└──────┬───────┘ └──────┬───────┘                       │
       │                │                               │
       └────────────────┴───────────────┐               │
                                        │               │
                              ┌─────────▼───────────────▼──────────────┐
                              │        新增模块（本次开发）              │
                              │                                        │
                              │  ┌─────────────────────────────────┐   │
                              │  │ demo_router.py                  │   │
                              │  │ · get_position_matrix()         │   │
                              │  │ · get_weekly_rankings()         │   │
                              │  └─────────────────────────────────┘   │
                              │  ┌─────────────────────────────────┐   │
                              │  │ cross_platform_content.py       │   │
                              │  │ (Service Handler)               │   │
                              │  │ · handle_cross_platform_stream  │   │
                              │  └─────────────────────────────────┘   │
                              └─────────────────┬──────────────────────┘
                                                │
                          ┌─────────────────────┼─────────────────────┐
                          │                     │                     │
                          ▼                     ▼                     ▼
                   ┌─────────────┐      ┌─────────────┐      ┌─────────────────┐
                   │  llm_hub    │      │ Platform    │      │ Methodology     │
                   │ (LLM调用)   │      │ Registry    │      │ Registry        │
                   │             │      │ (只读)      │      │ (只读)          │
                   └─────────────┘      └─────────────┘      └─────────────────┘
```

> **重要**：本次实现**不经过 `skills/skill-bulk-creative/`**。该 Skill 是独立 MCP Server，当前未被主 API 真实调用（`skill_router.py` 仍为 Mock）。直接修改它属于"侵入"，且修改后也无法通过主 API 调用。正确的做法是在 Service Handler 中直接编排 `llm_hub` + `PlatformRegistry` + `MethodologyRegistry`。

### 5.3 数据流转：榜单 → 内容生成

榜单中的"去改写"按钮触发内容生成时，通过 `context.seed_topic` 透传数据：

```json
{
  "message": "改写这个选题供多平台发布",
  "context": {
    "target_platforms": ["xiaohongshu", "douyin", "bilibili"],
    "seed_topic": {
      "id": "topic_001",
      "name": "个人IP定位方法论",
      "source": "小红书",
      "fit_score": 92,
      "heat": 95,
      "angles": ["差异化定位", "价值主张清晰"],
      "title_templates": [
        "为什么[你的领域]需要重新定义个人IP？",
        "[你的名字]如何用3个月找到定位？"
      ]
    },
    "user_position": {
      "x": 72,
      "y": 78,
      "feedback": "你的定位比较清晰，有专业特色也有市场需求。"
    }
  }
}
```

---

## 6. 接口设计

### 6.1 定位矩阵

```http
GET /api/v1/demo/position-matrix
```

**请求参数**

| 字段 | 类型 | 必填 | 示例 | 说明 |
|------|------|------|------|------|
| `user_id` | string | 否 | `u123` | 若后端不能从登录态识别用户则必传 |
| `profile_id` | string | 否 | `profile_xxx` | 与 `user_id` 二选一 |
| `industry` | string | 否 | `教育` | 预留计算逻辑 |
| `stage` | string | 否 | `起步` | 预留计算逻辑 |
| `platform` | string | 否 | `抖音` | 当前运营平台 |
| `goal` | string | 否 | `涨粉` | 运营目标 |
| `pain_point` | string | 否 | `选题靠感觉` | 当前痛点 |

**响应结构**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "x": 72,
    "y": 78,
    "feedback": "你的定位比较清晰，有专业特色也有市场需求。",
    "suggestion": "接下来用案例内容放大你的独特性。"
  }
}
```

**字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `x` | number | 是 | 横轴坐标 0-100，表示"专业独特性" |
| `y` | number | 是 | 纵轴坐标 0-100，表示"市场需求度" |
| `feedback` | string | 是 | 定位反馈文案 |
| `suggestion` | string | 是 | 行动建议文案 |

**空态约定**

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

### 6.2 本周榜单

```http
GET /api/v1/demo/weekly-rankings
```

**请求参数**

| 字段 | 类型 | 必填 | 示例 | 说明 |
|------|------|------|------|------|
| `sort_by` | string | 否 | `fit_score` | 排序方式：`fit_score` / `heat`，默认 `fit_score` |
| `limit` | int | 否 | `10` | 返回数量，默认 10 |
| `user_id` | string | 否 | `u123` | 用户标识 |
| `profile_id` | string | 否 | `profile_xxx` | 与 `user_id` 二选一 |
| `industry` | string | 否 | `教育` | 预留个性化推荐 |
| `stage` | string | 否 | `起步` | 预留个性化推荐 |
| `platform` | string | 否 | `抖音` | 预留个性化推荐 |
| `goal` | string | 否 | `涨粉` | 预留个性化推荐 |
| `pain_point` | string | 否 | `选题靠感觉` | 预留个性化推荐 |

**响应结构**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      {
        "id": "topic_001",
        "name": "个人IP定位方法论",
        "source": "小红书",
        "fit_score": 92,
        "heat": 95,
        "delta": 12,
        "risk_level": "low",
        "angles": ["差异化定位", "价值主张清晰", "目标用户明确"],
        "title_templates": [
          "为什么[你的领域]需要重新定义个人IP？",
          "[你的名字]如何用3个月找到定位？"
        ],
        "warnings": []
      }
    ],
    "total": 10
  }
}
```

**字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `list` | array | 是 | 榜单列表 |
| `total` | int | 否 | 总条数 |
| `list[].id` | string | 是 | 选题唯一标识 |
| `list[].name` | string | 是 | 选题名称（方向） |
| `list[].source` | string | 是 | 热点来源平台 |
| `list[].fit_score` | number | 是 | 适配度 0-100 |
| `list[].heat` | number | 是 | 热度值 |
| `list[].delta` | number | 否 | 热度变化值 |
| `list[].risk_level` | string | 否 | 风险等级：`low` / `medium` / `high` |
| `list[].angles` | string[] | 否 | 推荐切入角度 |
| `list[].title_templates` | string[] | 否 | 推荐标题模板 |
| `list[].warnings` | string[] | 否 | 风险提示 |

**空态约定**

```json
{
  "code": 0,
  "message": "success",
  "data": { "list": [], "total": 0 }
}
```

---

### 6.3 跨平台内容生成

```http
POST /api/v1/services/cross-platform-content/stream
Content-Type: application/json
```

**请求体**（复用现有 `ServiceStreamRequest`，通过 `context` 扩展）

```json
{
  "user_id": "u123",
  "conversation_id": "c456",
  "message": "生成一篇职场穿搭干货，适配小红书、抖音、B站",
  "platform": null,
  "context": {
    "target_platforms": ["xiaohongshu", "douyin", "bilibili"],
    "content_type": "图文",
    "seed_topic": {
      "id": "topic_001",
      "name": "个人IP定位方法论",
      "angles": ["差异化定位"],
      "title_templates": ["为什么[你的领域]需要重新定义个人IP？"]
    },
    "user_position": {
      "x": 72,
      "y": 78,
      "feedback": "你的定位比较清晰..."
    },
    "master_content": {
      "title": "职场穿搭的三个黄金法则",
      "content": "正文内容...",
      "topic": "职场穿搭"
    },
    "optimization_goal": "engagement",
    "niche": "职场"
  },
  "mode": null
}
```

**context 字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `target_platforms` | string[] | 否 | 目标平台列表，未提供则从 `message` 解析 |
| `content_type` | string | 否 | 图文 / 视频 / 仅文字，默认"图文" |
| `seed_topic` | object | 否 | 来自榜单的选题种子（含 angles / title_templates） |
| `user_position` | object | 否 | 来自定位矩阵的用户坐标与反馈 |
| `master_content` | object | 否 | 若用户已提供核心内容则直接适配，否则由 LLM 生成 |
| `optimization_goal` | string | 否 | 优化目标：`engagement` / `conversion` / `reach` |
| `niche` | string | 否 | 垂直领域，用于变体生成 |

**SSE 响应流**

```text
data: {"type": "start", "service": "cross-platform-content", "platforms": ["xiaohongshu", "douyin", "bilibili"]}

data: {"type": "platform_chunk", "platform": "xiaohongshu", "content": {"title":"...","body":"...","hashtags":["..."],"format_tips":"..."}}

data: {"type": "platform_chunk", "platform": "douyin", "content": {"title":"...","script":"...","hook":"...","hashtags":["..."],"duration_tip":"30-60秒"}}

data: {"type": "platform_chunk", "platform": "bilibili", "content": {"title":"...","sections":"...","danmu_prompt":"...","hashtags":["..."]}}

data: {"type": "done", "total_platforms": 3, "full_length": 1580}
```

**事件类型说明**

| type | 说明 |
|------|------|
| `start` | 开始生成，返回目标平台列表 |
| `platform_chunk` | 单个平台内容生成完毕，按平台逐条推送 |
| `delta` | （可选）若某平台内容较长，可进一步拆分段落增量推送 |
| `warning` | 合规风险提示（如命中某平台审核敏感词） |
| `error` | 某平台生成失败，返回错误信息但继续其他平台 |
| `done` | 全部完成 |

---

## 7. 数据模型

### 7.1 共享用户画像（User Profile Context）

三个模块共用同一套画像参数，前端可缓存并在三个接口间透传：

```typescript
interface UserProfileContext {
  user_id?: string;
  profile_id?: string;
  industry?: string;      // 行业：教育 / 美妆 / 职场 / ...
  stage?: string;         // 阶段：起步 / 成长 / 成熟
  platform?: string;      // 主运营平台：小红书 / 抖音 / B站
  goal?: string;          // 目标：涨粉 / 转化 / 品牌
  pain_point?: string;    // 痛点：选题靠感觉 / 内容没流量 / ...
}
```

### 7.2 定位矩阵输出

```typescript
interface PositionMatrixData {
  x: number;              // 0-100，专业独特性
  y: number;              // 0-100，市场需求度
  feedback: string;       // 定位反馈
  suggestion: string;     // 行动建议
}
```

### 7.3 本周榜单条目

```typescript
interface RankingItem {
  id: string;
  name: string;           // 选题名称
  source: string;         // 热点来源平台
  fit_score: number;      // 适配度 0-100
  heat: number;           // 热度值
  delta?: number;         // 热度变化值
  risk_level?: "low" | "medium" | "high";
  angles?: string[];      // 推荐切入角度
  title_templates?: string[];  // 推荐标题模板
  warnings?: string[];    // 风险提示
}

interface WeeklyRankingsData {
  list: RankingItem[];
  total: number;
}
```

### 7.4 跨平台内容输出（按平台）

```typescript
interface CrossPlatformContentResponse {
  type: "platform_chunk";
  platform: string;
  content: PlatformContent;
}

interface PlatformContent {
  // 通用字段
  title: string;
  body: string;
  hashtags: string[];
  
  // 平台-specific 字段
  format?: string;            // 图文 / 视频 / 仅文字
  hook?: string;              // 抖音：黄金3秒钩子
  script_segments?: string[]; // 抖音/B站：分段脚本
  duration_tip?: string;      // 视频时长建议
  pic_count_tip?: string;     // 小红书：图片数量建议
  pic_ratio?: string;         // 小红书：图片比例建议
  danmu_prompt?: string;      // B站：弹幕引导语
  
  // 策略建议
  best_time?: string;
  methodology?: string;
  compliance_warnings?: string[];
  style_guide?: string;
}
```

---

## 8. 实现方案

### 8.1 新增文件清单（严格遵循架构约束）

| 文件 | 用途 | 类型 | 是否触碰核心 |
|------|------|------|-------------|
| `apps/api/src/api/demo_router.py` | `/api/v1/demo/*` REST 路由（矩阵 + 榜单） | ✅ 新增 | ❌ 否 |
| `apps/api/src/services/handlers/cross_platform_content.py` | 跨平台内容生成 SSE Handler | ✅ 新增 | ❌ 否 |
| `apps/api/src/services/router.py` | `ALLOWED_SERVICES` 新增 `"cross-platform-content"` | 🟡 小改 | ❌ 否（纯注册） |
| `apps/api/src/api/main.py` | 新增一行 `app.include_router(demo_router)` | 🟡 小改 | ❌ 否（标准扩展点） |
| `skills/skill-bulk-creative/main.py` | ~~增强 `adapt_platform`~~ | — | ❌ **本次不修改** |
| `apps/orchestra/src/orchestra/core.py` | ~~新增意图分支~~ | — | ❌ **本次不修改** |

### 8.2 定位矩阵与榜单的实现策略

#### 定位矩阵 — LLM 生成

定位矩阵没有外部真实数据源，继续采用 **"LLM 生成结构化 JSON"** 策略：

```python
# demo_router.py 中定位矩阵的实现

@router.get("/position-matrix")
async def get_position_matrix(...):
    client = get_client(skill_name="demo_matrix")
    prompt = f"""
    基于用户画像：行业={industry}、阶段={stage}、平台={platform}、目标={goal}、痛点={pain_point}
    生成定位矩阵分析结果。
    必须严格按以下 JSON 格式输出：
    {{
      "x": <0-100的整数>,
      "y": <0-100的整数>,
      "feedback": "定位反馈文案...",
      "suggestion": "行动建议文案..."
    }}
    """
    response = await client.complete(prompt, response_format={"type": "json_object"})
    return {"code": 0, "message": "success", "data": json.loads(response.content)}
```

#### 本周榜单 — RPA 真实抓取 + LLM 增强

榜单采用 **"RPA 抓取真实热门话题 → LLM 基于真实数据生成结构化榜单"** 的混合策略：

```python
# demo_router.py 中榜单的实现（混合策略：RPA + LLM）

from lumina_skills.tool_skills import fetch_trending_topics
from lumina_skills.registry import TOOL_REGISTRY
from llm_hub import get_client

@router.get("/weekly-rankings")
async def get_weekly_rankings(
    sort_by: str = "fit_score",
    limit: int = 10,
    industry: str | None = None,
    stage: str | None = None,
    platform: str | None = None,
    goal: str | None = None,
    pain_point: str | None = None,
):
    # Step 1: 抓取各平台真实热门话题（RPA）
    real_topics = []
    for pf in ["douyin", "bilibili"]:
        try:
            result = await fetch_trending_topics(pf, limit=10)
            for t in result.get("topics", [])[:5]:
                real_topics.append({"source": pf, "title": t["title"]})
        except Exception:
            pass
    
    # 小红书需要 Cookie，单独处理
    try:
        result = await fetch_trending_topics("xiaohongshu", limit=10)
        for t in result.get("topics", [])[:5]:
            real_topics.append({"source": "xiaohongshu", "title": t["title"]})
    except Exception:
        pass
    
    # Step 2: 用 LLM 基于真实话题 + 用户画像生成结构化榜单
    client = get_client(skill_name="demo_rankings")
    prompt = f"""
    基于以下真实热门话题和用户画像，生成本周推荐选题榜单。
    
    【真实热门话题】（来自平台实时抓取）
    {chr(10).join([f"- [{t['source']}] {t['title']}" for t in real_topics]) if real_topics else "（暂无实时数据）"}
    
    【用户画像】
    行业：{industry}，阶段：{stage}，平台：{platform}，目标：{goal}，痛点：{pain_point}
    
    要求：
    - 结合真实热门话题和用户画像，推荐最有价值的选题
    - fit_score 表示该选题对用户的匹配程度（0-100）
    - heat 表示该选题的市场热度（0-100），可参考真实话题排名
    - 输出严格 JSON 格式
    
    输出格式：
    {{
      "list": [
        {{
          "id": "topic_001",
          "name": "选题名称",
          "source": "来源平台",
          "fit_score": 92,
          "heat": 95,
          "delta": 12,
          "risk_level": "low",
          "angles": ["切入角度1", "切入角度2"],
          "title_templates": ["标题模板1", "标题模板2"],
          "warnings": []
        }}
      ],
      "total": {limit}
    }}
    """
    
    response = await client.complete(prompt, response_format={"type": "json_object"})
    data = json.loads(response.content)
    data["data_source"] = "rpa+llm" if real_topics else "llm_only"
    return {"code": 0, "message": "success", "data": data}
```

> **说明**：
> - **RPA 抓取**：复用 `fetch_trending_topics`（已注册到 `TOOL_REGISTRY`），通过 Playwright 无头浏览器抓取真实热门话题
> - **抖音/B站**：无需登录，直接访问热榜页抓取
> - **小红书**：通过 `data/credentials/xiaohongshu_cookies.txt` 加载 Cookie 后访问
> - **LLM 增强**：RPA 抓取提供"热度"素材，LLM 基于用户画像计算"适配度"并生成结构化输出
> - **降级策略**：若 RPA 抓取失败（网络异常/反爬/Cookie 过期），自动降级为纯 LLM 生成，功能不中断

### 8.3 跨平台内容生成的实现策略（直接编排 LLM，不经过 Skill）

在 `cross_platform_content.py` 中，**直接在 Handler 内编排 LLM 调用**，不依赖 `skill-bulk-creative`：

```python
from llm_hub import get_client
from knowledge_base.platform_registry import PlatformRegistry
from knowledge_base.methodology_registry import MethodologyRegistry
from services.memory_service import ServiceMemoryStore

async def handle_cross_platform_content_stream(
    user_id: str,
    conversation_id: str,
    message: str,
    platform: str | None,
    context: dict,
    store: ServiceMemoryStore,
) -> AsyncIterator[str]:
    service = "cross-platform-content"
    
    # 1. 提取参数
    target_platforms = context.get("target_platforms") or _extract_platforms_from_message(message)
    seed_topic = context.get("seed_topic")
    user_position = context.get("user_position")
    master = context.get("master_content")
    
    # 2. 若用户未提供核心内容，由 LLM 基于 seed_topic 生成
    if not master and seed_topic:
        master = await _generate_master_from_seed(seed_topic, user_position)
    elif not master:
        master = await _generate_master_from_message(message)
    
    yield _sse({"type": "start", "service": service, "platforms": target_platforms})
    
    # 3. 匹配最佳方法论（只读调用 MethodologyRegistry）
    methodology = MethodologyRegistry().find_best_match(
        query=master.get("topic", ""),
        industry=context.get("industry"),
        goal=context.get("optimization_goal")
    )
    
    # 4. 逐平台适配（直接调用 LLM，不经过 skill-bulk-creative）
    for pf in target_platforms:
        try:
            # 4.1 读取平台规范（只读调用 PlatformRegistry）
            spec = PlatformRegistry().load(pf)
            
            # 4.2 构建 LLM Prompt，注入平台 DNA + 审核规则 + 格式约束 + 方法论
            prompt = _build_platform_prompt(
                master_content=master,
                platform=pf,
                spec=spec,
                methodology=methodology,
                seed_topic=seed_topic,
                user_position=user_position,
            )
            
            # 4.3 调用 LLM 生成结构化内容
            client = get_client(skill_name="cross_platform_content")
            response = await client.complete(
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = json.loads(response.content)
            
            # 4.4 流式推送
            yield _sse({"type": "platform_chunk", "platform": pf, "content": content})
            
        except Exception as e:
            yield _sse({"type": "error", "platform": pf, "message": str(e)[:500]})
            continue  # 单平台失败不影响其他平台
    
    yield _sse({"type": "done", "total_platforms": len(target_platforms)})
```

### 8.4 `_build_platform_prompt` 核心逻辑

```python
def _build_platform_prompt(master_content, platform, spec, methodology, seed_topic, user_position):
    """构建平台适配 Prompt，注入所有约束条件"""
    
    # 从 PlatformRegistry 读取的规范（只读，不改）
    dna_lines = [f"{item.get('element', '')}: {item.get('value', '')}" for item in spec.content_dna]
    audit_lines = [
        f"{rule.get('category', '')}类禁用词: {', '.join(rule.get('forbidden_terms', []))}"
        for rule in spec.audit_rules
    ]
    
    # 从 content_formats 读取格式约束
    formats = spec.content_formats
    format_constraints = []
    for fmt_name, fmt_cfg in formats.items():
        if isinstance(fmt_cfg, dict) and not fmt_cfg.get("note"):
            format_constraints.append(f"{fmt_name}: {fmt_cfg}")
    
    # 方法论引导
    meth_guide = ""
    if methodology:
        meth_guide = f"""
内容方法论：{methodology.name}
步骤框架：{methodology.steps}
"""
    
    # 选题种子信息
    seed_info = ""
    if seed_topic:
        seed_info = f"""
选题信息：
- 名称：{seed_topic.get('name')}
- 切入角度：{', '.join(seed_topic.get('angles', []))}
- 推荐标题模板：{seed_topic.get('title_templates', [])}
"""
    
    # 用户定位信息
    position_info = ""
    if user_position:
        position_info = f"""
用户定位：
- 专业独特性：{user_position.get('x')}/100
- 市场需求度：{user_position.get('y')}/100
- 定位反馈：{user_position.get('feedback')}
"""
    
    prompt = f"""
请将以下内容改写为适合 **{platform}** 平台的版本。

【平台 DNA】
{chr(10).join(dna_lines)}

【审核规则】
{chr(10).join(audit_lines)}

【格式约束】
{chr(10).join(format_constraints)}

{meth_guide}
{seed_info}
{position_info}

【原始内容】
标题：{master_content.get('title')}
正文：{master_content.get('content')}

【输出要求】
请输出严格符合以下 JSON 格式的内容：
{{
  "title": "平台适配后的标题（符合平台长度限制）",
  "body": "平台适配后的正文内容（符合平台风格）",
  "hashtags": ["标签1", "标签2"],
  "hook": "如果是视频平台，写出黄金3秒钩子",
  "best_time": "建议发布时间",
  "compliance_warnings": ["如有合规风险请列出"]
}}
"""
    return prompt
```

> **为什么不在 `skill-bulk-creative` 中实现？**
> 1. `skill-bulk-creative` 是独立 MCP Server，当前未被主 API 真实调用（`skill_router.py` 仍为 Mock）
> 2. 修改它属于"侵入"，且修改后仍无法通过现有 API 调用链路使用
> 3. 直接在 Service Handler 中编排 LLM 调用更简洁，完全复用现有 `llm_hub` + `knowledge-base`
> 4. 未来如需复用此逻辑，可将其提取为 `packages/lumina-skills/` 下的内联工具，通过 `TOOL_REGISTRY` 注册（符合架构扩展规范）

---

## 9. 实施计划（RGA 红绿灯跟踪 — ✅ 全部完成）

> 本章节采用 **Simon Willison Red/Green/Amber (RGA) 红绿灯法** 跟踪任务状态。  
> 🟢 = 已验证完成　🟡 = 部分完成（有已知限制）　🔴 = 未完成（阻塞中）  
> **完整跟踪文档**: [DEVELOPMENT_PLAN_RGA.md](./DEVELOPMENT_PLAN_RGA.md)  
> **集成测试**: `tests/test_demo_workbench.py` — **12/12 全部通过**

### Phase 0：RPA 抓取链路（✅ 已完成）

| # | 任务 | 状态 | 验证方式 |
|---|------|------|---------|
| P0-1 | `fetch_trending_topics` 注册到 `TOOL_REGISTRY` | 🟢 Green | `registry.py` 中存在该键 |
| P0-2 | 抖音热榜抓取（无需登录） | 🟢 Green | 10 条真实话题已验证 |
| P0-3 | B站热门抓取（无需登录） | 🟢 Green | 10 条真实视频已验证 |
| P0-4 | 小红书热门抓取（需 Cookie） | 🟢 Green | 7 条真实笔记已验证 |
| P0-5 | Playwright 配置修复 | 🟢 Green | 超时+选择器+URL 已修正 |
| P0-6 | 测试结果持久化 | 🟢 Green | `tests/rpa_test_results.json` 存在 |

### Phase 1：基础接口（✅ 已完成）

| # | 任务 | 状态 | 验证方式 | 实现文件 |
|---|------|------|---------|---------|
| P1-1 | 创建 `demo_router.py` | 🟢 Green | 文件存在且 FastAPI 可加载 | `demo_router.py` |
| P1-2 | 实现 `GET /position-matrix` | 🟢 Green | `test_position_matrix_endpoint_exists` PASS | `demo_router.py` |
| P1-3 | 实现 `GET /weekly-rankings` | 🟢 Green | `test_weekly_rankings_endpoint_exists` PASS | `demo_router.py` |
| P1-4 | 统一返回格式 | 🟢 Green | `test_position_matrix_response_format` PASS | `demo_router.py` |
| P1-5 | 空态 + `data_source` | 🟢 Green | `test_weekly_rankings_data_source_field` PASS | `demo_router.py` |
| P1-6 | 创建 `cross_platform_content.py` | 🟢 Green | 文件存在且被 router 导入 | `cross_platform_content.py` |
| P1-7 | 实现 SSE handler | 🟢 Green | `test_cross_platform_stream_events` PASS | `cross_platform_content.py` |
| P1-8 | `seed_topic` / `user_position` 透传 | 🟢 Green | handler 中读取 context 并注入 Prompt | `cross_platform_content.py` |
| P1-9 | `PlatformRegistry.load()` | 🟢 Green | 逐平台调用读取规范 | `cross_platform_content.py` |
| P1-10 | `MethodologyRegistry.find_best_match()` | 🟢 Green | 匹配并注入 Prompt | `cross_platform_content.py` |
| P1-11 | 注册到框架 | 🟢 Green | `test_service_registered` PASS | `router.py`, `main.py` |

### Phase 2：质量增强（✅ 已完成）

| # | 任务 | 状态 | 验证方式 | 实现位置 |
|---|------|------|---------|---------|
| P2-1 | 方法论注入 Prompt | 🟢 Green | `_build_platform_prompt` 注入 methodology | `cross_platform_content.py` |
| P2-2 | 基于 `audit_rules` 合规扫描 | 🟢 Green | `_scan_compliance()` 遍历禁用词 | `cross_platform_content.py` |
| P2-3 | `warning` 事件 SSE 推送 | 🟢 Green | 命中敏感词时 yield warning | `cross_platform_content.py` |
| P2-4 | 接入 `ServiceMemoryStore` | 🟢 Green | `list_messages` + `append` | `cross_platform_content.py` |
| P2-5 | 多轮对话修稿 | 🟢 Green | `_is_revision_request()` + `_revise_platform_content()` | `cross_platform_content.py` |
| P2-6 | `store.append()` / `list_messages()` | 🟢 Green | 用户消息和结果均保存 | `cross_platform_content.py` |

### Phase 3：体验优化（✅ 已完成）

| # | 任务 | 状态 | 验证方式 | 实现位置 |
|---|------|------|---------|---------|
| P3-1 | `sort_by` 真实生效 | 🟢 Green | `_apply_sort_and_pagination()` 二次排序 | `demo_router.py` |
| P3-2 | `limit` / `offset` 分页 | 🟢 Green | `offset` Query 参数 + 切片 | `demo_router.py` |
| P3-3 | Prompt 提取为模板文件 | 🟢 Green | `prompts/*.txt` 5 个模板 + 热更新 | `prompts/` 目录 |
| P3-4 | 图文/视频/仅文字差异化 Prompt | 🟢 Green | `content_type` 传入 + 平台字段差异化 | `cross_platform_content.py` |

---

### 完成汇总

- **新增文件**: 4 个（`demo_router.py`, `cross_platform_content.py`, `test_demo_workbench.py`, `prompts/*.txt` ×5）
- **修改文件**: 2 个（`services/router.py`, `api/main.py`）
- **总任务**: 27 个，全部 🟢 Green
- **测试通过率**: 12/12（100%）
- **架构约束遵守**: 零侵入 — 未修改任何 12 个稳定核心文件

---

## 10. 风险与假设

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 生成结构化 JSON 不稳定 | 接口解析失败 | Prompt 中明确 JSON Schema；增加 `try/except` + 重试机制；失败时返回降级文本 |
| LLM 改写质量不稳定 | 各平台版本风格同质化 | Prompt 中强化平台 DNA 示例；增加 few-shot 示例；接入方法论引导 |
| 平台规范库 YAML 更新滞后 | 新规则未适配 | 规范库版本化管理；定期同步；Prompt 中动态注入当前规范 |
| 榜单/矩阵 LLM 生成延迟较高 | 页面加载慢 | 后续增加缓存层（Redis），当前 MVP 阶段可接受 1-3s 延迟 |
| 同进程 LLM 串行调用导致整体延迟 | 多平台生成时用户等待久 | 使用 `asyncio.gather` 并行生成各平台内容（注意 LLM 客户端并发限制） |
| RPA 抓取链路稳定性 | 小红书 Cookie 过期 / 平台改版 / 反爬升级 | 捕获异常降级到 LLM 生成；定期更新 Cookie；监控 DOM 结构变化 |
| 小红书 Cookie 过期 | 小红书热门话题无法抓取 | 定期手动更新 `data/credentials/xiaohongshu_cookies.txt`（当前无自动化登录方案） |

### 关键假设

1. Demo/MVP 阶段，**榜单数据优先使用 RPA 抓取的真实热门话题**，RPA 失败时自动降级为纯 LLM 生成；定位矩阵数据由 LLM 生成
2. 用户画像参数（`industry` / `stage` / `platform` / `goal` / `pain_point`）由前端收集并缓存透传
3. LLM 输出遵循 JSON Schema，可解析为结构化数据
4. 前端 `/demo` 页面具备消费 SSE 流的能力（用于内容生成）
5. 跨平台内容生成时，用户提供的核心内容（或系统生成的初稿）为中文
6. 小红书 Cookie 文件 `data/credentials/xiaohongshu_cookies.txt` 保持有效（需定期手动更新）

---

## 11. 附录

### 11.1 架构约束速查

| 需求场景 | 正确做法 | 本次是否涉及 |
|---------|---------|-------------|
| 新增 REST 接口 | 新建 `demo_router.py` → `main.py` include_router | ✅ 是 |
| 新增 SSE 服务流 | 新建 handler → `services/router.py` 注册到 `ALLOWED_SERVICES` | ✅ 是 |
| 复用平台规范 | 只读调用 `PlatformRegistry.load()` | ✅ 是 |
| 复用方法论 | 只读调用 `MethodologyRegistry.find_best_match()` | ✅ 是 |
| 修改 `ServiceStreamRequest` | **禁止**。业务变体走 `context` | ❌ 否 |
| 修改 `skills/skill-bulk-creative/` | **禁止**。直接在 handler 中编排 LLM | ❌ 否 |
| 修改 `orchestra/core.py` | **禁止**。本次不经过编排层 | ❌ 否 |
| 修改 `PlatformRegistry` 内部逻辑 | **禁止**。只读调用 | ❌ 否 |
| 修改 `llm_hub` 初始化 | **禁止**。只调用 `get_client()` | ❌ 否 |

### 11.2 相关代码索引

| 文件 | 说明 | 使用方式 |
|------|------|---------|
| `apps/api/src/api/main.py` | API 统一入口 | 新增一行 `include_router` |
| `apps/api/src/services/router.py` | 统一服务流路由 | 注册 `"cross-platform-content"` |
| `apps/api/src/services/models.py` | `ServiceStreamRequest` 模型 | 通过 `context` 扩展，不改字段 |
| `apps/api/src/services/memory_service.py` | 会话记忆隔离 | 调用现有 `append/list_messages/clear` |
| `packages/llm-hub/src/llm_hub/` | LLM 统一调度 | 调用 `get_client()` + `complete()` / `stream_completion()` |
| `packages/knowledge-base/src/knowledge_base/platform_registry.py` | 平台规范库 | 只读调用 `load()` |
| `packages/knowledge-base/src/knowledge_base/methodology_registry.py` | 方法论库 | 只读调用 `find_best_match()` / `load()` |
| `packages/lumina-skills/src/lumina_skills/tool_skills.py` | 工具技能集合 | 调用 `fetch_trending_topics()` |
| `packages/lumina-skills/src/lumina_skills/registry.py` | MCP Tool 注册中心 | 只读调用 `TOOL_REGISTRY`，不改注册逻辑 |
| `apps/rpa/src/rpa/skill_utils.py` | RPA Skill 辅助类 | 只读调用 `RPASkillHelper.fetch_platform_data()`，不改内部逻辑 |
| `data/credentials/xiaohongshu_cookies.txt` | 小红书登录 Cookie | 只读，定期手动更新 |
| `data/platforms/*.yml` | 平台规范数据 | 只读，不修改结构 |
| `data/methodologies/*.yml` | 方法论数据 | 只读，不修改结构 |
| `skills/skill-bulk-creative/main.py` | 现有生成与适配工具 | **本次不使用、不修改** |
| `apps/orchestra/src/orchestra/core.py` | 编排层 | **本次不经过** |

### 11.3 术语表

| 术语 | 说明 |
|------|------|
| SSE | Server-Sent Events，服务端推送事件流 |
| MCP | Model Context Protocol，模型上下文协议 |
| Service Handler | `services/handlers/` 下的服务处理模块 |
| content_dna | 平台内容基因，描述平台调性、用户偏好、算法倾向 |
| audit_rules | 平台审核规则，定义违禁词、敏感类别、限流红线 |
| content_formats | 按内容形式（图文/视频/仅文字）细分的格式约束 |
| User Profile Context | 用户画像上下文，跨模块共享的参数集 |
| Seed Topic | 选题种子，来自榜单的选题数据，作为内容生成的输入 |
| RPA | Robotic Process Automation，机器人流程自动化（此处指 Playwright 无头浏览器抓取） |
| fetch_trending_topics | MCP 工具，通过 RPA 抓取各平台真实热门话题 |
| Cookie 登录 | 通过保存的 Cookie 字符串实现免密登录，用于小红书等平台 |
| 降级策略 | 当 RPA 抓取失败时，自动回退到纯 LLM 生成的兜底方案 |
