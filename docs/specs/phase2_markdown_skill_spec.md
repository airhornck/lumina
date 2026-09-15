# Phase 2 Hermes Markdown Skill SPECIFICATION

> 文档版本：v1.0
> 日期：2026-07-07
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

将 Lumina 沉淀的营销方法论（定位理论、钩子-故事-Offer、AIDA、PAS 等）封装为 Hermes 可识别、可执行的 Markdown Skill。让 Hermes Agent 在对话中能够按结构化流程调用 Lumina 营销方法，而不是每次都依赖模型自由发挥。

### 1.2 用户故事

> 作为用户，当我让 Lumina 帮我做品牌定位或写转化文案时，Hermes 应该按照 Lumina 验证过的营销方法论分步执行，而不是只给一段通用回答。

---

## 二、输入输出边界

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `skill_name` | str | 是 | Skill 标识，如 `lumina_marketing_methodology` |
| `user_input` | str | 是 | 用户原始请求 |
| `methodology` | str | 否 | 指定方法论，如 `positioning` / `hook_story_offer` / `aida` / `pas` |
| `platform` | str | 否 | 目标平台，默认 `xiaohongshu` |

### 2.2 输出

Hermes 执行 Skill 后返回文本回复，中间可调用 Lumina 工具（如 `lumina_generate_content`）。

### 2.3 边界条件

| 场景 | 预期行为 |
|------|----------|
| 指定方法论不存在 | 返回可用方法论列表，不报错 |
| 用户输入为空 | 提示用户补充信息 |
| Skill 文件缺失 | 优雅降级为普通对话 |

---

## 三、核心业务规则

### 3.1 Skill 文件格式

Hermes Markdown Skill 采用 `SKILL.md` 格式：

```yaml
---
name: lumina_marketing_methodology
description: "Lumina 营销方法论执行器：按结构化流程完成定位、选题、文案等任务。"
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [marketing, lumina, content, strategy]
    related_skills: []
---

# Lumina 营销方法论

## 支持的方法论

- positioning：定位理论（细分→目标→定位→差异化）
- hook_story_offer：钩子-故事-Offer
- aida：注意→兴趣→欲望→行动
- pas：痛点→激化→解决

## Workflow

1. 识别用户需求，选择最匹配的方法论。
2. 按方法论 steps 逐步引导用户补充必要信息。
3. 每完成一步，调用 `lumina_generate_content` 或 `lumina_recommend_topics` 生成中间产物。
4. 最后汇总为可直接使用的文案或策略建议。
```

### 3.2 动态加载与版本管理

- Skill 文件存放于 `data/hermes/skills/lumina-marketing/SKILL.md`。
- Hermes 启动时通过文件系统发现该 Skill（Hermes 会扫描 `HERMES_HOME/skills` 或 PYTHONPATH 下的 skills 目录）。
- 适配器初始化时确保 `lumina_marketing` 工具集已注册，供 Skill 调用。

### 3.3 与 Lumina 工具集成

Skill 执行过程中可调用：

| 工具 | 用途 |
|------|------|
| `lumina_generate_content` | 生成按平台适配的文案 |
| `lumina_recommend_topics` | 推荐选题 |
| `lumina_detect_risk` | 合规检测 |

---

## 四、安全合规

| 要求 | 实现 |
|------|------|
| 不暴露内部方法论 ID | 用户看到的是中文名称 |
| 不调用危险工具 | Skill 仅使用 `lumina_marketing` 工具集 |
| 输入过滤 | 对方法论名称做白名单校验 |

---

## 五、接口兼容性声明

- 不修改现有 `/api/v1/debug/chat/stream` 接口。
- 不修改 SSE 事件格式。
- Skill 对前端完全透明。

---

## 六、测试用例（TDD Harness）

### 6.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_skill_file_exists | - | `data/hermes/skills/lumina-marketing/SKILL.md` 存在且 frontmatter 合法 |
| test_methodology_list | - | 至少包含 positioning、hook_story_offer、aida、pas |
| test_methodology_steps | `positioning` | 返回 4 个步骤 |
| test_skill_handler_schema | - | `lumina_execute_methodology` schema 包含 methodology / user_input |
| test_handler_mock | mock 生成器 | 返回 ok=true 且包含方法论名称 |

---

## 七、实现文件

| 文件 | 说明 |
|------|------|
| 新增 `data/hermes/skills/lumina-marketing/SKILL.md` | Hermes Markdown Skill |
| 新增 `apps/api/src/services/hermes_markdown_skill.py` | Skill 加载器与执行入口 |
| 修改 `apps/api/src/services/hermes_tools.py` | 新增 `lumina_execute_methodology` 工具 |
| 新增 `tests/phase2/test_markdown_skill.py` | 单元测试 |

---

## 八、风险与回滚

| 风险 | 缓解 |
|------|------|
| Skill 文件解析失败 | frontmatter 解析失败时返回降级提示 |
| 方法论步骤与工具不匹配 | 使用 mock handler 兜底 |

**回滚**：设置 `LUMINA_USE_HERMES=false` 即可。
