# Lumina 真实用户场景测试计划

> **版本**: v1.0  
> **目标**: 通过模拟三类真实用户（个人IP、小店铺、MCN机构），对 Lumina 系统进行端到端的真实性与实用性验证。  
> **测试范围**: 意图理解 → Agent 编排 → Skill 真实调用 → 结果可用性评估。

---

## 一、测试目标与通过标准

### 1.1 核心测试目标

| 维度 | 测试目标 | 关键验证点 |
|------|---------|-----------|
| **意图理解** | 对话过程中，系统能准确识别用户真实意图，不误判、不漏判 | L1规则命中、L2记忆召回、L3 LLM兜底、澄清触发、意图切换检测 |
| **Agent 调度** | 每个意图都能正确映射到对应的 Agent 组合，并以正确的执行模式（串行/并行/混合）运行 | `config/agents.yaml` 映射、`orchestra` 执行模式 |
| **Skill 可用性** | 14个 Skill 的核心 Tools 在真实调用下不报错，返回结构符合预期 | 每个 Skill 至少 1 个 Happy Path + 1 个 Error Path |
| **结果实用性** | 返回内容对真实用户具有可直接使用或参考的价值，不是空泛的模板回复 | 人工/自动化评估：具体性、可操作性、平台适配性 |

### 1.2 通用通过标准（Go/No-Go）

- **P0（阻塞级）**: API 返回 200，意图识别正确，Agent 被触发，Skill 无未捕获异常。
- **P1（功能级）**: Skill 返回结果包含预期字段，非空，格式正确。
- **P2（体验级）**: 回复内容符合用户角色语境，具备平台特异性（如提到抖音/小红书/B站的差异），可直接落地执行或只需微调。

---

## 二、测试角色定义

### 角色 A：个人媒体工作者（个人IP打造者）

**画像**: 小美，25岁，自由职业者，想在抖音和小红书做“职场穿搭”个人IP。粉丝量<1000，没有团队，预算有限，需要具体可执行的建议。

**核心诉求**: 
- 账号定位和选题方向
- 低成本的内容创作（文案、脚本）
- 了解自己的账号问题
- 学习爆款方法论

**测试用户ID前缀**: `u_individual_{场景名}`

---

### 角色 B：小店铺经营者

**画像**: 老王，40岁，经营一家社区火锅店，想在抖音做本地生活推广，吸引周边客流。对互联网运营术语不熟悉，说话口语化。

**核心诉求**:
- 写能吸引本地顾客的推广文案
- 检查文案有没有违规风险
- 了解竞争对手在做什么
- 看看投放效果（如果做过）

**测试用户ID前缀**: `u_shop_{场景名}`

---

### 角色 C：MCN机构运营

**画像**: 李经理，MCN机构内容运营负责人，管理 20+ 个达人账号（抖音+小红书矩阵）。需要批量生产内容、监控多账号健康度、设计流量互导策略。

**核心诉求**:
- 矩阵账号整体规划
- 一稿多改批量生成
- 批量账号诊断/健康检查
- 成功案例拆解复制
- SOP 流程优化

**测试用户ID前缀**: `u_mcn_{场景名}`

---

## 三、测试场景矩阵（共 32 个场景）

### 3.1 通用对话与意图基础测试（3个角色 × 5个场景 = 15个）

这些场景验证 Intent Engine 的 L1/L2/L3、澄清、切换检测能力。

| 场景ID | 角色 | 用户输入示例 | 预期意图 kind | 预期触发的 Agent | 验证重点 |
|--------|------|-------------|---------------|-----------------|----------|
| `INT-001` | A | "你好" | `conversation` | `intent_parser` | L1 规则：casual 问候 |
| `INT-002` | A | "今天天气怎么样" | `conversation` | `intent_parser` | L1 规则：生活闲聊 |
| `INT-003` | B | "帮我看看" | `clarify_feedback` | `intent_parser` | 模糊输入触发澄清 |
| `INT-004` | A | 先问 "你好"，再问 "帮我诊断账号" | 第2轮 `diagnosis` | `data_analyst` + `content_strategist` | 意图切换检测 |
| `INT-005` | C | "帮我诊断账号、写文案、还要做矩阵规划" | 根据主次意图分类 | 主要意图对应的 Agent | 多意图输入的识别与取舍 |

