# Lumina 后端改造变更记录

> 基于 `docs/20260716_renovation_plan.md` 实施，覆盖阶段一至六的核心后端改造项。
>
> **生成时间**：2026-07-20
> **范围**：仅后端服务（apps/api/src/），不涉及前端/LLM 配置（persona 文件）

---

## 一、新增文件

### 1. `apps/api/src/services/conversation_profile_service.py` (12KB)

**新增，对应改造计划 P0-7/P0-9/P0-12**

| 变更项 | 说明 |
|---|---|
| `conversation_profiles` 表 DDL | `CREATE TABLE IF NOT EXISTS`，含 user_id, conversation_id, platform, platform_cn, niche, target_audience, content_style, goals(JSONB), timestamps |
| `ConversationProfile` 值对象 | 画像数据模型，含 `to_dict()` 序列化和 `format_for_prompt()` 格式化方法 |
| `ConversationProfileService` 服务 | 核心读写服务：`get_profile()`, `upsert_profile()`, `detect_platform_change()`, `update_profile_from_tool_args()`, `extract_and_update_from_message()` |
| 平台中文映射 | `PLATFORM_CN_MAP` 统一管理 7 个平台的中文名 |
| 平台变更检测 | 当用户消息中声明新平台时，检测并记录 `platform_changed_at` |
| Goals 合并策略 | 新 goals 追加而非覆盖，JSONB 去重保留顺序 |

---

## 二、修改文件

### 2. `apps/api/src/services/handlers/system_chat.py` (重写)

**关键修改，对应 P0-2/P0-3/P0-9/P0-12/P2-3/P1-8**

| 行号 | 变更 | 对应阶段 |
|---|---|---|
| 1-32 | 文件头 docstring 更新，新增 intent_completion 等 import | P1-8 |
| 68-114 | **画像集成**：读取 `conversation_profiles`、平台提取与更新、平台变更检测、平台解析优先级（画像 > explicit > current_message > history > inferred） | P0-9/P0-12 |
| 116-131 | **意图补全**：调用 `complete_intent()` 预处理短消息，补全后替代原始 message | P1-8 |
| 145-153 | 传递 `conversation_profile`、`session_round`、`intent_completed` 给 adapter | P2-3 |

**平台解析优先级逻辑**：
```
if 画像有平台 and 未检测到用户切换 → 平台 = 画像平台，source = "profile"
else → 走 resolve_platform_for_request() 原逻辑（explicit > current_message > history > inferred）
```

### 3. `apps/api/src/services/hermes_adapter.py` (关键修改)

**对应 P0-10/P1-1/P1-6/P1-7/P2-3**

| 行号 | 变更 | 对应阶段 |
|---|---|---|
| 444-460 | `chat_stream()` 签名新增 `conversation_profile`、`session_round`、`intent_completed` 参数 | P2-3 |
| 480-506 | **日志记录增强**：新增 `platform_source`、`session_round`、`context_hit`、`tool_platform_aligned`、`intent_completion` 字段 | P2-3 |
| 532-548 | **画像回写 (profile_block)**：在 system prompt 中插入 `format_for_prompt()` 生成的画像摘要，位置在 persona + platform_block 之后 | P1-6 |
| 622-631 | 将 `profile_block` 拼入 `effective_system`，与 persona / platform_block / 对话连续性提示构成完整 prompt | P1-6 |
| 636 | 调用 `set_request_context()` 时传入 `platform` 和 `user_message` 参数 | P0-10 |
| 551 | keyword 路径下也设置请求上下文 (`set_request_context(user_id, conversation_id, platform, user_message)`) | P0-10 |
| 807-815 | **`tool_platform_aligned` 验证**：在 `finally` 块中遍历 `rec["tools"]` 的所有 platform 参数，统计不同平台数量，`len(platforms) <= 1` 为一致 | P1-1 |

### 4. `apps/api/src/services/platform_utils.py` (小修改)

**对应 P0-12**

| 行号 | 变更 |
|---|---|
| 147-161 | 新增 `detect_platform_change_in_message()` 函数：检测用户消息中的平台是否与当前画像平台不同，返回 `(is_changed, new_platform)` |

