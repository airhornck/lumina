以下是基于 **四层架构**（OpenClaw 基座 + 多 Agent 中枢 + **MCP Skill Hub** + 双库体系）的完整详细开发计划：

```markdown
# AI 营销助手开发计划（OpenClaw + MCP Skill Hub 架构 V3.0）

> 架构策略：OpenClaw 基座（Node.js）→ 多 Agent 中枢（Python 编排）→ **MCP Skill Hub（Python 执行）** → 双库体系（知识层）
> 核心壁垒：垂直 SOP 编排 + 多 Agent 协作 + **原子化 Skill 体系** + 可扩展双库
> 版本：V3.0  
> 日期：2026-03-29

---

## 📋 目录

1. [四层架构概览](#1-四层架构概览)
2. [核心壁垒设计](#2-核心壁垒设计)
3. [技术架构详解](#3-技术架构详解)
4. [双库体系设计（可扩展配置化）](#4-双库体系设计可扩展配置化)
5. [MCP Skill Hub 层详细设计（执行层）](#5-mcp-skill-hub-层详细设计执行层)
6. [开发阶段规划（14 周）](#6-开发阶段规划14-周)
7. [OpenClaw 基座层（寄生策略）](#7-openclaw-基座层寄生策略)
8. [多 Agent 中枢层（编排层）](#8-多-agent-中枢层编排层)
9. [数据飞轮与进化机制](#9-数据飞轮与进化机制)
10. [里程碑与交付物](#10-里程碑与交付物)

---

## 1. 四层架构概览

### 1.1 清晰的分层边界与职责

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 4: 双库体系（知识资产层）★ 可扩展配置化 ★                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │
│  │  方法论库    │ │  平台规范库  │ │  用户策略记忆│                 │
│  │(AIDA/定位/增长│ │(小红书/抖音 │ │(效果数据驱动│                 │
│  │ 黑客等可配置) │ │ /B站可配置) │ │  进化)       │                 │
│  └──────────────┘ └──────────────┘ └──────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ 被加载使用
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: MCP Skill Hub（原子能力执行层）★ FastMCP 实现 ★          │
│  ┌──────────────┬──────────────┬──────────────┬──────────────────┐  │
│  │   诊断类      │   内容类      │   资产类      │      工具类      │  │
│  ├──────────────┼──────────────┼──────────────┼──────────────────┤  │
│  │•账号诊断Skill │ │•文案生成Skill│ │•方法论检索   │ │•行业新闻抓取   │  │
│  │(带基因分析)   │ │(带DNA转换)  │ │  Skill      │ │  Skill        │  │
│  │•流量分析Skill │ │•脚本创作Skill│ │•案例匹配     │ │•竞品监测Skill │  │
│  │•风险评估Skill │ │•选题生成Skill│ │•知识库问答   │ │•数据可视化    │  │
│  │              │ │(跨平台适配)  │ │  Skill      │ │  Skill        │  │
│  └──────────────┴──────────────┴──────────────┴──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↑ 被编排调用（通过 MCP Protocol）
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: 多 Agent 中枢（编排决策层）★ Python ★                    │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  SOP 编排引擎（DAG 执行器）                                      │ │
│  │  • 加载方法论 → 编译为 DAG → 调度 Agent → 调用 Skill Hub       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  多 Agent 协作系统（Blackboard 架构）                             │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │ │
│  │  │ 诊断Agent│→│ 策略Agent│→│ 创意Agent│→│ 审核Agent│         │ │
│  │  │          │  │(加载方法  │  │(调用内容类│  │(模拟对抗  │         │ │
│  │  │          │  │ 论库)     │  │  Skill)   │  │ 审核)     │         │ │
│  │  └──────────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘         │ │
│  │                     │             │             │               │ │
│  │                     └──────── 辩论优化 ←────────┘               │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ MCP Protocol (SSE/HTTP)
┌──────────────────────────────┼──────────────────────────────────────┐
│  Layer 1: OpenClaw 基座（Node.js - 仅做宿主）                        │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Gateway（原封不动使用）                                         │ │
│  │  • WebSocket 端口 18789 • Session 状态机 • ReAct 循环           │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  MCP Bridge（Node.js 唯一扩展）                                   │ │
│  │  • 注册为 Tool：marketing_intelligence_hub                        │ │
│  │  • 转发到 Python 中枢（携带 user_id, session, 原始输入）         │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 各层核心职责

| 层级 | 核心职责 | 技术实现 | 壁垒性 |
|------|---------|----------|--------|
| **Layer 4** | 知识存储与进化 | YAML + PostgreSQL | 时间积累 |
| **Layer 3** | 原子能力执行 | FastMCP Skills | 垂直深度 |
| **Layer 2** | 策略编排与决策 | 多 Agent + DAG | 智能壁垒 |
| **Layer 1** | 对话交互基座 | OpenClaw Node.js | 基础能力 |

---

## 2. 核心壁垒设计

### 2.1 壁垒一：可扩展双库体系（配置化非硬编码）

**方法论库（Methodology Library）**：AIDA、定位理论、增长黑客等编码为 YAML，可热更新
**平台规范库（Platform Library）**：小红书/抖音/B站的内容 DNA、审核规则、算法偏好配置化

### 2.2 壁垒二：多 Agent 编排 + Skill Hub 分离

- **中枢层（Orchestration）**：决定"做什么"（策略选择、流程编排、Agent 协作）
- **Skill Hub 层（Execution）**：决定"怎么做"（原子能力执行、工具调用、内容生成）

### 2.3 壁垒三：数据飞轮驱动进化

Skill 执行效果 → 回流到双库 → 优化方法论参数 / 平台策略

---

## 3. 技术架构详解

### 3.1 Layer 1: OpenClaw 基座（Node.js）

**零侵入策略**：仅 Fork 使用，只改配置，不改代码。

```javascript
// vendor/openclaw/config/skills/marketing-hub.js （唯一修改点）
module.exports = {
  name: "marketing_intelligence_hub",
  description: "营销智能中枢入口",
  
  async execute(params, context) {
    // 转发到 Python 中枢，后续所有逻辑在 Python 处理
    return await mcpClient.callTool({
      name: "marketing_orchestra",
      arguments: {
        user_input: params.text,
        user_id: context.session.user_id,
        session_history: context.session.messages.slice(-5)
      }
    });
  }
};
```

### 3.2 Layer 2: 多 Agent 中枢（Python 编排层）

**职责**：SOP 编排、Agent 协作、加载双库、决策调用哪个 Skill。

```python
# apps/orchestra/orchestra.py
class MarketingOrchestra:
    """营销智能中枢 - 编排层"""
    
    def __init__(self):
        self.methodology_lib = MethodologyRegistry()
        self.platform_lib = PlatformRegistry()
        self.skill_hub_client = SkillHubClient()  # 调用 Layer 3
        
    async def process(self, user_input, context):
        # 1. 意图识别 → 选择 SOP 或动态规划
        intent = self.classify_intent(user_input)
        
        if intent.sop_id:
            # 固定 SOP 模式：加载方法论 → 编译 DAG → 执行
            return await self.run_sop(intent.sop_id, context)
        else:
            # 动态模式：Planner Agent 实时规划
            return await self.run_dynamic_planning(user_input, context)
    
    async def run_sop(self, sop_id, context):
        # 加载方法论配置
        methodology = self.methodology_lib.load(sop_id)
        platform_spec = self.platform_lib.load(context.platform)
        
        # 编译为执行图
        dag = SOPEngine.compile(methodology, platform_spec)
        
        # 执行：Agent 协作调用 Skill Hub
        results = {}
        for node in dag:
            agent = self.get_agent(node.agent_role)  # 诊断/策略/创意/审核
            # Agent 决定调用哪个 Skill，并处理辩论
            result = await agent.execute(node, context, self.skill_hub_client)
            results[node.id] = result
            
        return results
