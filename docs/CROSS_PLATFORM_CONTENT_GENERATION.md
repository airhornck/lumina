# 跨平台内容生成与适配需求文档

> **状态**: 待评审  
> **版本**: v1.0  
> **日期**: 2026-04-21  
> **范围**: 生成一篇文章并适配为多个平台版本，前端通过统一接口接收结构化内容  
> **不包含**: 自动发布（RPA 执行）

---

## 1. 需求概述

### 1.1 用户场景

运营人员创作一篇核心内容（文章/脚本/笔记），需要系统自动生成适合多个社交媒体平台的差异化版本，前端以结构化数据形式接收各平台版本的内容、格式建议与合规提示，供人工审核后手动发布。

**典型用户输入**
> "生成一篇关于职场穿搭的干货文章，帮我改成适合小红书、抖音、B站发布的版本"

**期望输出**
- 小红书版：标题（20字以内）、正文（300-800字）、话题标签（≤10个）、图片建议
- 抖音版：黄金3秒钩子、口播脚本（30-60秒）、字幕要点、热门标签
- B站版：视频标题、分镜脚本、弹幕引导语、分区标签

### 1.2 目标

1. 用户通过自然语言描述需求，系统自动识别目标平台并完成内容生成与适配
2. 前端通过统一 SSE 流式接口接收按平台分组的结构化内容
3. 各平台版本符合平台规范库（`data/platforms/*.yml`）的格式约束与内容 DNA

---

## 2. 现状分析

### 2.1 已有能力

| 模块 | 已有能力 | 位置 |
|------|---------|------|
| **意图识别** | 已支持识别"一稿多改/改写多平台/适配平台"意图，归类为 `bulk_creation` / `content_variation` | `apps/intent/` + `config/intent_rules.yaml` |
| **编排路由** | `MarketingOrchestra._resolve_matrix_intent()` 已能识别多平台意图并调用 `skill-bulk-creative` | `apps/orchestra/src/orchestra/core.py:502-534` |
| **内容变体** | `skill-bulk-creative.generate_variations()` 支持按账号定位生成细分领域/场景化/地域化变体 | `skills/skill-bulk-creative/src/skill_bulk_creative/main.py:67-118` |
| **平台适配** | `skill-bulk-creative.adapt_platform()` 能读取 `PlatformRegistry` 规范库，获取长度限制、标签上限、审核规则 | `skills/skill-bulk-creative/src/skill_bulk_creative/main.py:193-242` |
| **平台规范库** | 已定义小红书/抖音/B站的内容 DNA、审核规则、content_formats（图文/视频/仅文字） | `data/platforms/*.yml` |
| **服务流接口** | 已有统一 SSE 服务流框架：`POST /api/v1/services/{service}/stream`，支持记忆管理 | `apps/api/src/services/router.py` |

### 2.2 关键缺失

| 缺失项 | 影响 | 严重程度 |
|--------|------|---------|
| `adapt_platform` 仅做文本截断，无 LLM 语义级改写 | 各平台版本只是"截短版"，没有平台风格差异（如小红书种草感 vs 抖音口语化） | 🔴 高 |
| `skills/` 下独立 MCP Server 未被主 API 真实调用 | `skill_router.py` 为 Mock，API 层无法通过标准 MCP Client 调用 `skill-bulk-creative` | 🟡 中 |
| 无面向前端的标准服务流接口 | 前端无法通过 `/{service}/stream` 模式消费多平台生成结果 | 🔴 高 |
| `generate_variations` 与 `adapt_platform` 未串联 | 一稿多改和平台适配是两个独立工具，缺少"先生成变体 → 再按平台适配"的完整编排 | 🔴 高 |
| 输出结构不统一 | 当前输出字段不一致，前端难以标准化渲染 | 🟡 中 |

---

## 3. 需求范围

### 3.1 In Scope

- 接收用户自然语言输入，解析目标平台列表
- 基于单篇核心内容，生成多平台差异化版本
- 按平台规范库约束长度、标签数、格式
- LLM 驱动的语义级平台风格改写（非简单截断）
- 统一 SSE 流式接口输出结构化结果
- 平台-specific 建议（最佳发布时间、内容形式、风险提醒）

