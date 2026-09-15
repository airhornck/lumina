# Phase 0 渐进式内容生成 SPECIFICATION

> 文档版本：v1.0
> 日期：2026-07-04
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` 5.2 P0-2 渐进式内容生成
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

当前 Lumina 在识别到内容生成意图（`content`、`content_single`、`content_pipeline`）后，直接调用 `CrossPlatformEngine.generate_sync()`，无论用户信息是否充足。本 SPEC 定义在内容生成前进行信息完整性检查，缺失关键信息时优先询问，而非强制生成低质量内容。

### 1.2 用户故事

> 作为用户，我希望 AI 在生成内容前先了解我的需求，而不是直接生成不相关的内容。

### 1.3 验收标准（来自业务真源）

- [ ] 用户说"帮我写文案"时，AI 先询问主题、风格、目标人群
- [ ] 用户说"改得软一点"时，AI 基于之前的内容修改，不是重新生成
- [ ] 用户说"再写一个"时，AI 保持相同主题和风格，换角度
- [ ] 信息不足时，AI 每次只问最关键的一个信息（不是一次性问所有）

---

## 二、输入输出边界

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_input` | str | 是 | 用户当前消息 |
| `kind` | str | 是 | 意图类型：`content` / `content_single` / `content_pipeline` |
| `platform` | str | 是 | 当前平台，如 `xiaohongshu` / `douyin` |
| `session_history` | List[Dict] | 是 | 当前对话历史 |
| `context` | Dict[str, Any] | 是 | 包含 `user_id`、`conversation_id`、可选字段等 |

### 2.2 输出

#### 情况 A：信息完整 → 正常生成

返回原有 `run_dynamic` 的生成结果，结构不变。

#### 情况 B：信息缺失 → 返回 clarification

```python
{
    "layer": "orchestra",
    "mode": "dynamic",
    "intent": {"kind": "content", "sop_id": None},
    "hub": {
        "ok": True,
        "result": {
            "type": "clarification",
            "reason": "missing_required_fields",
            "missing": ["topic"],  # 只返回最关键的一个字段
            "collected": {
                "platform": "xiaohongshu",
                "style": "soft"
            },
            "reply": "为了写出更贴合你的文案，想先确认一下：**这次的主题或产品是什么？**"
        }
    },
    "reply": "为了写出更贴合你的文案，想先确认一下：**这次的主题或产品是什么？**"
}
```

### 2.3 边界条件

| 场景 | 预期行为 |
|------|----------|
| 用户只输入"帮我写文案" | 询问主题 |
| 用户说"写个小红书文案" | 已推断 platform，询问主题 |
| 用户说"写个夏季防晒文案" | 已推断 topic，询问风格/目标人群 |
| 用户说"改得软一点" | 不归为 content 意图，走 conversation/clarification 或修稿流程 |
| 用户连续拒绝提供信息 | 最多追问 2 轮，第 3 轮基于已有信息生成 |
| 历史对话中已有关键信息 | 不重复询问 |
| 用户明确说"随便" | 使用默认配置生成，不再追问 |

---

## 三、核心业务规则

### 3.1 受控意图

渐进式生成仅对以下意图生效：

- `content`
- `content_single`
- `content_pipeline`

其他意图（如 `diagnosis`、`traffic`）已有 clarification 逻辑，不受影响。

### 3.2 关键字段定义

按优先级排序，每次只询问最靠前的缺失字段：

| 优先级 | 字段 | 说明 | 推断方式 |
|--------|------|------|----------|
| 1 | `topic` | 主题/产品 | 用户输入中提取名词短语 |
| 2 | `platform` | 目标平台 | 从关键词推断（小红书/抖音/B站等） |
| 3 | `style` | 风格 | 软植入/干货测评/种草清单/故事型 |
| 4 | `target_audience` | 目标人群 | 学生党/上班族/宝妈/新手等 |
| 5 | `content_goal` | 内容目标 | 涨粉/带货/互动/立人设 |

### 3.3 信息推断规则

从 `user_input` 和 `session_history` 中推断已收集字段：

| 字段 | 推断规则 |
|------|----------|
| `topic` | 提取用户输入中的产品/主题名词；若历史消息中用户明确回答过主题，则复用 |
| `platform` | 关键词匹配：小红书→xiaohongshu，抖音→douyin，B站→bilibili，视频号→shipinhao |
| `style` | 关键词匹配：软植入/软一点→soft，干货/测评→review，种草→recommend，故事→story |
| `target_audience` | 关键词匹配：学生党/大学生→student，上班族/白领→office_worker，宝妈→mom |
| `content_goal` | 关键词匹配：涨粉/爆款→growth，带货/转化→conversion，互动→engagement |