```

### 3.3 Layer 3: MCP Skill Hub（Python FastMCP 执行层）

**职责**：原子能力实现，四类 Skill，无状态执行，被中枢层调用。

```python
# apps/skill-hub/main.py
from fastmcp import FastMCP

mcp = FastMCP("marketing_skill_hub")

# 诊断类 Skill
@mcp.tool()
async def diagnose_account(account_url: str, platform: str, user_id: str) -> dict:
    """账号基因诊断 Skill"""
    pass

@mcp.tool()
async def analyze_traffic(metrics: dict, user_id: str) -> dict:
    """流量分析 Skill"""
    pass

# 内容类 Skill
@mcp.tool()
async def generate_text(topic: str, platform: str, content_dna: dict) -> dict:
    """文案生成 Skill（带平台 DNA 适配）"""
    pass

@mcp.tool()
async def generate_script(hook_type: str, duration: int, platform: str) -> dict:
    """脚本创作 Skill"""
    pass

# 资产类 Skill
@mcp.tool()
async def retrieve_methodology(query: str, industry: str) -> dict:
    """方法论检索 Skill"""
    pass

@mcp.tool()
async def match_cases(content_type: str, industry: str, limit: int = 5) -> dict:
    """案例匹配 Skill"""
    pass

# 工具类 Skill
@mcp.tool()
async def fetch_industry_news(category: str, days: int = 3) -> dict:
    """行业新闻抓取 Skill"""
    pass

