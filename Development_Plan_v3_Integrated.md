# Lumina AI营销平台开发计划 V3.0（整合版）

> **版本**：V3.0  
> **日期**：2026-03-30  
> **架构策略**：OpenClaw 原生扩展 + 工业级 Intent 层 + Python MCP Skill  
> **核心理念**：保留 OpenClaw 对话能力，强化意图识别准确性，分阶段交付单账号与矩阵能力

---

## 📋 目录

1. [架构总览](#1-架构总览)
2. [产品功能映射](#2-产品功能映射)
3. [开发阶段规划](#3-开发阶段规划)
4. [核心模块详细设计](#4-核心模块详细设计)
5. [Agent集群实现方案](#5-agent集群实现方案)
6. [技术规范](#6-技术规范)
7. [里程碑与交付物](#7-里程碑与交付物)
8. [团队配置与分工](#8-团队配置与分工)
9. [风险管控](#9-风险管控)
10. [附录](#10-附录)

---

## 1. 架构总览

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Layer 1: 用户交互层 (UI Layer)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │Lumina Studio│  │  移动端App   │  │   IM插件    │  │   API网关   │              │
│  │  (Web端)    │  │(iOS/Android)│  │(钉钉/飞书)  │  │  (OpenAPI)  │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         └─────────────────┴─────────────────┴─────────────────┘                   │
│                                    │                                              │
│                              WebSocket/HTTP                                       │
└────────────────────────────────────┼──────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼──────────────────────────────────────────────┐
│                         Layer 2: OpenClaw 原生层                                │
│                                    │                                              │
│  ┌─────────────────────────────────┴─────────────────────────────────┐           │
│  │                    OpenClaw Core (Node.js)                         │           │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │           │
│  │  │   Gateway    │  │Agent Runtime │  │    Session Manager       │  │           │
│  │  │              │  │  (ReAct循环)  │  │  • 对话状态机            │  │           │
│  │  │ • WebSocket  │  │              │  │  • 上下文管理            │  │           │
│  │  │ • 消息路由   │  │ • 工具选择   │  │  • 记忆持久化            │  │           │
│  │  │ • 心跳检测   │  │ • 澄清机制   │  │                          │  │           │
│  │  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │           │
│  │         │                 │                       │                │           │
│  │         └─────────────────┴───────────────────────┘                │           │
│  │                           │                                        │           │
│  │                    ┌──────┴──────┐                                 │           │
│  │                    │  MCP Client │ ◄── Bridge 扩展                 │           │
│  │                    └──────┬──────┘                                 │           │
│  └───────────────────────────┼────────────────────────────────────────┘           │
└──────────────────────────────┼────────────────────────────────────────────────────┘
                               │ MCP Protocol (SSE/HTTP)
┌──────────────────────────────┼────────────────────────────────────────────────────┐
│                    Layer 3: Python AI Core Service                               │
│                              │                                                   │
│  ┌───────────────────────────┴───────────────────────────────────────────────┐  │
│  │                    Intent Engine (工业级实现)                                │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │  L1 规则层   │  │L2 向量记忆层 │  │L2.5轻量分类 │  │ L3 LLM分类器    │  │  │
│  │  │             │  │             │  │             │  │                 │  │  │
│  │  │•硬规则匹配  │  │•用户记忆检索│  │•BERT分类   │  │•GPT-4o/Claude  │  │  │
│  │  │•热加载配置  │  │•全局模式匹配│  │•成本优化   │  │•置信度校准      │  │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │  │
│  │         └─────────────────┴─────────────────┴─────────────────┘           │  │
│  │                                    │                                      │  │
│  │                    ┌───────────────┴───────────────┐                      │  │
│  │                    │      意图切换检测器           │                      │  │
│  │                    │   • 话题切换识别              │                      │  │
│  │                    │   • 动态阈值调整              │                      │  │
│  │                    └───────────────┬───────────────┘                      │  │
│  │                                    │                                      │  │
│  │                    ┌───────────────┴───────────────┐                      │  │
│  │                    │        澄清引擎               │                      │  │
│  │                    │   • 指代消解                  │                      │  │
│  │                    │   • 选项生成                  │                      │  │
│  │                    └───────────────┬───────────────┘                      │  │
│  └────────────────────────────────────┼──────────────────────────────────────┘  │
│                                       │                                         │
│  ┌────────────────────────────────────┼───────────────────────────────────────┐ │
│  │                    LLM Management Hub                                       │ │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────────────────────────┐  │ │
│  │  │  LLM Pool  │  │  Assignment  │  │         Strategy Engine             │  │ │
│  │  │            │  │   分配策略    │  │                                     │  │ │
│  │  │•Claude-4   │  │             │  │ • 显式指定                          │  │ │
│  │  │•GPT-4o     │  │ • 按Skill   │  │ • 成本优先                          │  │ │
│  │  │•DeepSeek   │  │ • 按策略    │  │ • 质量优先                          │  │ │
│  │  │•DeepSeek-R1│  │             │  │ • 延迟优先                          │  │ │
│  │  └────────────┘  └──────────────┘  └─────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                       │                                          │
│  ┌────────────────────────────────────┼───────────────────────────────────────┐ │
│  │                 MCP Skill Hub (Agent集群实现)                               │ │
│  │                                                                              │ │
│  │   单账号Agent组                    │          矩阵Agent组                   │ │
│  │  ┌─────────────────────────────┐   │   ┌─────────────────────────────┐     │ │
│  │  │ • ContentStrategistSkill    │   │   │ • MatrixCommanderSkill      │     │ │
│  │  │ • CreativeStudioSkill       │   │   │ • BulkCreativeSkill         │     │ │
│  │  │ • GrowthHackerSkill         │   │   │ • AccountKeeperSkill        │     │ │
│  │  │ • DataAnalystSkill          │   │   │ • TrafficBrokerSkill        │     │ │
│  │  │ • CommunityManagerSkill     │   │   │ • KnowledgeMinerSkill       │     │ │
│  │  │ • ComplianceOfficerSkill    │   │   │ • SOPEvolverSkill           │     │ │
│  │  └─────────────────────────────┘   │   └─────────────────────────────┘     │ │
│  │                                                                              │ │
│  │   通用Skill层                      │          工具Skill层                   │ │
│  │  ┌─────────────────────────────┐   │   ┌─────────────────────────────┐     │ │
│  │  │ • IntentParserSkill         │   │   │ • RPAExecutorSkill          │     │ │
│  │  │ • KnowledgeRetrievalSkill   │   │   │ • BrowserAutomationSkill    │     │ │
│  │  │ • MethodologySkill          │   │   │ • DataCollectionSkill       │     │ │
│  │  └─────────────────────────────┘   │   └─────────────────────────────┘     │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 架构设计原则

| 原则 | 说明 | 落地方式 |
|-----|------|---------|
| **对话优先** | 确保用户获得自然的对话体验 | 复用 OpenClaw 原生澄清机制，不重复造轮子 |
| **意图准确** | 营销 vs 闲聊意图识别准确率 > 95% | 工业级 Intent 层（L1/L2/L2.5/L3 四级架构） |
| **成本可控** | 降低 LLM 调用成本 | 规则层拦截 85%+ 闲聊，轻量分类器降本 50% |
| **模式解耦** | 单账号/矩阵模式可独立演进 | Agent 分组实现，共享通用 Skill |
| **渐进交付** | 先单账号深度，后矩阵规模 | 分 4 个 Milestone 交付 |

---

## 2. 产品功能映射

### 2.1 双模式功能对照

| 功能域 | 单账号精细化运营 | 多账号矩阵协同 | 共享基础设施 |
|-------|----------------|---------------|------------|
| **业务诊断** | 深度定位分析、人设设计 | 矩阵定位规划、主号-卫星号策略 | 诊断引擎、知识库 |
| **内容策略** | 选题日历、热点追踪 | 矩阵协同排期、差异化策略分发 | Intent 解析、热点数据源 |
| **创意生成** | 脚本/文案/视觉一体化 | 一稿多改批量生成（10+版本） | LLM Hub、Prompt 模板库 |
| **发布执行** | API/RPA 自动发布 | 批量 RPA 登录发布、错峰调度 | 无头浏览器网格 |
| **数据复盘** | 单账号深度归因分析 | 跨账号数据对比、矩阵效果评估 | 数据仓库、分析引擎 |
| **知识沉淀** | 个人案例库、内容模板 | 矩阵成功案例提取、SOP自动进化 | 向量数据库、知识图谱 |

### 2.2 技术实现映射

```
产品功能 ───────────────────────────────────────► 技术组件

用户输入 "帮我诊断账号"
    │
    ├──► OpenClaw Gateway (WebSocket)
    │
    ├──► Intent Engine (L1→L2→L3)
    │         └──► 识别: marketing/diagnosis
    │
    ├──► Agent Runtime (ReAct 循环)
    │         └──► 选择: DiagnosisSkill
    │
    ├──► MCP Bridge
    │         └──► 调用 Python Skill
    │
    └──► Python Layer
              ├──► AccountDiagnosisSkill
              │         ├──► 数据采集 (RPA/Data API)
              │         ├──► LLM 分析 (DeepSeek-R1)
              │         └──► 生成诊断报告
              │
              └──► 返回结构化结果
                         └──► OpenClaw 格式化回复
```

---

## 3. 开发阶段规划

### 3.1 总体时间线（16 周）

```
Week  1-2:  ████ 基础设施 + OpenClaw 环境准备
Week  3-4:  ████ 工业级 Intent 层开发
Week  5-6:  ████ MCP Bridge + LLM Hub
Week  7-9:  ████ 单账号 Agent 组（6个核心Agent）
Week 10-12: ████ 矩阵 Agent 组 + RPA 基础能力
Week 13-14: ████ 集成测试 + 对话体验优化
Week 15-16: ████ 性能压测 + 生产部署
```

### 3.2 详细阶段规划

#### Phase 1: 基础设施与 OpenClaw 环境（Week 1-2）

**目标**：搭建基础运行环境，验证 OpenClaw 原生对话能力

| 任务 | 负责人 | 输出物 | 验收标准 |
|-----|--------|--------|---------|
| 1.1 环境搭建 | DevOps | 开发环境 | Docker Compose 可一键启动 |
| 1.2 Fork OpenClaw | 架构师 | `vendor/openclaw/` | 保留 Git 历史，可同步上游 |
| 1.3 理解核心架构 | 架构师 | 架构文档 | 理解 Agent Runtime、Session State |
| 1.4 验证对话能力 | 架构师 | 测试报告 | 闲聊输入触发澄清而非返回 JSON |
| 1.5 数据库设计 | 后端工程师 | Schema 设计 | PostgreSQL + Redis  schema |

**关键验证点**：
```
输入: "今天过得怎么样"
期望: "请问你是想了解账号诊断，还是内容创作？"
禁止: 返回 JSON 或执行错误 Skill
```

#### Phase 2: 工业级 Intent 层（Week 3-4）

**目标**：实现高准确率、低成本的意图识别系统

| 任务 | 负责人 | 输出物 | 技术要点 |
|-----|--------|--------|---------|
| 2.1 L1 规则引擎 | 后端工程师 | `apps/intent/l1_rules.py` | 热加载 YAML 配置、正则匹配 |
| 2.2 L2 向量记忆 | 后端工程师 | `apps/intent/l2_memory.py` | 用户级 + 全局级混合记忆 |
| 2.3 L2.5 轻量分类器 | 算法工程师 | `apps/intent/l2_5_classifier.py` | BERT 微调模型（可选） |
| 2.4 L3 LLM 分类器 | 后端工程师 | `apps/intent/l3_llm.py` | GPT-4o-mini 兜底 |
| 2.5 置信度校准 | 算法工程师 | `apps/intent/calibrator.py` | Isotonic Regression |
| 2.6 意图切换检测 | 后端工程师 | `apps/intent/switch_detector.py` | 动态阈值调整 |
| 2.7 澄清引擎 | 后端工程师 | `apps/intent/clarification.py` | 指代消解、选项生成 |

**Intent 层架构实现**：

```python
# apps/intent/engine.py
class IntentEngine:
    """工业级意图识别引擎（L1/L2/L2.5/L3 四级架构）"""
    
    def __init__(self):
        self.l1_rules = L1RuleEngine("config/intent_rules.yaml")
        self.l2_memory = HybridMemoryStore(vector_store)
        self.l2_5_classifier = LightweightClassifier()  # 可选
        self.l3_llm = LLMClassifier()
        self.calibrator = ConfidenceCalibrator()
        self.switch_detector = IntentSwitchDetector()
        self.cache = IntentCache()
    
    async def recognize(self, text: str, user_id: str, session: dict) -> Intent:
        # 1. 缓存检查
        cache_key = self._get_cache_key(text, session)
        if cached := await self.cache.get(cache_key):
            return cached
        
        # 2. L1 规则层（零成本拦截）
        if intent := self.l1_rules.match(text):
            await self._cache_and_return(cache_key, intent)
        
        # 3. L2 向量记忆层
        if intent := await self.l2_memory.search(text, user_id):
            if intent.confidence > 0.85:
                await self._cache_and_return(cache_key, intent)
        
        # 4. L2.5 轻量分类器（降本增效）
        if self.l2_5_classifier:
            label, conf = await self.l2_5_classifier.predict(text)
            if conf > 0.9:
                intent = Intent(type=label, confidence=conf, source="l2_5")
                await self._cache_and_return(cache_key, intent)
        
        # 5. L3 LLM 分类器（最终兜底）
        intent = await self.l3_llm.classify(text, session)
        intent.confidence = self.calibrator.calibrate(intent.confidence)
        
        # 6. 动态阈值判定
        threshold = self._get_dynamic_threshold(user_id, session)
        if intent.confidence < threshold:
            intent.type = IntentType.AMBIGUOUS
        
        # 7. 意图切换检测
        if self.switch_detector.detect(intent, session):
            intent.type = IntentType.AMBIGUOUS
            intent.reason = "potential_topic_switch"
        
        await self.cache.set(cache_key, intent, ttl=300)
        return intent
```

**配置文件示例** (`config/intent_rules.yaml`)：

```yaml
# L1 规则配置（热加载）
casual:
  patterns:
    - "^你好$|^在吗$|^在么$"
    - "你是谁|你能做什么"
    - "天气|今天.*怎么样|几点|星期"
    - "讲个笑话|讲个故事"
    - "^\s*(hi|hello|hey)\s*$"
  
marketing:
  patterns:
    - "(诊断|分析|看看).*(账号|号|主页|数据)"
    - "(写|生成|创作).*(文案|脚本|内容|标题)"
    - "(选题|方向|定位|人设|IP).*(建议|思路|怎么做)"
    - "(流量|粉丝|曝光).*(提升|增加|优化)"
    - "(小红书|抖音|B站|视频号).*(运营|推广)"
  
  subtypes:
    diagnosis: "诊断|分析.*账号|看看.*号"
    content_creation: "文案|标题|正文|改写"
    script_creation: "脚本|分镜|口播"
    strategy: "选题|方向|定位|人设"
    risk_check: "风险|违规|审核|敏感词"

# 动态阈值配置
threshold:
  base: 0.7
  high_active_bonus: -0.1  # 历史对话>50时
  marketing_context_bonus: -0.05  # 上一轮是营销意图时
```

#### Phase 3: MCP Bridge + LLM Hub（Week 5-6）

**目标**：建立 Node.js-Python 通信通道，统一管理 LLM

| 任务 | 负责人 | 输出物 | 说明 |
|-----|--------|--------|------|
| 3.1 MCP Client (Node.js) | Node.js 后端 | `packages/mcp-bridge/client.js` | 连接 OpenClaw 与 Python |
| 3.2 MCP Server (Python) | Python 后端 | `apps/api/mcp_server.py` | FastMCP 实现 |
| 3.3 LLM Hub 配置中心 | Python 后端 | `packages/llm-hub/` | 两步配置法 |
| 3.4 Provider 适配器 | Python 后端 | `packages/llm-hub/providers/` | OpenAI/Claude/DeepSeek |
| 3.5 数据隔离层 | Python 后端 | `apps/core/isolation.py` | user_id 透传与隔离 |

**MCP Bridge 核心实现**：

```javascript
// packages/mcp-bridge/index.js
const { Client } = require('@modelcontextprotocol/sdk');

class IntentAwareBridge {
    constructor(pythonMcpUrl, timeoutMs = 3000) {
        this.pythonUrl = pythonMcpUrl;
        this.timeout = timeoutMs;
    }

    async execute(params, context) {
        const session = context.session;
        const sessionContext = {
            previous_intent: session.get('last_intent'),
            previous_topic: session.get('last_topic'),
            user_history_count: session.get('history_count', 0),
            intent_switch_count: session.get('intent_switch_count', 0),
            user_id: session.user_id,
        };

        // 1. 调用 Intent Engine（带重试）
        let intentResult;
        try {
            intentResult = await this.callWithRetry({
                name: "intent_recognize",
                arguments: { text: params.text, user_id: session.user_id, session_context: sessionContext }
            }, 2);
        } catch (err) {
            // Fallback: 保守假设为营销意图
            intentResult = { intent_type: 'marketing', confidence: 0.5, requires_clarification: false };
        }

        // 2. 处理澄清状态
        if (intentResult.requires_clarification) {
            session.setState('CLARIFYING', {
                questions: intentResult.questions,
                possible_intents: intentResult.suggestions,
                original_text: params.text
            });
            return { type: 'clarification', message: intentResult.questions[0], suggestions: intentResult.suggestions };
        }

        // 3. 更新会话上下文
        session.set('last_intent', intentResult.intent_type);
        session.set('last_topic', intentResult.topic || params.text);
        session.increment('history_count');

        // 4. 调用业务 Skill
        const businessResult = await this.callWithRetry({
            name: "marketing_orchestra",
            arguments: {
                user_input: params.text,
                confirmed_intent: intentResult.intent_type,
                intent_subtype: intentResult.subtype,
                user_id: session.user_id
            }
        });
        
        return businessResult;
    }
}
```

#### Phase 4: 单账号 Agent 组（Week 7-9）

**目标**：实现单账号精细化运营的 6 个核心 Agent

| Agent | Skill 名称 | 核心能力 | LLM 配置 |
|-------|-----------|---------|---------|
| 内容策略师 | `skill-content-strategist` | SWOT分析、选题日历、热点预测 | DeepSeek-V3 |
| 创意工厂 | `skill-creative-studio` | 脚本/文案/视觉生成 | Claude-Sonnet |
| 投放优化师 | `skill-growth-hacker` | 投放策略、A/B测试 | GPT-4o |
| 数据分析师 | `skill-data-analyst` | 归因分析、异常预警 | DeepSeek-V3 |
| 用户运营官 | `skill-community-manager` | 评论回复、粉丝分层 | GPT-4o-mini |
| 合规审查员 | `skill-compliance-officer` | 敏感词、品牌调性 | DeepSeek-V3 |

**Agent 实现示例**（创意工厂）：

```python
# skills/skill-creative-studio/main.py
from fastmcp import FastMCP
from llm_hub import get_client
from pydantic import BaseModel

mcp = FastMCP("creative_studio")

class ContentRequest(BaseModel):
    content_type: str  # post, script, copy
    topic: str
    platform: str  # xiaohongshu, douyin, bilibili
    tone: str = "professional"
    user_id: str

class ContentOutput(BaseModel):
    title: str
    content: str
    hashtags: list[str]
    cover_suggestion: str
    bgm_suggestion: str

@mcp.tool()
async def generate_content(request: ContentRequest) -> ContentOutput:
    """
    创意工厂：生成多模态营销内容
    自动路由到 Claude-Sonnet（创意能力强）
    """
    # 1. 获取 LLM（根据配置自动选择）
    llm = get_client(skill_name="creative_studio")
    
    # 2. 获取用户画像和历史数据
    profile = await get_user_profile(request.user_id)
    history = await get_user_history(request.user_id, limit=10)
    
    # 3. 构建 Prompt
    prompt = f"""
    基于以下信息生成{request.platform}平台的{request.content_type}：
    
    主题：{request.topic}
    调性：{request.tone}
    用户定位：{profile.positioning}
    历史爆款：{history.top_performing}
    
    请生成：
    1. 吸引人的标题（使用钩子理论）
    2. 正文内容（符合平台调性）
    3. 推荐标签（5-8个）
    4. 封面设计建议
    5. BGM推荐（如适用）
    """
    
    # 4. 调用 LLM
    response = await llm.complete(prompt, temperature=0.8)
    
    # 5. 解析并返回结构化结果
    return parse_content_response(response)
```

#### Phase 5: 矩阵 Agent 组 + RPA（Week 10-12）

**目标**：实现多账号矩阵协同的 6 个核心 Agent + 基础 RPA 能力

| Agent | Skill 名称 | 核心能力 | 依赖 |
|-------|-----------|---------|------|
| 矩阵指挥官 | `skill-matrix-commander` | 主号-卫星号策略设计 | 单账号 Agent 组 |
| 批量创意工厂 | `skill-bulk-creative` | 一稿多改（10+版本） | 创意工厂 Skill |
| 账号维护工 | `skill-account-keeper` | Cookie管理、养号 | 浏览器网格 |
| 流量互导员 | `skill-traffic-broker` | 评论@引流、私信回复 | RPA 执行器 |
| 知识提取器 | `skill-knowledge-miner` | 爆款拆解、归因分析 | 数据仓库 |
| SOP进化师 | `skill-sop-evolver` | 策略迭代、知识沉淀 | 知识图谱 |

**矩阵协同核心逻辑**：

```python
# skills/skill-matrix-commander/main.py
@mcp.tool()
async def plan_matrix_strategy(master_account: str, satellite_configs: list, user_id: str) -> dict:
    """
    矩阵指挥官：规划主号-卫星号协同策略
    """
    # 1. 分析主号定位
    master_profile = await analyze_account(master_account)
    
    # 2. 为每个卫星号生成分化策略
    strategies = []
    for config in satellite_configs:
        strategy = {
            "account_id": config["id"],
            "positioning": f"{master_profile.niche} - {config['angle']}",
            "content_differentiation": generate_differentiation(master_profile, config),
            "posting_schedule": calculate_optimal_schedule(config),
            "traffic_route": design_traffic_path(config, master_account)
        }
        strategies.append(strategy)
    
    # 3. 生成协同排期表
    calendar = generate_matrix_calendar(strategies)
    
    return {
        "master_strategy": master_profile,
        "satellite_strategies": strategies,
        "collaboration_calendar": calendar
    }

# skills/skill-bulk-creative/main.py
@mcp.tool()
async def generate_matrix_variations(master_content: dict, account_profiles: list, user_id: str) -> list:
    """
    批量创意工厂：基于主号内容生成多账号差异化版本
    """
    variations = []
    
    for profile in account_profiles:
        if profile["type"] == "细分领域":
            variation = await create_niche_version(master_content, profile)
        elif profile["type"] == "场景化":
            variation = await create_scenario_version(master_content, profile)
        elif profile["type"] == "地域化":
            variation = await create_local_version(master_content, profile)
        
        variations.append(variation)
    
    return variations
```

#### Phase 6: 集成测试与体验优化（Week 13-14）

| 任务 | 负责人 | 输出物 | 验收标准 |
|-----|--------|--------|---------|
| 6.1 端到端联调 | 全团队 | 测试报告 | 完整链路 < 2s |
| 6.2 意图识别测试 | 算法工程师 | 准确率报告 | 营销意图 > 95%，闲聊拦截 > 85% |
| 6.3 对话体验优化 | 产品 + 算法 | 体验报告 | 澄清质量评分 > 4.0/5 |
| 6.4 RPA 稳定性测试 | 后端工程师 | 压测报告 | 成功率 > 98% |

#### Phase 7: 性能压测与生产部署（Week 15-16）

| 任务 | 负责人 | 输出物 |
|-----|--------|--------|
| 7.1 性能压测 | DevOps | 压测报告 |
| 7.2 安全审计 | 安全工程师 | 审计报告 |
| 7.3 生产部署 | DevOps | 部署文档 |
| 7.4 监控告警 | DevOps | Grafana 面板 |
| 7.5 用户手册 | 产品 | 操作文档 |

---

## 4. 核心模块详细设计

### 4.1 Intent Engine 详细设计

#### 4.1.1 组件清单

| 组件 | 文件路径 | 核心职责 |
|-----|---------|---------|
| L1 Rule Engine | `apps/intent/l1_rules.py` | 硬规则匹配，零成本拦截 |
| L2 Memory Store | `apps/intent/l2_memory.py` | 向量检索 + 全局热模式 |
| L2.5 Classifier | `apps/intent/l2_5_classifier.py` | BERT 微调分类（可选） |
| L3 LLM Classifier | `apps/intent/l3_llm.py` | GPT-4o-mini 兜底 |
| Confidence Calibrator | `apps/intent/calibrator.py` | Isotonic Regression 校准 |
| Switch Detector | `apps/intent/switch_detector.py` | 意图切换检测 |
| Clarification Engine | `apps/intent/clarification.py` | 澄清问题生成 |
| Intent Cache | `apps/intent/cache.py` | Redis 缓存 |

#### 4.1.2 数据流

```
用户输入
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  L1 Rule Engine                                              │
│  • 匹配 casual patterns → 直接返回                           │
│  • 匹配 marketing patterns → 直接返回                        │
│  • 未匹配 → 进入 L2                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
┌──────────┐      ┌──────────────┐      ┌──────────────┐
│ L2 Memory│      │L2.5 Classifier│     │   L3 LLM    │
│ • 用户级 │      │  • BERT 分类   │      │ • GPT-4o   │
│ • 全局级 │      │  • <10ms 延迟 │      │ • 兜底保障 │
└────┬─────┘      └──────┬───────┘      └──────┬───────┘
     │                   │                    │
     └───────────────────┼────────────────────┘
                         ▼
              ┌──────────────────────┐
              │ Confidence Calibrator │
              │  Isotonic Regression  │
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │ Dynamic Threshold    │
              │ 基于用户活跃度调整    │
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │ Intent Switch Detector│
              │ 检测话题切换          │
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │ Clarification Engine │
              │ 生成澄清问题          │
              └──────────────────────┘
```

### 4.2 LLM Management Hub 设计

#### 4.2.1 配置结构

```yaml
# config/llm.yaml

# ========== 第一步：配置 LLM 池 ==========
llm_pool:
  claude-sonnet-4:
    provider: anthropic
    model: claude-sonnet-4-20250514
    api_key: ${ANTHROPIC_API_KEY}
    temperature: 0.5
    max_tokens: 8192
    tags: ["high-quality", "creative", "expensive"]
    cost_per_1k_input: 0.003
    cost_per_1k_output: 0.015
    
  gpt-4o:
    provider: openai
    model: gpt-4o
    api_key: ${OPENAI_API_KEY}
    tags: ["high-quality", "fast"]
    cost_per_1k_input: 0.005
    cost_per_1k_output: 0.015
    
  deepseek-v3:
    provider: deepseek
    model: deepseek-chat
    api_key: ${DEEPSEEK_API_KEY}
    tags: ["cheap", "fast", "chinese-optimized"]
    cost_per_1k_input: 0.0002
    cost_per_1k_output: 0.0004
    
  deepseek-r1:
    provider: deepseek
    model: deepseek-reasoner
    api_key: ${DEEPSEEK_API_KEY}
    tags: ["reasoning", "cheap", "chinese-optimized"]
    cost_per_1k_input: 0.0004
    cost_per_1k_output: 0.0016
    
  gpt-4o-mini:
    provider: openai
    model: gpt-4o-mini
    api_key: ${OPENAI_API_KEY}
    tags: ["cheap", "fast", "classification"]
    cost_per_1k_input: 0.00015
    cost_per_1k_output: 0.0006

# ========== 第二步：配置分配策略 ==========
default_llm: "deepseek-v3"

# Skill 级别的显式配置
skill_config:
  # 创意生成：需要高质量输出
  creative_studio:
    llm: "claude-sonnet-4"
    temperature: 0.8
    
  # 账号诊断：需要推理能力
  account_diagnosis:
    llm: "deepseek-r1"
    temperature: 0.3
    
  # Intent 分类：成本低优先
  intent_classification:
    llm: "gpt-4o-mini"
    temperature: 0.1
    
  # 内容改写：成本优先策略
  content_rewrite:
    strategy: "cost_aware"
    
  # 竞品监测：延迟优先
  competitor_monitor:
    strategy: "latency_first"

# 策略定义
strategies:
  cost_aware:
    priority: ["deepseek-v3", "gpt-4o-mini", "deepseek-r1"]
    
  quality_first:
    priority: ["claude-sonnet-4", "gpt-4o", "deepseek-r1"]
    
  latency_first:
    priority: ["gpt-4o-mini", "deepseek-v3", "gpt-4o"]
```

#### 4.2.2 调用接口

```python
# packages/llm-hub/client.py
from typing import Optional, Literal

class LLMClient:
    """统一的 LLM 调用接口"""
    
    def __init__(self, config_path: str = "config/llm.yaml"):
        self.config = load_config(config_path)
        self.providers = self._init_providers()
    
    def get_client(
        self,
        skill_name: Optional[str] = None,
        llm_name: Optional[str] = None,
        strategy: Optional[Literal["cost_aware", "quality_first", "latency_first"]] = None
    ) -> LLMInstance:
        """
        获取 LLM 客户端
        
        优先级：llm_name > skill_config > strategy > default
        """
        if llm_name:
            return self._get_by_name(llm_name)
        
        if skill_name and skill_name in self.config.skill_config:
            skill_cfg = self.config.skill_config[skill_name]
            if "llm" in skill_cfg:
                return self._get_by_name(skill_cfg["llm"])
            if "strategy" in skill_cfg:
                return self._get_by_strategy(skill_cfg["strategy"])
        
        if strategy:
            return self._get_by_strategy(strategy)
        
        return self._get_by_name(self.config.default_llm)
    
    async def complete(self, prompt: str, **kwargs) -> str:
        """统一的 complete 接口"""
        # 实现调用逻辑
        pass
```

### 4.3 无头浏览器网格（RPA 基础）

```python
# apps/rpa/browser_grid.py
class BrowserGrid:
    """
    无头浏览器网格管理器
    支持多账号并发、指纹伪装、Cookie隔离
    """
    
    def __init__(self):
        self.pool = BrowserPool(max_instances=50)
        self.anti_detect = AntiDetectionLayer()
        self.session_mgr = SessionManager()
        self.proxy_mgr = ProxyManager()
    
    async def create_session(self, account_id: str, platform: str) -> BrowserSession:
        """为指定账号创建隔离的浏览器会话"""
        # 1. 分配代理
        proxy = await self.proxy_mgr.allocate(account_id)
        
        # 2. 配置指纹
        fingerprint = self.anti_detect.generate_fingerprint()
        
        # 3. 创建浏览器实例
        browser = await self.pool.acquire()
        
        # 4. 应用反检测配置
        await self.anti_detect.apply(browser, fingerprint)
        
        # 5. 恢复登录态
        cookies = await self.session_mgr.load_cookies(account_id)
        await browser.set_cookies(cookies)
        
        return BrowserSession(browser, account_id, proxy)
    
    async def execute_task(self, session: BrowserSession, task: RPATask) -> TaskResult:
        """在指定会话中执行 RPA 任务"""
        try:
            result = await task.execute(session.browser)
            # 保存新的 cookies
            await self.session_mgr.save_cookies(session.account_id, await session.browser.get_cookies())
            return TaskResult(success=True, data=result)
        except Exception as e:
            return TaskResult(success=False, error=str(e))
```

---

## 5. Agent集群实现方案

### 5.1 Agent 与 Skill 的映射关系

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent 集群层                                 │
│                                                                  │
│  Agent（业务概念）              │   Skill（技术实现）            │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  ┌─────────────────────────┐   │   ┌─────────────────────────┐  │
│  │ 内容策略师               │   │   │ skill-content-strategist│  │
│  │ (Content Strategist)    │───┼──►│ • analyze_positioning() │  │
│  │                         │   │   │ • generate_calendar()   │  │
│  └─────────────────────────┘   │   │ • predict_trends()      │  │
│                                │   └─────────────────────────┘  │
│  ┌─────────────────────────┐   │   ┌─────────────────────────┐  │
│  │ 创意工厂                 │   │   │ skill-creative-studio   │  │
│  │ (Creative Studio)       │───┼──►│ • generate_script()     │  │
│  │                         │   │   │ • generate_copy()       │  │
│  └─────────────────────────┘   │   │ • suggest_visual()      │  │
│                                │   └─────────────────────────┘  │
│  ┌─────────────────────────┐   │   ┌─────────────────────────┐  │
│  │ 数据分析师               │   │   │ skill-data-analyst      │  │
│  │ (Data Analyst)          │───┼──►│ • analyze_metrics()     │  │
│  │                         │   │   │ • attribution_analysis()│  │
│  └─────────────────────────┘   │   │ • generate_report()     │  │
│                                │   └─────────────────────────┘  │
│                                │                                │
│  [矩阵模式 Agent]              │                                │
│                                │                                │
│  ┌─────────────────────────┐   │   ┌─────────────────────────┐  │
│  │ 矩阵指挥官               │   │   │ skill-matrix-commander  │  │
│  │ (Matrix Commander)      │───┼──►│ • plan_matrix()         │  │
│  │                         │   │   │ • design_coordination() │  │
│  └─────────────────────────┘   │   └─────────────────────────┘  │
│                                │   ┌─────────────────────────┐  │
│  ┌─────────────────────────┐   │   │ skill-bulk-creative     │  │
│  │ 批量创意工厂             │   │   │ • generate_variations() │  │
│  │ (Bulk Creative)         │───┼──►│ • adapt_platform()      │  │
│  │                         │   │   │ • optimize_timing()     │  │
│  └─────────────────────────┘   │   └─────────────────────────┘  │
│                                │                                │
└────────────────────────────────┴────────────────────────────────┘
```

### 5.2 Skill 调用协议

每个 Skill 遵循统一的 MCP 协议：

```python
# Skill 接口规范
@mcp.tool()
async def skill_function(
    # 业务参数
    param1: str,
    param2: int,
    
    # 上下文参数（自动注入）
    user_id: str,           # 用户ID（数据隔离）
    session_id: str,        # 会话ID
    intent_type: str,       # 意图类型
    intent_subtype: str,    # 意图子类型
) -> SkillOutput:
    """
    Skill 功能描述
    
    Args:
        param1: 参数1说明
        param2: 参数2说明
    
    Returns:
        SkillOutput 结构体
    """
    pass

# 统一的输出结构
class SkillOutput(BaseModel):
    success: bool
    data: Optional[dict]
    error: Optional[str]
    suggested_reply: Optional[str]  # 给用户的回复建议
    follow_up_questions: Optional[list[str]]  # 追问建议
```

### 5.3 Agent 编排模式

```python
# apps/orchestra/agent_orchestrator.py
class AgentOrchestrator:
    """
    Agent 编排器
    根据意图类型自动组建 Agent 小队
    """
    
    # 单账号模式 Agent 组合
    SINGLE_ACCOUNT_AGENTS = {
        "diagnosis": ["skill-content-strategist", "skill-data-analyst"],
        "content_creation": ["skill-creative-studio", "skill-compliance-officer"],
        "strategy": ["skill-content-strategist", "skill-data-analyst"],
        "data_analysis": ["skill-data-analyst", "skill-growth-hacker"],
    }
    
    # 矩阵模式 Agent 组合
    MATRIX_AGENTS = {
        "matrix_setup": ["skill-matrix-commander", "skill-account-keeper"],
        "bulk_creation": ["skill-bulk-creative", "skill-creative-studio"],
        "traffic_broker": ["skill-traffic-broker", "skill-community-manager"],
        "knowledge_mining": ["skill-knowledge-miner", "skill-sop-evolver"],
    }
    
    async def orchestrate(self, intent: Intent, user_id: str, mode: str = "single") -> AgentTeam:
        """根据意图组建 Agent 小队"""
        
        # 选择 Agent 组合
        if mode == "single":
            agent_names = self.SINGLE_ACCOUNT_AGENTS.get(intent.subtype, ["skill-content-strategist"])
        else:
            agent_names = self.MATRIX_AGENTS.get(intent.subtype, ["skill-matrix-commander"])
        
        # 创建 Agent 实例
        agents = [self._create_agent(name) for name in agent_names]
        
        # 确定执行模式（串行/并行）
        execution_mode = self._determine_execution_mode(intent)
        
        return AgentTeam(agents, execution_mode)
    
    async def execute_team(self, team: AgentTeam, context: dict) -> ExecutionResult:
        """执行 Agent 小队"""
        if team.mode == "parallel":
            # 并行执行
            results = await asyncio.gather(*[
                agent.execute(context) for agent in team.agents
            ])
            return self._merge_results(results)
        else:
            # 串行执行
            result = context
            for agent in team.agents:
                result = await agent.execute(result)
            return result
```

---

## 6. 技术规范

### 6.1 项目目录结构

```
lumina/
├── apps/
│   ├── api/                      # FastAPI + MCP Server
│   │   ├── main.py
│   │   ├── routers/
│   │   └── dependencies/
│   │
│   ├── intent/                   # 工业级 Intent 层
│   │   ├── __init__.py
│   │   ├── engine.py             # 主入口
│   │   ├── l1_rules.py           # L1 规则引擎
│   │   ├── l2_memory.py          # L2 向量记忆
│   │   ├── l2_5_classifier.py    # L2.5 轻量分类器
│   │   ├── l3_llm.py             # L3 LLM 分类器
│   │   ├── calibrator.py         # 置信度校准
│   │   ├── switch_detector.py    # 意图切换检测
│   │   └── clarification.py      # 澄清引擎
│   │
│   ├── orchestra/                # Agent 编排层
│   │   ├── __init__.py
│   │   ├── orchestrator.py       # Agent 编排器
│   │   ├── team.py               # Agent 小队
│   │   └── mode_router.py        # 单账号/矩阵模式路由
│   │
│   ├── core/                     # 核心基础设施
│   │   ├── database.py           # 数据库连接
│   │   ├── cache.py              # Redis 缓存
│   │   ├── isolation.py          # 数据隔离
│   │   └── security.py           # 安全模块
│   │
│   └── rpa/                      # RPA 基础能力
│       ├── browser_grid.py       # 浏览器网格
│       ├── anti_detection.py     # 反检测
│       └── executor.py           # 任务执行器
│
├── packages/
│   ├── llm-hub/                  # LLM 管理 Hub
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── client.py
│   │   └── providers/
│   │       ├── openai.py
│   │       ├── anthropic.py
│   │       └── deepseek.py
│   │
│   └── mcp-bridge/               # Node.js MCP Bridge
│       ├── index.js
│       ├── client.js
│       └── intent-aware-bridge.js
│
├── skills/                       # MCP Skills（Agent 实现）
│   ├── skill-content-strategist/
│   ├── skill-creative-studio/
│   ├── skill-data-analyst/
│   ├── skill-growth-hacker/
│   ├── skill-community-manager/
│   ├── skill-compliance-officer/
│   ├── skill-matrix-commander/
│   ├── skill-bulk-creative/
│   ├── skill-account-keeper/
│   ├── skill-traffic-broker/
│   ├── skill-knowledge-miner/
│   └── skill-sop-evolver/
│
├── vendor/
│   └── openclaw/                 # Fork 的 OpenClaw
│
├── config/
│   ├── llm.yaml                  # LLM 配置
│   ├── intent_rules.yaml         # Intent 规则
│   └── agents.yaml               # Agent 配置
│
├── tests/
├── docs/
├── scripts/
└── docker-compose.yml
```

### 6.2 API 规范

```yaml
# Intent 识别接口
POST /api/v1/intent/recognize
Request:
  text: string              # 用户输入
  user_id: string           # 用户ID
  session_id: string        # 会话ID
  
Response:
  intent_type: "marketing" | "casual" | "ambiguous"
  subtype: string           # 具体子类型
  confidence: float         # 置信度
  requires_clarification: boolean
  questions: [string]       # 澄清问题（如果需要）
  suggestions: [string]     # 选项建议

# Agent 执行接口
POST /api/v1/agent/execute
Request:
  user_input: string
  intent_type: string
  intent_subtype: string
  user_id: string
  mode: "single" | "matrix"
  
Response:
  success: boolean
  result: object
  reply: string             # 给用户的回复
  follow_up: [string]       # 追问建议
```

### 6.3 数据模型

```python
# 用户模型
class User(BaseModel):
    id: str
    created_at: datetime
    mode: Literal["single", "matrix"] = "single"
    settings: UserSettings

# 会话模型
class Session(BaseModel):
    id: str
    user_id: str
    state: Literal["idle", "clarifying", "executing", "completed"]
    last_intent: Optional[str]
    history: List[Message]
    created_at: datetime
    updated_at: datetime

# 意图模型
class Intent(BaseModel):
    type: Literal["marketing", "casual", "ambiguous", "system"]
    subtype: Optional[str]
    confidence: float
    entities: Dict[str, Any]
    reason: str              # 识别来源（L1/L2/L3）
    suggested_sop: Optional[str]

# Agent 执行记录
class AgentExecution(BaseModel):
    id: str
    session_id: str
    user_id: str
    intent: Intent
    agents: List[str]        # 参与的 Agent
    results: Dict[str, Any]
    latency_ms: int
    created_at: datetime
```

---

## 7. 里程碑与交付物

### 7.1 里程碑规划

| 里程碑 | 时间 | 核心交付 | 验收标准 |
|-------|------|---------|---------|
| **M1** | Week 2 | 基础设施就绪 | OpenClaw 可运行，对话澄清正常 |
| **M2** | Week 4 | Intent 层可用 | 意图识别准确率 > 90%，闲聊拦截 > 80% |
| **M3** | Week 6 | MCP Bridge 连通 | Node.js-Python 通信延迟 < 200ms |
| **M4** | Week 9 | 单账号 Agent 组 | 6 个核心 Agent 可工作，端到端 < 3s |
| **M5** | Week 12 | 矩阵 Agent 组 + RPA | 批量发布功能可用，RPA 成功率 > 95% |
| **M6** | Week 14 | 集成测试通过 | 完整链路可用，体验评分 > 4.0 |
| **GA** | Week 16 | 生产发布 | 监控告警完备，文档齐全 |

### 7.2 关键指标

| 指标类别 | 指标名称 | 目标值 |
|---------|---------|--------|
| **准确性** | 营销意图识别准确率 | > 95% |
| **准确性** | 闲聊意图拦截率 | > 85% |
| **准确性** | 意图切换检测准确率 | > 90% |
| **性能** | 端到端响应时间（P95） | < 3s |
| **性能** | Intent 识别延迟 | < 200ms |
| **性能** | MCP 通信延迟 | < 100ms |
| **成本** | LLM 调用成本（vs 全用 GPT-4o） | 降低 60% |
| **稳定性** | RPA 任务成功率 | > 98% |
| **稳定性** | 系统可用性 | > 99.5% |

---

## 8. 团队配置与分工

### 8.1 团队结构

```
                    ┌──────────────┐
                    │   架构师     │
                    │  (1人)       │
                    └──────┬───────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  Intent 团队 │ │  Agent 团队  │ │  基础设施团队 │
    │  (2人)       │ │  (3人)       │ │  (2人)       │
    └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
           │               │               │
    ┌──────┴───────┐ ┌──────┴───────┐ ┌──────┴───────┐
    │• L1/L2/L3    │ │• Skill开发   │ │• OpenClaw    │
    │• 置信度校准   │ │• Agent编排   │ │• MCP Bridge  │
    │• 切换检测     │ │• RPA集成     │ │• 部署运维    │
    │• 澄清引擎     │ │• LLM Hub    │ │• 监控告警    │
    └──────────────┘ └──────────────┘ └──────────────┘
```

### 8.2 角色职责

| 角色 | 人数 | 核心职责 |
|-----|------|---------|
| **架构师** | 1 | OpenClaw 架构理解、Intent 层设计、技术决策、代码审查 |
| **Intent 工程师** | 2 | L1/L2/L3 实现、置信度校准、澄清引擎、效果优化 |
| **Agent 工程师** | 2 | Skill 开发、Agent 编排、Prompt 优化 |
| **RPA 工程师** | 1 | 浏览器网格、反检测、RPA 执行器 |
| **Node.js 后端** | 1 | MCP Bridge、OpenClaw 配置扩展 |
| **Python 后端** | 1 | LLM Hub、数据层、API 开发 |
| **DevOps** | 1 | 双栈部署、监控、CI/CD |
| **产品经理** | 1 | 需求梳理、体验验收 |
| **算法工程师** | 1 | L2.5 分类器、效果评估（可选，可 Intent 工程师兼任） |

---

## 9. 风险管控

### 9.1 风险矩阵

| 风险 | 概率 | 影响 | 应对策略 |
|-----|------|------|---------|
| OpenClaw 与 Python 通信延迟 | 中 | 中 | 本地使用 Unix Socket，云端使用 HTTP/2；目标 < 200ms |
| 意图识别准确率不达标 | 中 | 高 | L1 规则持续优化 + L2.5 分类器兜底；每周评估迭代 |
| 平台风控升级导致 RPA 失效 | 高 | 高 | 持续投入反检测技术；保持 API 发布能力作为降级方案 |
| LLM 成本超预算 | 中 | 中 | 规则层拦截 85%+ 闲聊；DeepSeek 作为主要模型 |
| 冷启动用户误判率高 | 中 | 中 | 全局热模式 + 先验概率；新用户引导优化 |
| Node.js 团队不熟悉 | 低 | 低 | 仅修改配置层，不动核心逻辑；提供详细文档 |

### 9.2 应急预案

| 场景 | 应急措施 |
|-----|---------|
| Intent Engine 故障 | 降级到 L1 规则层，所有请求走 LLM 兜底 |
| Python 层故障 | OpenClaw 返回友好提示，引导用户稍后重试 |
| LLM 服务故障 | 切换到备用 Provider，或返回预设回复模板 |
| RPA 大规模失效 | 切换到 API 发布模式，或引导用户手动发布 |
| 数据库故障 | 启用只读模式，返回缓存数据 |

---

## 10. 附录

### 10.1 术语表

| 术语 | 定义 |
|-----|------|
| **OpenClaw** | Node.js 原生 Agent 框架，提供 Gateway、Agent Runtime、Session 管理 |
| **MCP** | Model Context Protocol，连接 Node.js 与 Python 的通信协议 |
| **Intent** | 用户意图，分为 marketing（营销）、casual（闲聊）、ambiguous（模糊） |
| **Skill** | Python 实现的 MCP Server，封装原子业务能力 |
| **Agent** | 业务概念，由一个或多个 Skill 组成，模拟特定角色 |
| **RPA** | Robotic Process Automation，无头浏览器自动化 |
| **SOP** | Standard Operating Procedure，标准运营流程 |

### 10.2 参考文档

- [OpenClaw GitHub](https://github.com/openclaw/openclaw)
- [MCP 官方文档](https://modelcontextprotocol.io/)
- [FastMCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- 产品方案 V4: `AI营销助手产品方案V4.md`
- Intent 层方案: `工业级intent层.txt`

### 10.3 变更日志

| 版本 | 日期 | 变更内容 |
|-----|------|---------|
| V1.0 | 2026-03-28 | 初始版本，OpenClaw 扩展架构 |
| V2.0 | 2026-03-29 | 整合 Intent 层方案，强化意图识别 |
| V3.0 | 2026-03-30 | 整合产品方案 V4，完善 Agent 集群设计 |

---

**本文档整合了产品方案、工业级 Intent 层方案与 OpenClaw 架构，形成完整的开发路线图。核心创新点：**

1. **四级意图识别**：L1 规则 + L2 记忆 + L2.5 分类器 + L3 LLM，准确率 > 95%
2. **双模式 Agent 集群**：单账号 6 Agent + 矩阵 6 Agent，共享通用 Skill
3. **成本优化**：规则层拦截 85%+ 闲聊，整体降本 60%
4. **渐进交付**：16 周分 7 阶段，先单账号深度，后矩阵规模

*最后更新：2026-03-30*