### 3.4 追问策略

- 每次只问**一个**最关键缺失字段
- 追问文本由模板生成，必要时可用轻量级 LLM 润色
- 同一轮对话中最多追问 **2 次**
- 第 3 次仍缺失时，使用默认值生成并提示用户

### 3.5 默认配置

当用户拒绝补充或追问达到上限时：

```python
DEFAULT_CONTENT_CONFIG = {
    "platform": "xiaohongshu",
    "style": "soft",
    "target_audience": "general",
    "content_goal": "engagement",
}
```

---

## 四、错误处理

| 错误场景 | 处理策略 |
|----------|----------|
| 推断模块异常 | 降级为直接生成，记录 error |
| LLM 润色失败 | 使用模板化追问文本 |
| 历史记录为空 | 按全部字段缺失处理 |
| 字段推断冲突 | 以最新用户输入为准 |

---

## 五、安全合规

| 要求 | 实现 |
|------|------|
| 不伪造信息 | clarification 只询问真实信息，不编造 |
| 不泄露隐私 | 追问文本不暴露其他用户数据 |
| 可控回退 | Feature Flag 关闭时直接走原生成逻辑 |

---

## 六、接口兼容性声明

- 不修改 `/api/v1/debug/chat/stream` 接口路径
- 不修改 SSE 事件类型
- `clarification` 类型已在现有 `diagnosis`/`traffic` 中使用，字段结构保持一致
- 新增 `reason`: `missing_required_fields`
- 新增环境变量 `LUMINA_ENABLE_PROGRESSIVE_GENERATION`

---

## 七、Feature Flag

```bash
LUMINA_ENABLE_PROGRESSIVE_GENERATION=true   # 启用渐进式生成
LUMINA_ENABLE_PROGRESSIVE_GENERATION=false  # 回滚到直接生成
```

---

## 八、测试用例（TDD Harness）

### 8.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_missing_topic | "帮我写文案" | 返回 clarification，missing=["topic"] |
| test_infer_platform | "写个小红书文案" | collected.platform=xiaohongshu，missing=["topic"] |
| test_infer_topic | "写个夏季防晒文案" | collected.topic=夏季防晒，missing=["style"] |
| test_historical_info_reuse | 历史已提供 topic 和 style，再问"帮我写文案" | 直接生成 |
| test_max_clarification_2_rounds | 连续 2 轮不回答 | 第 3 轮使用默认值生成 |
| test_disable_flag | Flag=false，输入"帮我写文案" | 直接生成 |
| test_content_pipeline_clarification | "帮我写一稿多改" | 询问主题 |

### 8.2 集成测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_chat_stream_asks_topic | POST /chat/stream "帮我写文案" | SSE 返回 clarification 类型回复 |
| test_chat_stream_generates_after_info | 先回答主题，再问生成 | SSE 返回正常内容生成 |
| test_chat_stream_no_format_change | 任何 clarification | SSE 事件类型不变 |

### 8.3 接口回归测试

| 用例 | 预期 |
|------|------|
| test_debug_chat_stream_sse_format | SSE 事件类型和字段不变 |
| test_existing_content_still_works | Flag 关闭时原有内容生成路径不变 |

---

## 九、实现文件

| 文件 | 说明 |
|------|------|
| `apps/orchestra/src/orchestra/core.py` | 在 `run_dynamic` 的 content 分支前插入完整性检查 |
| 新增 `apps/orchestra/src/orchestra/required_fields.py` | 字段定义、推断规则、默认值 |
| 新增 `apps/orchestra/src/orchestra/intent_guards.py` | 完整性检查入口、追问生成 |
| `apps/orchestra/src/orchestra/nlg.py` | 可能需要新增 clarification 文本生成 |
| 新增 `tests/orchestra/test_progressive_generation.py` | 单元测试 |
| 新增 `tests/integration/test_progressive_generation.py` | 集成测试 |

---

## 十、风险与回滚

| 风险 | 缓解 |
|------|------|
| 追问过多导致用户体验下降 | 限制最多 2 轮追问 |
| 推断规则覆盖不全 | 持续迭代关键词库 |
| LLM 润色增加延迟 | 使用模板兜底 |
| 破坏现有生成流程 | Feature Flag 可秒级回滚 |

**回滚**：设置 `LUMINA_ENABLE_PROGRESSIVE_GENERATION=false` 即可。