> 注：B、C 角色也会覆盖类似的基础意图场景（在完整表格中展开）。

### 3.2 单账号运营 Agent 组测试（覆盖 6 个 Agent / 6 个 Skill）

#### Agent: `content_strategist` → Skill: `skill-content-strategist`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `STR-001` | A | "我是做职场穿搭的，账号怎么定位？" | `strategy` / `positioning` | `analyze_positioning` | 回复包含：人设定位、目标受众、差异化建议、内容方向 |
| `STR-002` | A | "帮我生成未来一周的选题日历" | `strategy` / `topic_selection` | `generate_topic_calendar` | 回复包含：7个具体选题、每个选题的标题建议、适合发布时间 |
| `STR-003` | B | "火锅店怎么在抖音上定位" | `strategy` | `analyze_positioning` | 回复包含：本地生活定位策略、目标客群（周边3公里）、内容形式建议 |
| `STR-004` | A | "分析下这个竞品账号：@职场穿搭Lisa" | `competitor` | `analyze_competitor_real` | 如无法RPA抓取，应给出合理的降级方案或引导提供主页链接 |

#### Agent: `creative_studio` → Skill: `skill-creative-studio`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `CRE-001` | A | "帮我写一条抖音文案，主题是'面试穿搭避雷'" | `content_creation` | `generate_text` | 文案包含：钩子开头、3个避雷点、行动号召，符合抖音口播风格 |
| `CRE-002` | B | "写个小红书笔记，推广我家火锅店的招牌毛肚" | `content_creation` | `generate_text` | 笔记包含：标题、正文、话题标签，符合小红书种草风格 |
| `CRE-003` | A | "帮我写一个30秒的短视频脚本，讲职场新人穿搭" | `script_creation` | `generate_script` | 脚本包含：时长分配、画面描述、口播台词、BGM建议 |
| `CRE-004` | B | "优化这个标题：火锅店开业了" | `content_creation` | `optimize_title` | 给出 3-5 个优化后的标题，并说明优化理由 |
| `CRE-005` | A | "基于'面试穿搭'主题，生成3个不同风格的变体" | `content_creation` | `batch_generate_variations` | 返回3个风格差异明显的版本（如干货型/故事型/反转型） |

#### Agent: `data_analyst` → Skill: `skill-data-analyst`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `DAT-001` | A | "帮我诊断一下账号"（提供小红书主页链接） | `diagnosis` | `diagnose_account` | 返回：账号健康评分、内容质量分析、发布规律分析、3条可执行建议 |
| `DAT-002` | B | "我最近的流量为什么跌了" | `traffic_analysis` | `analyze_traffic` + `detect_anomalies` | 分析可能原因（内容/发布时间/平台算法/竞争环境），给出建议 |
| `DAT-003` | C | "给这20个账号做批量诊断" | `diagnosis` | `diagnose_account`（批量）或 `check_account_health_batch` | 批量返回各账号状态概览，异常账号高亮 |
| `DAT-004` | A | "生成我上周的数据周报" | `data_analysis` | `generate_weekly_report` | 包含：关键指标趋势、内容表现TOP3、下周优化建议 |

#### Agent: `growth_hacker` → Skill: `skill-growth-hacker`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `GRW-001` | B | "我想在抖音投本地推广，怎么设置" | `growth_strategy` | `design_ad_strategy` | 给出：投放目标建议、预算分配、定向设置（本地3公里）、内容素材建议 |
| `GRW-002` | B | "帮我设计一个A/B测试，看哪个标题更好" | `growth_strategy` | `design_ab_test` | 给出：测试假设、分组方案、观察指标、测试周期 |
| `GRW-003` | A | "我的千川投放ROI怎么优化" | `growth_strategy` / `traffic_analysis` | `optimize_bidding` | 给出：出价策略、人群包优化、素材迭代建议 |

#### Agent: `community_manager` → Skill: `skill-community-manager`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `COM-001` | A | "有人评论'衣服哪里买'，帮我回复" | `community_management` | `generate_comment_reply` | 回复自然、带引导（如置顶链接/私信）、不机械 |
| `COM-002` | A | "帮我分析一下粉丝画像，分分层" | `fan_engagement` | `segment_fans` | 给出：粉丝分层维度（如活跃粉/潜水粉/转化粉）、各层运营策略 |
| `COM-003` | B | "设置一下自动回复，有人问地址就回复" | `community_management` | `auto_reply_settings` | 返回自动回复规则配置（触发词+回复内容） |

