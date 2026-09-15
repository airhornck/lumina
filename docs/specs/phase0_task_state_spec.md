# Phase 0 任务状态机 SPECIFICATION

> ⚠️ 本 SPEC 实现（task_state.py 任务状态机）已决策退役，多步任务规划由 Hermes planner 的 todo 工具承担，PostgreSQL 表保留但停止读写，详见 docs/specs/phase4_unified_planner_deprecation_spec.md §7。

> 文档版本：v1.0
> 日期：2026-07-04
> 对应业务真源：`docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` 5.2 P0-3 任务自主规划
> 工程纪律：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`

---

## 一、需求导入

### 1.1 业务目标

当前 Lumina 的 `MarketingOrchestra` 每次请求都是无状态的（`marketing_orchestra_process()` 每次都新建实例）。复杂任务（如"帮我运营账号"）被拆分为独立的单次调用，无法在多轮对话中跟踪进度。本 SPEC 定义任务状态机，让系统能在多轮对话中跟踪复杂任务的进度、已收集信息和下一步动作。

### 1.2 用户故事

> 作为用户，我希望 AI 能根据我的目标自动规划行动步骤，而不是我问一步做一步。

### 1.3 验收标准（来自业务真源）

- [ ] 用户说"帮我运营账号"时，AI 提出"诊断→定位→选题→内容"的完整计划
- [ ] 每个步骤完成后，AI 自动引导到下一步（不是结束对话）
- [ ] 用户可以在任何步骤说"跳过"或"先做别的"
- [ ] AI 记住当前进行到哪一步，用户回来继续时不重复

---

## 二、输入输出边界

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | str | 是 | 用户唯一标识 |
| `conversation_id` | str | 是 | 对话唯一标识 |
| `user_input` | str | 是 | 用户当前消息 |
| `intent` | Dict[str, Any] | 是 | 当前意图分类结果 |
| `session_history` | List[Dict] | 是 | 当前对话历史 |

### 2.2 输出

任务状态机输出一个 `TaskState` 对象，并影响 `run_dynamic` 的决策：

```python
{
    "task_id": "task_uuid",
    "task_type": "account_growth",  # 任务类型
    "status": "in_progress",        # pending / in_progress / completed / cancelled
    "current_step": "diagnosis",    # 当前步骤
    "steps": [                      # 完整步骤计划
        {"id": "diagnosis", "label": "账号诊断", "status": "in_progress"},
        {"id": "positioning", "label": "定位优化", "status": "pending"},
        {"id": "topic", "label": "选题推荐", "status": "pending"},
        {"id": "content", "label": "内容生成", "status": "pending"}
    ],
    "collected_info": {             # 已收集的信息
        "platform": "xiaohongshu",
        "account_url": "https://..."
    },
    "next_action": "do_diagnosis",  # 下一步动作
    "created_at": "2026-07-04T14:30:00+00:00",
    "updated_at": "2026-07-04T14:35:00+00:00"
}
```

### 2.3 边界条件

| 场景 | 预期行为 |
|------|----------|
| 用户首次发起复杂任务 | 创建新任务，生成步骤计划，返回第一步引导 |
| 用户中途离开再回来 | 读取任务状态，继续当前步骤 |
| 用户说"跳过" | 标记当前步骤为 skipped，进入下一步 |
| 用户说"先做别的" | 暂停当前任务，按新意图执行；原任务状态保留 |
| 用户说"不做了" | 取消当前任务 |
| 所有步骤完成 | 标记任务 completed，总结并询问是否开启新任务 |
| 任务类型未知 | 不归为任务状态机，按原 intent 处理 |

---

## 三、核心业务规则

### 3.1 任务类型定义

| 任务类型 | 触发意图/关键词 | 默认步骤 |
|----------|----------------|----------|
| `account_growth` | "帮我运营账号"、"怎么涨粉" | diagnosis → positioning → topic → content |
| `content_planning` | "帮我做一周规划"、"内容日历" | topic → content → schedule |
| `traffic_optimization` | "流量下降了"、"怎么提升流量" | data_collection → diagnosis → optimization |
| `brand_positioning` | "定位"、"人设"、"赛道" | positioning → topic → content |

### 3.2 任务生命周期

```
pending → in_progress → completed
              │
              ▼
          cancelled / paused