### 5. `apps/api/src/services/hermes_tools.py` (关键修改)

**对应 P0-10/P1-1**

| 行号 | 变更 | 对应阶段 |
|---|---|---|
| 40-44 | `set_request_context()` 签名新增 `platform` 和 `user_message` 参数，存入线程局部变量 | P0-10 |
| 56-59 | 新增 `_current_platform()` 函数：获取当前请求已解析的平台 | P0-10 |
| 381-403 | **`handle_tool_call()` 平台一致性校验**：在所有工具调用前，检查 args 中的 platform 是否与已解析平台一致，不一致时自动替换（除非检测到多平台对比意图） | P1-1 |

---

## 三、新增模块

### 6. `apps/api/src/services/intent_completion.py` (5KB)

**新增，对应 P1-8/P1-9**

| 函数 | 说明 |
|---|---|
| `is_likely_referencing(message)` | 检测消息是否可能包含指代/省略表达（<3字、含指代词、纯疑问短词） |
| `get_last_topic_from_history(history)` | 从对话历史中提取最近一轮 assistant 回复前 100 字作为话题摘要 |
| `get_last_user_message(history)` | 获取最近一条用户消息 |
| `complete_intent(message, history)` | **核心补全逻辑**：模式匹配 4 种省略模式（图文跨格式/视频跨格式/接上一问题/追问更多）+ 短文本兜底 |
| `needs_confirmation(message, completion)` | 置信度判断：短消息 + 兜底补全时需确认 |

**补全示例**：
- 用户：「那么图文的又咋做」→ 「基于上一轮话题「...」，用户希望基于上一轮主题生成对应的图文内容。」
- 用户：「接上一个问题」→ 「基于上一轮话题「...」，用户希望继续上一个话题。」
- 用户：「然后呢」→ 「基于上一轮话题「...」，用户在追问上一轮主题的更多信息。」

集成方式：在 `system_chat.py` 的 `handle_system_chat_stream()` 中，查询历史后、构建 adapter 前，对 `is_likely_referencing()` 为 True 的消息调用 `complete_intent()`。补全后的内容替代原始 message，LLM 收到的就是补全后的完整意图。

---

## 四、数据模型变更汇总

### 新增表：`conversation_profiles`

```sql
CREATE TABLE IF NOT EXISTS conversation_profiles (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,
    platform VARCHAR(64),            -- 统一标识：shipinhao/xiaohongshu/douyin/...
    platform_cn VARCHAR(64),         -- 中文名：视频号/小红书/抖音/...
    niche VARCHAR(256),              -- 赛道：健康养生/美妆/职场/...
    target_audience VARCHAR(512),    -- 目标人群
    content_style VARCHAR(512),      -- 内容风格：干货型/跟练型/...
    goals JSONB DEFAULT '[]'::jsonb, -- 目标数组：["涨粉","打造IP"]
    niche_extracted_at TIMESTAMPTZ,  -- 赛道最后提取时间
    platform_changed_at TIMESTAMPTZ, -- 平台最后变更时间
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_conv_profile UNIQUE (user_id, conversation_id)
);
```

### 已有表：无变更

- `chat_messages` — 已有的对话历史表（保持不变）

---

## 五、日志字段增强

### 对话日志新增字段（`conversation_log.py` JSONL 输出）

| 字段 | 类型 | 含义 | 写入位置 |
|---|---|---|---|
| `session_round` | int | 当前会话第几轮（user+assistant=1 轮） | adapter rec 构造处 |
| `platform_source` | str | 平台来源：profile/explicit/current_message/history/inferred/none | adapter rec 构造处 |
| `context_hit` | bool | 是否命中上下文（历史拼接是否生效） | adapter rec 构造处 |
| `tool_platform_aligned` | bool | 同一次请求内工具 platform 是否一致 | adapter finally 验证后 |
| `intent_completion` | bool | 是否经过意图补全 | adapter rec 构造处 |

---

## 六、改造覆盖矩阵

### 改造计划 → 实现对照