#### Agent: `compliance_officer` → Skill: `skill-compliance-officer`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `CMP-001` | B | "帮我检查这个文案有没有违规风险"（提供文案） | `risk_check` | `check_content_risk` | 明确标出风险点（如极限词、虚假宣传）、给出修改建议 |
| `CMP-002` | A | "说'全网最低价'会不会被限流" | `risk_check` | `check_content_risk` | 指出具体违规类型（价格误导/极限词）、建议替代表述 |
| `CMP-003` | C | "检查这10条内容的合规性" | `compliance_review` | `check_content_risk`（批量） | 批量返回每条的风险等级和修改建议 |

### 3.3 矩阵协同 Agent 组测试（覆盖 6 个 Agent / 6 个 Skill）

#### Agent: `matrix_commander` → Skill: `skill-matrix-commander`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `MAT-001` | C | "帮我规划一个职场类账号矩阵" | `matrix_setup` | `plan_matrix_strategy` | 给出：主号+卫星号定位、各账号内容分工、起号顺序 |
| `MAT-002` | C | "设计矩阵内部的流量互导路径" | `matrix_strategy` | `design_traffic_routes` | 给出：导流节点设计、评论区引导策略、主页引流链路 |
| `MAT-003` | C | "生成矩阵账号一周的协同发布日历" | `matrix_strategy` | `generate_collaboration_calendar` | 给出：各账号每日发布内容、互动配合时间点 |

#### Agent: `bulk_creative` → Skill: `skill-bulk-creative` + `skill-creative-studio`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `BLK-001` | C | "把这条职场穿搭脚本改写成适合抖音、小红书、B站三个平台的版本" | `content_variation` | `adapt_platform` | 三个版本具有明显的平台调性差异（抖音重口播、小红书重图文、B站重深度） |
| `BLK-002` | C | "批量生成10条职场穿搭的标题变体" | `bulk_creation` | `generate_variations` | 返回10条差异化标题，覆盖不同角度（痛点/好奇/共鸣/利益） |
| `BLK-003` | C | "优化这50条标题" | `bulk_creation` | `batch_optimize` | 批量返回优化结果，附带优化原因分类统计 |

#### Agent: `account_keeper` → Skill: `skill-account-keeper`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `ACC-001` | C | "批量登录这10个小红书账号" | `batch_login` | `batch_login` | 返回各账号登录状态，失败账号说明原因 |
| `ACC-002` | C | "检查所有账号的健康状态" | `account_maintenance` | `check_account_health_batch` | 返回账号状态清单（正常/异常/需登录），异常项说明 |
| `ACC-003` | C | "导出所有账号的Cookie" | `account_maintenance` | `export_cookies` | 成功导出或给出安全提示/操作路径 |

#### Agent: `traffic_broker` → Skill: `skill-traffic-broker`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `TRF-001` | C | "设计从抖音主号导流到小红书卫星号的路径" | `traffic_routing` | `design_traffic_route` | 给出：导流话术、评论区运营、主页跳转、风险规避 |
| `TRF-002` | C | "计算这个流量互导方案的价值" | `cross_promotion` | `calculate_traffic_value` | 给出：预估转化漏斗、各节点转化率、价值估算 |
| `TRF-003` | C | "优化矩阵内部的交叉推广" | `cross_promotion` | `optimize_cross_promotion` | 给出：当前问题诊断、优化后的内容配合策略 |

#### Agent: `knowledge_miner` → Skill: `skill-knowledge-miner`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `KNO-001` | A | "拆解这个爆款视频：'职场穿搭3个禁忌'" | `case_analysis` | `analyze_success_content` | 给出：爆款结构（钩子+痛点+解决方案+行动号召）、可复制元素 |
| `KNO-002` | C | "从最近10个职场类爆款中提取可复用的模式" | `pattern_extraction` | `extract_patterns` | 给出：共同开头模式、内容框架、标题公式、适用条件 |
| `KNO-003` | A | "为什么这个视频爆了，帮我归因" | `case_analysis` | `attribute_success` | 给出：时机/内容/算法/互动等多维度归因 |