@mcp.tool()
async def monitor_competitor(account_id: str, platform: str) -> dict:
    """竞品监测 Skill"""
    pass

if __name__ == "__main__":
    mcp.run(transport="sse")
```

---

## 4. 双库体系设计（可扩展配置化）

### 4.1 方法论库（YAML 配置）

```yaml
# data/methodologies/aida_advanced.yml
methodology_id: "aida_advanced"
name: "AIDA 增强版"
steps:
  - step_id: "attention"
    theory: "zeigarnik_effect"
    # 指定使用哪个 Skill
    skill_call: 
      name: "generate_text"
      params:
        element: "hook"
        intensity: "high"
        
  - step_id: "desire"
    theory: "social_proof"
    skill_call:
      name: "match_cases"  # 调用资产类 Skill 匹配案例
      params:
        case_type: "social_proof"
```

### 4.2 平台规范库（YAML 配置）

```yaml
# data/platforms/xiaohongshu_v2024.yml
platform_id: "xiaohongshu"
content_dna:
  - element: "hook_position"
    value: "0-3s"
    # 指定使用哪个 Skill 来检查
    validation_skill: "validate_hook_timing"
    
audit_rules:
  - category: "medical"
    forbidden_terms: ["疗效", "治疗"]
    # 指定使用哪个 Skill 来审核
    audit_skill: "check_medical_compliance"
```

### 4.3 双库加载机制

```python
# packages/knowledge-base/methodology_registry.py
class MethodologyRegistry:
    """方法论库管理器 - 支持热加载"""
    
    def __init__(self, data_dir="data/methodologies"):
        self.data_dir = Path(data_dir)
        self._cache = {}
        
    def load(self, methodology_id: str) -> Methodology:
        """加载指定方法论"""
        if methodology_id not in self._cache:
            yaml_path = self.data_dir / f"{methodology_id}.yml"
            config = yaml.safe_load(yaml_path.read_text())
            self._cache[methodology_id] = Methodology.from_config(config)
        return self._cache[methodology_id]

# packages/knowledge-base/platform_registry.py
class PlatformRegistry:
    """平台规范库管理器"""
    
    def load(self, platform_id: str) -> PlatformSpec:
        """加载平台规范"""
        yaml_path = self.data_dir / f"{platform_id}_v2024.yml"
        return PlatformSpec.from_yaml(yaml_path)
```

---

## 5. MCP Skill Hub 层详细设计（执行层）

### 5.1 Skill 分类与职责矩阵

| 分类 | Skill 名称 | 输入 | 输出 | 依赖双库 | 对应 Agent |
|------|-----------|------|------|----------|-----------|
| **诊断类** | `diagnose_account` | 账号 URL、平台 | 基因诊断报告、问题清单 | 平台规范库（审核规则） | 诊断 Agent |
| **诊断类** | `analyze_traffic` | 流量数据 | 漏斗分析、下降归因 | 方法论库（AIDA 漏斗） | 诊断 Agent |
| **诊断类** | `detect_risk` | 内容文本 | 风险项、修改建议 | 平台规范库（敏感词） | 诊断 Agent |
| **内容类** | `generate_text` | 主题、平台、DNA | 文案、标题、标签 | 平台规范库（DNA 规范）、方法论库（钩子理论） | 创意 Agent |
| **内容类** | `generate_script` | 钩子类型、时长 | 分镜脚本、口播稿 | 平台规范库（时长规范） | 创意 Agent |
| **内容类** | `select_topic` | 行业、热点 | 选题列表、优先级 | 资产类 Skill（新闻检索） | 策略 Agent |
| **资产类** | `retrieve_methodology` | 查询词、行业 | 方法论步骤、Prompt | 方法论库（YAML 配置） | 策略 Agent |
| **资产类** | `match_cases` | 内容类型、行业 | 匹配案例、参考链接 | 案例数据库 | 策略 Agent |
| **资产类** | `qa_knowledge` | 问题 | 知识库答案 | 向量数据库 | 全 Agent |
| **工具类** | `fetch_industry_news` | 分类、天数 | 新闻列表、热度分 | 爬虫/API | 策略 Agent |
| **工具类** | `monitor_competitor` | 竞品账号 | 竞品动态、差距分析 | 爬虫/数据库 | 诊断 Agent |
| **工具类** | `visualize_data` | 数据、图表类型 | 可视化图片/链接 | 图表库 | 诊断 Agent |

### 5.2 Skill 详细接口定义（FastMCP）

#### 5.2.1 诊断类 Skills

**Skill: diagnose_account**
```python
# skills/skill-account-diagnosis/src/main.py
from fastmcp import FastMCP
from pydantic import BaseModel, Field