### 3.2 Out of Scope

- 自动发布到各平台（RPA 执行，需 `skill-rpa-executor` 后续串联）
- 图片/视频的实际生成（仅输出内容文案与素材建议）
- 实时热点自动注入（如需热点，先由 `skill-content-strategist` 提供）
- 用户级账号矩阵管理（如多账号选择，后续由 `skill-matrix-commander` 支持）

---

## 4. 架构方案

### 4.1 方案决策

| 方案 | 说明 | 评估 |
|------|------|------|
| A. 新建 Skill | 在 `skills/` 下新建 `skill-content-distributor` | ❌ 拒绝。与 `skill-bulk-creative` 高度重复，且独立 Skill 仍未被主 API 打通 |
| B. 补全 Skill Router MCP | 把 `skill_router.py` 从 Mock 改为真实 MCP Client 调用 | ⚠️ 不充分。`skill_router.py` 设计为单 Skill 单方法调用，不适合"生成+适配"多步骤编排 |
| **C. 新增 Service Handler（推荐）** | 在 `services/router.py` 下新增 `cross-platform-content` service，内部编排 `skill-bulk-creative` 工具 | ✅ **采纳**。复用现有统一流式接口，改动最小，编排灵活 |

### 4.2 系统交互图

```
┌─────────────┐      POST /api/v1/services/cross-platform-content/stream
│   前端      │ ──────────────────────────────────────────────────────────►
│  (Web/App)  │                                                            │
└─────────────┘                                                            │
       ▲                                                                   │
       │ SSE stream                                                        │
       │                                                                   ▼
       │                          ┌─────────────────────────────┐
       │                          │  services/router.py         │
       │                          │  (ALLOWED_SERVICES 新增项)   │
       │                          └─────────────┬───────────────┘
       │                                        │
       │                          ┌─────────────▼───────────────┐
       │                          │ cross_platform_content.py   │
       │                          │ (新增 Service Handler)       │
       │                          │                             │
       │                          │  1. 解析目标平台列表          │
       │                          │  2. 调用 generate_variations │
       │                          │  3. 调用 adapt_platform      │
       │                          │  4. 流式组装 SSE 响应         │
       │                          └─────────────┬───────────────┘
       │                                        │
       │              ┌─────────────────────────┼─────────────────────────┐
       │              │                         │                         │
       │              ▼                         ▼                         ▼
       │    ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
       │    │ skill-bulk-     │      │ llm_hub         │      │ PlatformRegistry│
       │    │ creative        │      │ (语义级改写)     │      │ (规范约束)       │
       │    │                 │      │                 │      │                 │
       │    │ · generate_     │      │ · 平台风格注入   │      │ · content_dna   │
       │    │   variations    │      │ · 审核规则过滤   │      │ · audit_rules   │
       │    │ · adapt_platform│      │ · 方法论引导    │      │ · content_      │
       │    │                 │      │                 │      │   formats       │
       │    └─────────────────┘      └─────────────────┘      └─────────────────┘
       │
       │  data: {"type": "platform_chunk", "platform": "xiaohongshu", ...}
       │  data: {"type": "platform_chunk", "platform": "douyin", ...}
       │  data: {"type": "done"}
```

### 4.3 与现有模块的关系

- **复用 `skill-bulk-creative`**：不新建 Skill，增强现有 `adapt_platform` 加入 LLM 驱动改写
- **复用 `services/router.py` 框架**：统一入口、统一 SSE 协议、统一记忆管理
- **复用 `PlatformRegistry`**：动态读取 `data/platforms/*.yml`，约束输出格式
- **复用 `MethodologyRegistry`**：注入内容方法论（AIDA/钩子故事等）提升生成质量
- **复用 `llm_hub`**：统一 LLM 调用与流式输出

---

## 5. 接口设计

### 5.1 前端调用接口

```http
POST /api/v1/services/cross-platform-content/stream
Content-Type: application/json
```

**请求体**（复用 `ServiceStreamRequest`，通过 `context` 扩展）