#### Agent: `sop_evolver` → Skill: `skill-sop-evolver`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `SOP-001` | C | "评估我们当前的内容生产SOP" | `sop_optimization` | `evaluate_sop` | 给出：SOP各环节效率评分、瓶颈识别、改进建议 |
| `SOP-002` | C | "根据最近的爆款数据，进化我们的选题策略" | `process_evolution` | `evolve_strategy` | 给出：数据洞察、策略调整方向、新SOP草案 |
| `SOP-003` | A | "推荐一个适合新人起号的方法论" | `knowledge_qa` | `knowledge_retrieval` + `retrieve_methodology` | 给出：方法论名称、适用场景、执行步骤、注意事项 |

### 3.4 通用工具 Agent 与 RPA 测试

#### Agent: `rpa_executor` → Skill: `skill-rpa-executor`

| 场景ID | 角色 | 用户输入 | 预期子意图 | 需调用的核心 Tools | 可用性评估标准 |
|--------|------|---------|-----------|-------------------|---------------|
| `RPA-001` | A | "帮我登录抖音账号" | `qr_login` | `execute_task` (login) | 返回二维码图片/链接 + 操作指引 |
| `RPA-002` | B | "抓取这个竞品账号的数据" | `competitor` / `data_collection` | `execute_task` (crawl_account) | 成功返回数据或明确说明需登录/授权 |
| `RPA-003` | C | "批量发布这20条内容到小红书" | `content_publish` | `batch_execute` (publish) | 返回发布任务队列状态，失败项说明原因 |

### 3.5 SOP / 方法论执行链路测试

| 场景ID | 角色 | 用户输入 | 预期 kind | 需调用的 SOP | 可用性评估标准 |
|--------|------|---------|-----------|-------------|---------------|
| `SOP-004` | A | "用 AIDA 方法论帮我写一条文案" | `methodology` | `aida_advanced` | 文案明显体现 AIDA 四阶段结构 |
| `SOP-005` | A | "用钩子-故事-offer结构写个脚本" | `methodology` | `hook_story_offer` | 脚本包含：钩子（3秒留人）、故事（共鸣/冲突）、offer（行动号召） |
| `SOP-006` | B | "给我推荐一个适合本地生活推广的方法论" | `methodology` / `qa` | 平台适配的方法论 | 根据店铺特点推荐合适的方法论并解释原因 |

### 3.6 平台规范适配测试

| 场景ID | 角色 | 用户输入 | 预期平台 | 验证重点 |
|--------|------|---------|---------|----------|
| `PLT-001` | A | "帮我写一条抖音文案" | `douyin` | 文案应符合抖音规范（口播感强、节奏快、善用口语化表达） |
| `PLT-002` | A | "帮我写一条小红书笔记" | `xiaohongshu` | 笔记应符合小红书规范（种草感、emoji、分段清晰、话题标签） |
| `PLT-003` | A | "帮我写一条B站脚本" | `bilibili` | 脚本应符合B站规范（开场留人、内容深度、互动梗、节奏适中） |

---

## 四、测试执行方式

### 4.1 测试代码结构

测试代码将放在 `tests/real_world/` 目录下，分为以下文件：

```
tests/real_world/
├── test_plan.md              # 本测试计划
├── conftest.py               # 共享 fixture（TestClient、mock 控制）
├── test_intent_understanding.py   # 意图理解测试（覆盖 L1/L2/L3/澄清/切换）
├── test_single_account_agents.py  # 单账号运营 Agent 测试
├── test_matrix_agents.py          # 矩阵协同 Agent 测试
├── test_rpa_and_sop.py            # RPA、SOP、平台规范测试
└── test_usability_criteria.py     # 可用性自动化评估（结果结构+内容评分）
```

### 4.2 测试模式

- **Mock 模式**: 对于依赖外部 LLM / RPA 浏览器的测试，默认使用 `unittest.mock` 进行可控 mock，验证链路完整性。
- **真实调用模式（可选）**: 通过环境变量 `LUMINA_TEST_REAL_CALLS=1` 开启。此时会真实调用配置好的 LLM 和 RPA。该模式需要：
  - 有效的 LLM API Key
  - RPA 浏览器环境可用
  - 测试账号数据准备就绪（不会操作真实生产账号，使用测试账号）