mcp = FastMCP("account_diagnosis")

class AccountDiagnosisInput(BaseModel):
    account_url: str = Field(description="账号主页链接")
    platform: str = Field(enum=["xiaohongshu", "douyin", "bilibili"])
    user_id: str = Field(description="用于数据隔离")
    analysis_depth: str = Field(default="standard", enum=["quick", "standard", "deep"])

class AccountDiagnosisOutput(BaseModel):
    account_gene: dict = Field(description="账号基因：内容类型、风格标签、受众画像")
    health_score: float = Field(ge=0, le=100)
    key_issues: list[str]
    improvement_suggestions: list[dict]
    recommended_methodology: str = Field(description="建议使用的营销方法论ID")

@mcp.tool()
async def diagnose_account(args: AccountDiagnosisInput) -> AccountDiagnosisOutput:
    """
    账号基因诊断 Skill - 分析账号内容DNA、识别问题、推荐方法论
    """
    # 1. 爬取账号近期内容（调用内部爬虫）
    contents = await crawl_account(args.account_url, args.platform)
    
    # 2. 内容DNA分析（标签提取、风格识别）
    gene_analysis = await analyze_content_dna(contents)
    
    # 3. 健康度评分（根据平台规范库的标准）
    platform_spec = load_platform_spec(args.platform)
    health_score = calculate_health_score(gene_analysis, platform_spec)
    
    # 4. 问题识别（流量漏斗诊断）
    issues = identify_issues(gene_analysis, health_score)
    
    # 5. 推荐方法论（根据行业和内容类型）
    recommended_method = match_methodology(gene_analysis.industry, issues)
    
    return AccountDiagnosisOutput(
        account_gene=gene_analysis,
        health_score=health_score,
        key_issues=issues,
        improvement_suggestions=generate_suggestions(issues, platform_spec),
        recommended_methodology=recommended_method
    )
```

**Skill: analyze_traffic**
```python
class TrafficAnalysisInput(BaseModel):
    metrics: dict = Field(description="流量数据：{views: int, likes: int, shares: int, ...}")
    user_id: str
    platform: str
    time_range: str = Field(default="7d", enum=["7d", "30d", "90d"])

class TrafficAnalysisOutput(BaseModel):
    funnel_analysis: dict = Field(description="曝光→点击→互动→转化漏斗")
    drop_off_points: list[str]
    trend: str = Field(enum=["up", "stable", "down", "volatile"])
    anomaly_detection: list[dict]
    actionable_insights: list[str]

@mcp.tool()
async def analyze_traffic(args: TrafficAnalysisInput) -> TrafficAnalysisOutput:
    """流量分析 Skill - 漏斗分析、异常检测、趋势判断"""
    pass
```

**Skill: detect_risk**
```python
class RiskDetectionInput(BaseModel):
    content_text: str
    platform: str
    content_type: str = Field(enum=["post", "script", "comment"])

class RiskDetectionOutput(BaseModel):
    risk_level: str = Field(enum=["low", "medium", "high", "critical"])
    risk_categories: list[str] = Field(description=["medical", "comparison", "sensitive", "copyright"])
    flagged_terms: list[dict]
    suggestions: list[str]
    alternative_phrases: dict

@mcp.tool()
async def detect_risk(args: RiskDetectionInput) -> RiskDetectionOutput:
    """风险评估 Skill - 基于平台规范库的审核规则检测"""
    # 加载平台审核规则
    audit_rules = load_platform_audit_rules(args.platform)
    
    # 多维度风险扫描
    risks = []
    for rule in audit_rules:
        matches = scan_content(args.content_text, rule)
        if matches:
            risks.append({
                "category": rule.category,
                "severity": rule.severity,
                "matches": matches
            })
    
    return RiskDetectionOutput(
        risk_level=calculate_overall_risk(risks),
        risk_categories=[r["category"] for r in risks],
        flagged_terms=extract_flagged_terms(risks),
        suggestions=generate_fix_suggestions(risks),
        alternative_phrases=get_alternative_phrases(risks)
    )
```

#### 5.2.2 内容类 Skills

**Skill: generate_text**
```python
class TextGenerationInput(BaseModel):
    topic: str = Field(description="内容主题")
    platform: str = Field(enum=["xiaohongshu", "douyin", "bilibili", "wechat"])
    content_dna: dict = Field(description="来自平台规范库的内容DNA参数")
    methodology_hint: str = Field(description="应用的方法论（如AIDA）")
    user_id: str
    constraints: dict = Field(default={}, description="额外约束：字数、风格等")