```json
{
  "user_id": "u123",
  "conversation_id": "c456",
  "message": "生成一篇职场穿搭干货，适配小红书、抖音、B站",
  "platform": null,
  "context": {
    "target_platforms": ["xiaohongshu", "douyin", "bilibili"],
    "content_type": "图文",
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

**字段说明**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户唯一标识 |
| `conversation_id` | string | 是 | 对话唯一标识 |
| `message` | string | 是 | 用户自然语言输入 |
| `platform` | string | 否 | 默认平台上下文 |
| `context.target_platforms` | string[] | 否 | 目标平台列表，未提供则从 `message` 中解析 |
| `context.content_type` | string | 否 | 内容形式：图文/视频/仅文字，默认"图文" |
| `context.master_content` | object | 否 | 若用户已提供核心内容，直接适配；否则由 LLM 生成 |
| `context.optimization_goal` | string | 否 | 优化目标：engagement / conversion / reach |
| `context.niche` | string | 否 | 垂直领域，用于变体生成 |

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

### 5.2 内部调用链路

```python
# cross_platform_content.py 内部伪代码

async def handle_cross_platform_content_stream(...):
    # 1. 提取参数
    target_platforms = context.get("target_platforms") or _extract_from_message(message)
    master = context.get("master_content")
    
    # 2. 若用户未提供核心内容，先由 LLM 生成
    if not master:
        master = await _generate_master_content(message, llm_client)
    
    # 3. 一稿多改（按账号定位生成变体）
    variations = await generate_variations(
        BulkVariationInput(master_content=master, target_accounts=...)
    )
    
    # 4. 逐平台适配（LLM 语义级改写 + 规范约束）
    for platform in target_platforms:
        adapted = await adapt_platform(
            content=variations[0],
            source_platform="generic",
            target_platforms=[platform],
            user_id=user_id
        )
        # 增强：调用 LLM 做语义改写（而非仅截断）
        refined = await _llm_refine_for_platform(adapted, platform, spec)
        yield _sse({"type": "platform_chunk", "platform": platform, "content": refined})
    
    yield _sse({"type": "done"})
```

---

## 6. 数据模型

### 6.1 输出结构（按平台）

```typescript
interface CrossPlatformContentResponse {
  type: "platform_chunk";
  platform: string;           // xiaohongshu | douyin | bilibili | ...
  content: PlatformContent;
}

interface PlatformContent {
  // 通用字段
  title: string;              // 平台适配后的标题
  body: string;               // 正文/脚本内容
  hashtags: string[];         // 话题标签（已按平台上限裁剪）
  
  // 平台-specific 字段（根据 platform 动态填充）
  format?: string;            // 内容形式：图文 / 视频 / 仅文字
  hook?: string;              // 抖音：黄金3秒钩子
  script_segments?: string[]; // 抖音/B站：分段脚本
  duration_tip?: string;      // 视频时长建议
  pic_count_tip?: string;     // 小红书：图片数量建议
  pic_ratio?: string;         // 小红书：图片比例建议
  danmu_prompt?: string;      // B站：弹幕引导语
  