### 4.3 数据准备清单

在开启真实调用模式前，需准备以下测试数据：

1. **测试账号链接**:
   - 小红书测试主页链接 × 2
   - 抖音测试主页链接 × 2
2. **测试文案内容**:
   - 1条待检查的推广文案（含潜在风险词）
   - 1条待优化的标题
   - 1条待改编的脚本
3. **测试矩阵账号列表**:
   - 5个模拟账号信息（平台、昵称、定位）
4. **LLM 配置确认**:
   - `config/llm.yaml` 中测试用模型可访问

---

## 五、测试自动化评估规则（可用性评分）

为减少主观判断，设计以下自动化评估规则：

### 5.1 结构化检查（硬规则，必须全部通过）

| 检查项 | 说明 |
|--------|------|
| `has_reply` | 返回体中包含非空的 `reply` 字段 |
| `has_intent` | 返回体中包含 `intent.kind`，且与预期一致 |
| `has_agent_calls` | `hub.result` 或 `debug` 中记录了预期的 Agent / Skill 调用 |
| `no_uncaught_error` | 无 500 错误，无未捕获异常 traceback |
| `platform_aware` | 回复文本中提及了用户指定的平台名称（抖音/小红书/B站） |

### 5.2 内容质量检查（软规则，80%通过即可）

| 检查项 | 说明 | 评分方式 |
|--------|------|---------|
| `actionable` | 回复中包含明确的行动建议（如"建议周三晚上8点发布"） | 正则/LLM 判分 |
| `specific` | 回复中没有大面积的空泛套话（如"持续努力就会成功"） | LLM 判分 0-1 |
| `role_context` | 回复符合用户角色语境（个人IP/小店铺/MCN） | LLM 判分 0-1 |
| `format_correct` | 如用户要求"脚本"，返回格式应为脚本格式（分镜/台词/时长） | 结构化检查 |

### 5.3 可用性评分公式

```
可用性得分 = (硬规则通过数 / 硬规则总数) * 0.6 + (软规则平均分) * 0.4
```

- **得分 ≥ 0.85**: 优秀，可直接使用
- **得分 0.70 - 0.85**: 良好，需轻微调整
- **得分 < 0.70**: 不及格，需优化 Agent / Prompt / Skill

---

## 六、执行计划与里程碑

| 阶段 | 任务 | 预计耗时 | 交付物 |
|------|------|---------|--------|
| **Phase 1** | 搭建测试框架（fixture、mock、评估函数） | 1 天 | `conftest.py` + 评估模块 |
| **Phase 2** | 实现意图理解测试（32个场景中的对话基础测试） | 1 天 | `test_intent_understanding.py` |
| **Phase 3** | 实现单账号 Agent 测试 | 2 天 | `test_single_account_agents.py` |
| **Phase 4** | 实现矩阵 Agent 测试 | 2 天 | `test_matrix_agents.py` |
| **Phase 5** | 实现 RPA / SOP / 平台规范测试 | 1 天 | `test_rpa_and_sop.py` |
| **Phase 6** | 运行真实调用测试，输出可用性报告 | 2 天 | 测试报告 + 问题清单 |

---

## 七、待用户确认事项

在正式开始编写测试代码前，请确认以下事项：

1. **角色覆盖**: 上述三类角色（个人IP / 小店铺 / MCN）是否符合你的目标用户画像？是否需要新增角色（如品牌方、电商大卖家）？
2. **场景优先级**: 32 个场景中，哪些属于 P0（必须优先测），哪些可以延后？
3. **真实调用测试**: 是否计划运行真实 LLM / RPA 调用测试？如果是，请确认测试账号和数据是否已准备。
4. **可用性标准**: 上述自动化评估规则是否满足你的预期？是否需要增加人工抽检环节？
5. **输出格式**: 测试代码完成后，你希望以什么形式接收测试结果？（pytest HTML 报告 / Markdown 报告 / 两者都要）

---

*文档生成时间: 2026-04-16*  
*下一步: 用户审核确认后，进入 Phase 1 测试框架搭建。*