class TextGenerationOutput(BaseModel):
    title: str
    content: str
    hashtags: list[str]
    hook_analysis: dict = Field(description="钩子类型、位置、强度分析")
    platform_optimization: dict = Field(description="针对特定平台的优化点")

@mcp.tool()
async def generate_text(args: TextGenerationInput) -> TextGenerationOutput:
    """
    文案生成 Skill - 带平台DNA适配和方法论应用
    """
    # 1. 加载平台规范（DNA参数验证）
    platform_spec = load_platform_spec(args.platform)
    dna = validate_and_enhance_dna(args.content_dna, platform_spec)
    
    # 2. 加载方法论Prompt
    methodology_prompt = load_methodology_prompt(args.methodology_hint)
    
    # 3. 构造生成Prompt（融合方法论+平台DNA）
    prompt = build_generation_prompt(
        topic=args.topic,
        methodology=methodology_prompt,
        dna=dna,
        constraints=args.constraints
    )
    
    # 4. 调用LLM生成
    llm = get_client(skill_name="text_generator")
    raw_content = await llm.complete(prompt)
    
    # 5. 后处理（标签提取、格式调整）
    result = post_process_content(raw_content, args.platform)
    
    return TextGenerationOutput(
        title=result.title,
        content=result.content,
        hashtags=result.hashtags,
        hook_analysis=analyze_hook(result.content, dna),
        platform_optimization=get_optimization_tips(result, platform_spec)
    )
```

**Skill: generate_script**
```python
class ScriptGenerationInput(BaseModel):
    topic: str
    hook_type: str = Field(enum=["suspense", "fear", "curiosity", "empathy", "authority"])
    duration: int = Field(description="时长秒数", ge=15, le=300)
    platform: str
    visual_elements: list[str] = Field(default=[], description="需要的视觉元素")
    user_id: str

class ScriptGenerationOutput(BaseModel):
    hook_script: str = Field(description="黄金3秒钩子文案")
    full_script: str
    shot_list: list[dict] = Field(description="分镜列表：{timestamp, visual, audio, text}")
    bgm_suggestion: str
    caption_highlights: list[str]

@mcp.tool()
async def generate_script(args: ScriptGenerationInput) -> ScriptGenerationOutput:
    """脚本创作 Skill - 分镜脚本生成，适配平台时长规范"""
    pass
```

**Skill: select_topic**
```python
class TopicSelectionInput(BaseModel):
    industry: str
    account_stage: str = Field(enum=["cold_start", "growth", "mature"])
    hot_topics: list[str] = Field(default=[], description="当前热点列表")
    user_id: str
    platform: str

class TopicSelectionOutput(BaseModel):
    recommended_topics: list[dict] = Field(description="[{topic, score, reason, methodology}]")
    content_calendar: list[dict] = Field(description="发布日历建议")
    trend_analysis: str

@mcp.tool()
async def select_topic(args: TopicSelectionInput) -> TopicSelectionOutput:
    """选题生成 Skill - 结合热点、账号阶段、方法论"""
    # 1. 获取行业新闻（调用工具类Skill）
    news = await fetch_industry_news(args.industry, days=3)
    
    # 2. 热点匹配度分析
    matched_topics = match_hot_topics(news, args.hot_topics)
    
    # 3. 根据账号阶段筛选（冷启动vs增长期策略不同）
    suitable_topics = filter_by_stage(matched_topics, args.account_stage)
    
    # 4. 方法论适配（某些话题更适合AIDA，某些适合故事化）
    topics_with_methodology = assign_methodology(suitable_topics)
    
    return TopicSelectionOutput(
        recommended_topics=topics_with_methodology,
        content_calendar=generate_calendar(topics_with_methodology),
        trend_analysis=summarize_trends(news)
    )
```

#### 5.2.3 资产类 Skills

**Skill: retrieve_methodology**
```python
class MethodologyRetrievalInput(BaseModel):
    query: str
    industry: str
    goal: str = Field(enum=["conversion", "awareness", "retention"])
    user_id: str

class MethodologyRetrievalOutput(BaseModel):
    methodology_id: str
    name: str
    steps: list[dict]
    prompt_templates: dict
    success_cases: list[str]
    applicable_scenarios: list[str]