  // 策略建议
  best_time?: string;         // 最佳发布时间
  methodology?: string;       // 使用的内容方法论（AIDA / hook-story-offer 等）
  compliance_warnings?: string[]; // 合规风险提示
  style_guide?: string;       // 平台风格指引摘要
}
```

### 6.2 平台规范库调用约定

`cross_platform_content.py` 通过 `PlatformRegistry().load(platform)` 读取以下字段注入 Prompt：

| 规范字段 | 用途 |
|---------|------|
| `content_dna` | 注入 LLM Prompt：平台内容基因（如"小红书：种草感、emoji、个人体验"） |
| `audit_rules` | 注入 LLM Prompt：审核禁区；输出前做敏感词过滤 |
| `content_formats.{format}.title.max_chars` | 约束标题长度 |
| `content_formats.{format}.content.max_chars` | 约束正文长度 |
| `content_formats.{format}.tags.max_count` | 约束标签数量 |

---

## 7. 实施计划

### 7.1 Phase 1：基础链路打通（预计 1-2 天）

- [ ] **增强 `skill-bulk-creative.adapt_platform`**
  - 在截断基础上，增加 LLM 语义改写调用
  - Prompt 模板注入 `content_dna` + `audit_rules` + `content_formats`
  - 输出改为结构化 JSON（title/body/hashtags/format_tips）

- [ ] **新增 `apps/api/src/services/handlers/cross_platform_content.py`**
  - 实现 `handle_cross_platform_content_stream()`
  - 内部编排：解析平台 → 生成/获取核心内容 → 调用 `adapt_platform` → 流式输出
  - 异常处理：单平台失败不影响其他平台

- [ ] **注册到统一路由**
  - `services/router.py`：`ALLOWED_SERVICES` 加入 `"cross-platform-content"`
  - `services/router.py`：`service_stream()` 中新增分支

### 7.2 Phase 2：质量与体验优化（预计 2-3 天）

- [ ] **接入方法论引导**
  - 调用 `MethodologyRegistry` 匹配最佳内容方法论
  - 在 LLM Prompt 中注入方法论框架（如 AIDA、钩子-故事-行动）

- [ ] **合规风险前置检测**
  - 生成后调用 `skill-compliance-officer` 做敏感词/审核规则检测
  - 在 SSE 中通过 `warning` 事件推送风险提示

- [ ] **记忆上下文**
  - 接入 `ServiceMemoryStore`，支持多轮对话修稿
  - 如用户说"小红书的再软一点"，基于上一轮结果再生成

### 7.3 Phase 3：发布闭环（未来迭代）

- [ ] 串联 `skill-rpa-executor`
  - 用户确认内容后，一键批量发布到多平台
  - 需增加发布状态回调与错误重试机制

---

## 8. 风险与假设

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| LLM 改写质量不稳定 | 各平台版本风格同质化 | Prompt 中强化平台 DNA 示例；增加 few-shot 示例 |
| 平台规范库 YAML 更新滞后 | 新规则未适配 | 规范库版本化管理；定期同步各平台官方文档 |
| 生成内容过长导致流式延迟 | 用户体验差 | 单平台内容分段增量推送（`delta` 事件） |
| `skills/` MCP 未被主 API 打通 | 未来 Skill 扩展受限 | Phase 1 先走直接 import（与 `orchestra/core.py` 同方式），Phase 2 补 MCP Client |

### 关键假设

1. 用户提供的核心内容（或系统生成的初稿）为中文，目标平台以国内主流平台为主
2. 各平台规范库（`data/platforms/*.yml`）已包含足够约束字段用于 Prompt 注入
3. LLM 输出遵循 JSON Schema，可解析为结构化数据（`response_format={"type": "json_object"}`）
4. 前端具备消费 SSE 流并实时渲染的能力

---

## 9. 附录

### 9.1 相关代码索引

| 文件 | 说明 |
|------|------|
| `skills/skill-bulk-creative/src/skill_bulk_creative/main.py` | 现有生成与适配工具 |
| `apps/orchestra/src/orchestra/core.py:502-534` | 已有矩阵意图解析逻辑 |
| `apps/api/src/services/router.py` | 统一服务流路由 |
| `apps/api/src/services/models.py` | `ServiceStreamRequest` 模型 |
| `data/platforms/*.yml` | 平台规范库 |
| `packages/knowledge-base/src/knowledge_base/platform_registry.py` | 规范库加载器 |

### 9.2 术语表

| 术语 | 说明 |
|------|------|
| SSE | Server-Sent Events，服务端推送事件流 |
| MCP | Model Context Protocol，模型上下文协议（Anthropic 提出，本项目用于 Skill 间通信） |
| Service Handler | `services/handlers/` 下的服务处理模块，处理特定业务流 |
| content_dna | 平台内容基因，描述平台调性、用户偏好、算法倾向 |
| audit_rules | 平台审核规则，定义违禁词、敏感类别、限流红线 |
| content_formats | 按内容形式（图文/视频/仅文字）细分的格式约束 |