```

### 3.3 步骤状态

| 状态 | 说明 |
|------|------|
| `pending` | 未开始 |
| `in_progress` | 进行中 |
| `completed` | 已完成 |
| `skipped` | 用户跳过 |
| `failed` | 执行失败 |

### 3.4 任务启动规则

当用户输入触发以下意图且没有正在进行的同类型任务时，启动任务状态机：

- `topic` + 关键词"规划"、"日历"、"一周"
- `conversation` + 关键词"运营账号"、"涨粉"、"流量下降"
- `diagnosis` + 关键词"全面诊断"、"整体分析"

### 3.5 任务状态对意图路由的影响

| 场景 | 行为 |
|------|------|
| 有进行中的任务，用户输入匹配当前步骤 | 执行当前步骤 |
| 有进行中的任务，用户输入为新意图 | 暂停当前任务，执行新意图；后续可恢复 |
| 有进行中的任务，用户输入"下一步" | 推进到下一 pending 步骤 |
| 有进行中的任务，用户输入"跳过" | 当前步骤标记 skipped，进入下一步 |
| 有进行中的任务，用户输入"不做了" | 任务标记 cancelled |

### 3.6 与渐进式生成的关系

任务状态机负责宏观步骤规划，渐进式生成负责单步内的信息收集。两者可叠加：

- 任务状态机决定当前步骤（如 diagnosis）
- 渐进式生成在该步骤内收集必要信息（如账号链接）

---

## 四、数据库 Schema

```sql
CREATE TABLE IF NOT EXISTS task_states (
    id BIGSERIAL PRIMARY KEY,
    task_id UUID NOT NULL UNIQUE,
    user_id VARCHAR(128) NOT NULL,
    conversation_id VARCHAR(128) NOT NULL,
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    current_step VARCHAR(64) NOT NULL,
    steps JSONB NOT NULL,
    collected_info JSONB NOT NULL DEFAULT '{}',
    next_action VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_states_user_conv_active
    ON task_states (user_id, conversation_id, status)
    WHERE status IN ('pending', 'in_progress');
```

---

## 五、错误处理

| 错误场景 | 处理策略 |
|----------|----------|
| 数据库不可用 | 降级为内存任务状态，不阻断服务 |
| 任务状态损坏 | 创建新任务，旧任务标记 cancelled |
| 步骤执行失败 | 标记步骤 failed，询问用户是否重试或跳过 |
| 任务冲突 | 以最新任务为准，旧任务自动 paused |

---

## 六、安全合规

| 要求 | 实现 |
|------|------|
| 用户数据隔离 | 查询必须带 `user_id` + `conversation_id` |
| 不泄露他人任务 | 严格按用户维度隔离 |
| 任务状态不可被用户篡改 | 只通过系统逻辑更新 |

---

## 七、接口兼容性声明

- 不修改 `/api/v1/debug/chat/stream` 接口路径
- 不修改 SSE 事件类型
- 任务状态通过现有 `clarification` 类型回复引导用户
- 新增环境变量 `LUMINA_ENABLE_TASK_STATE`

---

## 八、Feature Flag

```bash
LUMINA_ENABLE_TASK_STATE=true   # 启用任务状态机
LUMINA_ENABLE_TASK_STATE=false  # 回滚到原单步处理
```

---

## 九、测试用例（TDD Harness）

### 9.1 单元测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_create_task | "帮我运营账号" | 创建 account_growth 任务，current_step=diagnosis |
| test_resume_task | 任务进行中，用户再说"继续" | 读取状态，继续 diagnosis |
| test_skip_step | 用户说"跳过" | 当前步骤 skipped，进入下一步 |
| test_cancel_task | 用户说"不做了" | 任务 cancelled |
| test_complete_task | 所有步骤完成 | 任务 completed |
| test_pause_for_new_intent | 任务进行中，用户问"帮我写文案" | 任务 paused，执行 content 意图 |
| test_disable_flag | Flag=false | 不创建任务，按原 intent 处理 |

### 9.2 集成测试

| 用例 | 输入 | 预期 |
|------|------|------|
| test_chat_stream_task_plan | "帮我运营账号" | 返回步骤计划引导 |
| test_chat_stream_task_resume | 中断后重新进入对话 | 不重复询问已提供信息 |
| test_chat_stream_task_next_step | 诊断完成后说"下一步" | 进入定位步骤 |

### 9.3 接口回归测试

| 用例 | 预期 |
|------|------|
| test_debug_chat_stream_sse_format | SSE 事件类型和字段不变 |
| test_existing_single_intent_unchanged | 单一意图不受任务状态机影响 |

---

## 十、实现文件

| 文件 | 说明 |
|------|------|
| 新增 `apps/orchestra/src/orchestra/task_state.py` | TaskState 模型、存储、生命周期管理 |
| `apps/orchestra/src/orchestra/core.py` | 在 `process()` 中集成任务状态机 |
| `apps/api/src/services/handlers/system_chat.py` | 无需改动，但需确保 context 透传 |
| 新增 `tests/orchestra/test_task_state.py` | 单元测试 |
| 新增 `tests/integration/test_task_state.py` | 集成测试 |

---

## 十一、风险与回滚

| 风险 | 缓解 |
|------|------|
| 任务状态机过度复杂 | 阶段 0 只支持 4 种任务类型 |
| 用户感知到流程变长 | 提供跳过和取消能力 |
| 数据库不可用 | 降级到内存状态 |
| 破坏现有单步体验 | Feature Flag 可秒级回滚 |

**回滚**：设置 `LUMINA_ENABLE_TASK_STATE=false` 即可。