@mcp.tool()
async def retrieve_methodology(args: MethodologyRetrievalInput) -> MethodologyRetrievalOutput:
    """
    方法论检索 Skill - 从方法论库加载配置并实例化为可执行步骤
    """
    # 从YAML库加载
    methodology = load_methodology_from_yaml(args.industry, args.goal)
    
    # 根据查询词匹配最适方法论
    best_match = match_methodology(args.query, methodology)
    
    return MethodologyRetrievalOutput(
        methodology_id=best_match.id,
        name=best_match.name,
        steps=best_match.steps,
        prompt_templates=best_match.prompt_templates,
        success_cases=best_match.case_studies,
        applicable_scenarios=best_match.applicable_scenarios
    )
```

**Skill: match_cases**
```python
class CaseMatchingInput(BaseModel):
    content_type: str
    industry: str
    target_metrics: dict = Field(description="目标指标：{ctr: float, save_rate: float}")
    limit: int = Field(default=5, ge=1, le=10)
    user_id: str

class CaseMatchingOutput(BaseModel):
    matched_cases: list[dict] = Field(description="[{case_id, title, similarity_score, key_success_factors}]")
    pattern_analysis: str
    actionable_takeaways: list[str]

@mcp.tool()
async def match_cases(args: CaseMatchingInput) -> CaseMatchingOutput:
    """案例匹配 Skill - 向量检索相似成功案例"""
    pass
```

**Skill: qa_knowledge**
```python
class KnowledgeQAInput(BaseModel):
    question: str
    knowledge_domain: str = Field(enum=["methodology", "platform_rules", "industry_trend"])
    user_id: str

class KnowledgeQAOutput(BaseModel):
    answer: str
    sources: list[str]
    confidence: float
    related_methodologies: list[str]

@mcp.tool()
async def qa_knowledge(args: KnowledgeQAInput) -> KnowledgeQAOutput:
    """知识库问答 Skill - RAG检索"""
    pass
```

#### 5.2.4 工具类 Skills

**Skill: fetch_industry_news**
```python
class IndustryNewsInput(BaseModel):
    category: str = Field(enum=["beauty", "3c", "food", "fashion", "general"])
    days: int = Field(default=3, ge=1, le=7)
    sources: list[str] = Field(default=["weibo", "zhihu", "36kr"])

class IndustryNewsOutput(BaseModel):
    news_list: list[dict] = Field(description="[{title, summary, heat_score, source, url}]")
    hot_keywords: list[str]
    trend_prediction: str

@mcp.tool()
async def fetch_industry_news(args: IndustryNewsInput) -> IndustryNewsOutput:
    """行业新闻抓取 Skill - 多源聚合"""
    pass
```

**Skill: monitor_competitor**
```python
class CompetitorMonitorInput(BaseModel):
    account_id: str
    platform: str
    monitor_metrics: list[str] = Field(default=["content", "fans", "engagement"])
    user_id: str

class CompetitorMonitorOutput(BaseModel):
    latest_contents: list[dict]
    performance_comparison: dict
    content_gap_analysis: str
    threat_level: str

@mcp.tool()
async def monitor_competitor(args: CompetitorMonitorInput) -> CompetitorMonitorOutput:
    """竞品监测 Skill - 竞品动态追踪与差距分析"""
    pass
```

**Skill: visualize_data**
```python
class DataVisualizationInput(BaseModel):
    data: dict
    chart_type: str = Field(enum=["line", "bar", "pie", "funnel", "heatmap"])
    title: str
    user_id: str

class DataVisualizationOutput(BaseModel):
    chart_url: str
    insights: list[str]
    recommendations: list[str]

@mcp.tool()
async def visualize_data(args: DataVisualizationInput) -> DataVisualizationOutput:
    """数据可视化 Skill - 自动生成图表并解读"""
    pass
```

### 5.3 Skill Hub 统一入口与注册

```python
# apps/skill-hub/main.py
from fastmcp import FastMCP
import importlib

mcp = FastMCP("marketing_skill_hub")

# 动态注册所有 Skills
skills_modules = [
    "skills.diagnosis.account_diagnosis",
    "skills.diagnosis.traffic_analysis",
    "skills.diagnosis.risk_detection",
    "skills.content.text_generator",
    "skills.content.script_generator",
    "skills.content.topic_selector",
    "skills.asset.methodology_retrieval",
    "skills.asset.case_matcher",
    "skills.asset.knowledge_qa",
    "skills.tool.industry_news",
    "skills.tool.competitor_monitor",
    "skills.tool.data_visualizer"
]

def register_skills():
    for module_path in skills_modules:
        module = importlib.import_module(module_path)
        if hasattr(module, 'mcp'):
            # 将模块的 tools 注册到主 mcp
            for tool_name, tool_func in module.mcp._tools.items():
                mcp._tools[tool_name] = tool_func

if __name__ == "__main__":
    register_skills()
    mcp.run(transport="sse")  # Server-Sent Events 供中枢层连接