| 改造项 | 状态 | 备注 |
|---|---|---|
| **阶段一：会话记忆基建** | | |
| P0-1: 建立会话消息存储表 | ✅ 已有 | `chat_messages` 表 |
| P0-2: 根据 conversation_id 查询历史 | ✅ 已有 | `handle_system_chat_stream` |
| P0-3: 历史消息拼入 LLM prompt | ✅ 已有 | `conversation_history` 传入 Hermes |
| P0-5: 会话新建/恢复策略（后端部分） | ✅ 已有 | 收敛到 system-chat 单一入口 |
| **阶段二：平台与用户画像持久化** | | |
| P0-7: 会话级画像表 | ✅ **本次** | `conversation_profiles` 表 + `ConversationProfileService` |
| P0-8: 平台识别与提取 | ✅ 已有 | `extract_platform_from_text` |
| P0-9: 画像更新策略 | ✅ **本次** | 从用户消息/工具调用参数中提取并更新 |
| P0-10: 工具平台参数读取顺序 | ✅ **本次** | `handle_tool_call` 中自动统一平台 |
| P0-11: platform 字段回填日志 | ✅ **本次** | `platform_source` 字段记录来源 |
| P0-12: 平台变更检测 | ✅ **本次** | `detect_platform_change_in_message` + `platform_changed_at` |
| **阶段三：工具层平台一致性** | | |
| P1-1: 平台归一校验 | ✅ **本次** | `handle_tool_call` 中自动对齐 + `tool_platform_aligned` 日志验证 |
| P1-2: 多平台对比识别 | ✅ 已有 | `detect_multi_platform_intent` |
| **阶段四：长对话稳定性** | | |
| P1-6: 画像回写到 system prompt | ✅ **本次** | `profile_block` 拼入 hermes system prompt |
| **阶段五：指代消解与意图补全** | | |
| P1-7: system prompt 指代消解提示 | ✅ 已有 | 「对话连续性提示」已在 prompt 中 |
| P1-8: 意图补全逻辑 | ✅ **本次** | `intent_completion.py` + 集成到 flow |
| P1-9: 置信度判断 | ✅ **本次** | `needs_confirmation()` |
| **阶段六：可观测** | | |
| P2-3: 日志增强字段 | ✅ **本次** | 5 个新增字段 |

### 本批次不覆盖

- 阶段四 P1-3/P1-4/P1-5（会话摘要）：需要 LLM 摘要生成，后续单独实现
- 阶段五 P1-8 的 LLM 辅助补全增强（当前为规则匹配）
- 阶段六 P2-1/P2-2（人设固化）：属于 persona 文件配置
- 阶段六 P2-4（监控看板）：基础设施层
- 阶段六 P2-5（回归测试集）：测试工作
- 前端改造（P0-4）：前端负责

---

## 七、验收检查

### 关键回归用例验证

| 用例 | 场景 | 对应修改 |
|---|---|---|
| R1 | 连续多轮 conversation_id 一致 history_len 递增 | ✅ 已有（chat_messages + session_history） |
| R4 | 声明视频号后省略平台词，工具平台为视频号 | ✅ P0-9/P0-10（画像持久化 + 工具平台对齐） |
| R5 | 「怎么打造养生账号 ip」→ 视频号非小红书 | ✅ P0-9（画像持久化） |
| R6 | 同次请求内工具平台一致（不混用） | ✅ P1-1（handle_tool_call 对齐） |
| R12/R13 | 指代消解「那么图文的又咋做」「接上一个问题」 | ✅ P1-8（intent_completion.py） |

---

## 八、回滚方案

如需回滚单次变更：

1. **conversation_profile_service.py** → 删除文件，删除 `conversation_profiles` 表（或忽略）
2. **system_chat.py** → 还原为原始版本（git checkout）
3. **hermes_adapter.py** → 还原 chat_stream 签名和 system prompt 构造
4. **hermes_tools.py** → 还原 set_request_context 和 handle_tool_call
5. **platform_utils.py** → 删除 detect_platform_change_in_message
6. **intent_completion.py** → 删除文件