```

### 5.4 Skill 开发规范

每个 Skill 独立目录结构：
```
skills/skill-{name}/
├── SKILL.md                    # OpenClaw 风格定义（元信息）
├── pyproject.toml              # 依赖管理
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastMCP Tool 定义
│   ├── models.py               # Pydantic 模型
│   └── utils.py                # 工具函数
├── tests/
│   └── test_skill.py
└── Dockerfile                  # 可选：独立部署
```

---

## 6. 开发阶段规划（14 周）

### 6.1 总体时间线

```
Week 1-2:   Layer 1 - OpenClaw 寄生基座 + Bridge
Week 3-4:   Layer 2 - 多 Agent 中枢骨架（编排层）
Week 5-8:   Layer 3 - MCP Skill Hub（执行层）+ Layer 4 - 双库填充
Week 9-12:  集成测试 + 数据飞轮 + 进化机制
Week 13-14: 生产部署 + 壁垒固化
```

### 6.2 详细任务分解

#### Phase 1: 基座层（Week 1-2）

**目标**：让 OpenClaw 成为宿主，零侵入改造。

| 任务 | 负责人 | 输出物 |
|------|--------|--------|
| 1.1 | Fork OpenClaw 官方仓库 | 架构师 | `vendor/openclaw/` |
| 1.2 | 开发 MCP Bridge（Node.js） | Node.js 工程师 | `packages/mcp-bridge/index.js` |
| 1.3 | Python 中枢骨架搭建 | Python 架构师 | `apps/orchestra/main.py` |
| 1.4 | Skill Hub 基础框架 | Python 架构师 | `apps/skill-hub/main.py`（FastMCP 基础） |
| 1.5 | 端到端连通测试 | 全团队 | OpenClaw → Bridge → Orchestra → Skill Hub 通路 |

#### Phase 2: 编排层（Week 3-4）

**目标**：构建多 Agent 架构与双库体系框架。

| 任务 | 负责人 | 输出物 | 关键设计 |
|------|--------|--------|----------|
| 2.1 | Agent 基类与通信 | Python 架构师 | `packages/agent-core/` | Blackboard 架构 |
| 2.2 | SOP 编排引擎（DAG） | Python 架构师 | `packages/sop-engine/` | YAML → 执行图编译器 |
| 2.3 | 双库框架（可加载） | 后端工程师 | `packages/knowledge-base/` | 热加载机制 |
| 2.4 | Skill Hub 客户端 | 后端工程师 | `packages/skill-hub-client/` | 中枢层调用 Skill Hub 的客户端 |
| 2.5 | 中枢→Skill Hub 调用链路 | Python 架构师 | 编排层调用执行层完整链路 | MCP Client 实现 |

#### Phase 3: 执行层 + 知识层（Week 5-8）**核心开发期**

| 周次 | 任务 | 负责人 | 输出物 | 说明 |
|------|------|--------|--------|------|
| 5 | **诊断类 Skill**（3个） | 算法工程师 | `skills/skill-account-diagnosis/`, `skill-traffic-analysis/`, `skill-risk-detection/` | 账号基因分析、流量漏斗、风险扫描 |
| 5 | **资产类 Skill**（2个） | 后端工程师 | `skills/skill-methodology-retrieval/`, `skill-case-matching/` | 方法论检索、案例匹配 |
| 6 | **内容类 Skill**（3个） | 算法工程师 | `skills/skill-text-generator/`, `skill-script-generator/`, `skill-topic-selection/` | 文案生成（带DNA转换）、脚本创作、选题生成 |
| 6 | **工具类 Skill**（2个） | 后端工程师 | `skills/skill-industry-news/`, `skill-competitor-monitor/` | 新闻抓取、竞品监测 |
| 7 | **Skill Hub 集成** | Python 架构师 | `apps/skill-hub/main.py` | FastMCP 统一入口，注册所有 11 个 Skill |
| 7 | **方法论库填充** | 产品经理+算法 | `data/methodologies/aida.yml`, `positioning.yml`, `growth_hacker.yml` | AIDA、定位理论、增长黑客配置化 |
| 8 | **平台库填充** | 运营+产品 | `data/platforms/xiaohongshu_v2024.yml`, `douyin_v2024.yml`, `bilibili_v2024.yml` | 内容DNA、审核规则、算法偏好 |
| 8 | **辩论机制实现** | 算法工程师 | `agents/critic.py`（对抗审核） | 模拟平台审核、竞品攻击场景 |

#### Phase 4: 集成与进化（Week 9-12）

| 任务 | 负责人 | 输出物 |
|------|--------|--------|
| 9.1 | 编排层调用 Skill Hub 集成 | Python 架构师 | 完整 DAG 执行链路（Agent → Skill Hub → 返回） |
| 9.2 | 效果数据回流接口 | 后端工程师 | `api/feedback/` |
| 10.1 | 策略进化引擎 | 算法工程师 | 根据效果自动调参 |
| 11.1 | 端到端测试 | QA | 诊断→策略→创意→审核→回流闭环 |
| 12.1 | 双库加密与防泄露 | 架构师 | YAML 加密存储 |

#### Phase 5: 部署（Week 13-14）

| 任务 | 负责人 | 输出物 |
|------|--------|--------|
| 13.1 | Docker 化（三层容器） | DevOps | `docker-compose.yml`（OpenClaw + Orchestra + Skill Hub） |
| 13.2 | 监控告警 | DevOps | Prometheus + Grafana |
| 14.1 | 生产部署 | 全团队 | 上线运行 |

---

## 7. OpenClaw 基座层（寄生策略）

**原则**：零侵入，仅做对话宿主。

- **不改代码**：只修改 `config/skills/marketing-hub.js` 注册 Bridge
- **不扩状态**：复用 OpenClaw 原生 Session 状态机（IDLE → CLARIFYING → EXECUTING）
- **不替逻辑**：复杂编排下沉到 Python 中枢层

---

## 8. 多 Agent 中枢层（编排层）

### 8.1 核心职责

- **SOP 编排**：加载方法论库 → 编译为 DAG → 调度执行
- **Agent 协作**：诊断 → 策略 → 创意 → 审核 的流水线
- **Skill 调度**：决定调用 Skill Hub 中的哪个具体 Skill
- **辩论机制**：策略 Agent 生成多方案，Critic Agent 对抗审核，循环优化

### 8.2 与 Skill Hub 的调用关系

```python
# 中枢层 Agent 调用 Skill Hub 示例
class CreativeAgent:
    async def generate_content(self, strategy, platform, context):
        # 1. 加载平台规范（从双库）
        platform_spec = self.platform_lib.load(platform)
        
        # 2. 调用 Skill Hub 的内容类 Skill
        result = await self.skill_hub_client.call(
            skill_name="generate_text",
            params={
                "topic": strategy.topic,
                "platform": platform,
                "content_dna": platform_spec.content_dna,  # 注入平台 DNA
                "user_id": context.user_id
            }
        )
        
        # 3. 返回给中枢层继续流转
        return result
```

---

## 9. 数据飞轮与进化机制

### 9.1 三层数据资产

| 数据层 | 内容 | 存储 | 进化机制 |
|--------|------|------|----------|
| **用户策略记忆** | 每个账号的有效策略历史 | PostgreSQL (按 user_id 隔离) | 个性化推荐 |
| **行业基准库** | 跨账号聚合的行业数据 | 独立 Schema | 行业洞察报告 |
| **方法论参数库** | 方法论 YAML 中的参数（如 hook_strength） | YAML + 版本控制 | 根据效果自动调参 |

### 9.2 进化代码示例

```python
# optimization/evolution.py
class MethodologyEvolution:
    async def daily_evolution(self):
        """每日进化循环"""
        # 1. 获取昨日所有执行记录
        executions = await self.get_yesterday_executions()
        
        # 2. 按方法论分组分析效果
        for method_id, group in executions.groupby('methodology_id'):
            avg_ctr = group['ctr'].mean()
            
            # 3. 如果效果低于阈值，调整方法论参数
            if avg_ctr < 0.03:
                config = self.methodology_lib.load(method_id)
                config.steps[0].params['hook_strength'] += 0.1  # 增强钩子
                await self.methodology_lib.update(config)
```

---

## 10. 里程碑与交付物

| 里程碑 | 时间 | 核心交付 | 验证标准 |
|--------|------|---------|----------|
| **M1** | Week 2 | OpenClaw + Bridge | 基座寄生成功 |
| **M2** | Week 4 | 多 Agent 中枢骨架 | 方法论可配置化 |
| **M3** | Week 8 | **11个 MCP Skill + 双库 V1** | 诊断/内容/资产/工具链路完整 |
| **M4** | Week 12 | 数据飞轮运转 | 效果回流自动优化 |
| **GA** | Week 14 | 生产环境 | 三类方法论 + 三平台规范上线 |

---

**总结**：此方案明确区分四层架构——OpenClaw 基座（对话）→ 多 Agent 中枢（编排）→ **MCP Skill Hub（执行，含诊断/内容/资产/工具四类 11 个 Skill）** → 双库体系（知识，可扩展配置化）。开发周期 14 周，构建完整垂直壁垒。
```