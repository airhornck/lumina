"""
Agent 编排器 V3

基于开发计划 V3 重构的 Agent 编排层
支持单账号/矩阵双模式
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal
from enum import Enum


class ExecutionMode(Enum):
    """执行模式"""
    SERIAL = "serial"       # 串行
    PARALLEL = "parallel"   # 并行
    MIXED = "mixed"         # 混合


class AgentMode(Enum):
    """Agent 模式"""
    SINGLE = "single"       # 单账号模式
    MATRIX = "matrix"       # 矩阵模式


@dataclass
class Agent:
    """Agent 定义"""
    id: str
    name: str
    name_en: str
    description: str
    skills: List[str]
    triggers: List[str]
    priority: int = 1
    llm_config: Optional[Dict[str, Any]] = None


@dataclass
class AgentTeam:
    """Agent 小队"""
    agents: List[Agent]
    mode: ExecutionMode
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    execution_time_ms: int = 0
    agent_outputs: Dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    """
    Agent 编排器
    
    根据意图类型自动组建 Agent 小队并执行
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化编排器
        
        Args:
            config_path: Agent 配置文件路径
        """
        self.agents: Dict[str, Agent] = {}
        self.intent_agent_map: Dict[str, List[str]] = {}
        self.execution_modes: Dict[str, ExecutionMode] = {}
        
        # 加载配置
        if config_path:
            self._load_config(config_path)
        else:
            self._load_default_config()
    
    def _load_default_config(self) -> None:
        """加载默认配置"""
        # 单账号 Agent
        self.agents.update({
            "content_strategist": Agent(
                id="content_strategist",
                name="内容策略师",
                name_en="ContentStrategist",
                description="负责账号定位与内容规划",
                skills=["skill-content-strategist"],
                triggers=["strategy", "topic_selection", "positioning"],
                priority=1
            ),
            "creative_studio": Agent(
                id="creative_studio",
                name="创意工厂",
                name_en="CreativeStudio",
                description="负责多模态内容生成",
                skills=["skill-creative-studio"],
                triggers=["content_creation", "script_creation"],
                priority=1
            ),
            "data_analyst": Agent(
                id="data_analyst",
                name="数据分析师",
                name_en="DataAnalyst",
                description="负责数据复盘与诊断",
                skills=["skill-data-analyst"],
                triggers=["diagnosis", "data_analysis", "traffic_analysis"],
                priority=1
            ),
            "growth_hacker": Agent(
                id="growth_hacker",
                name="投放优化师",
                name_en="GrowthHacker",
                description="负责流量获取与优化",
                skills=["skill-growth-hacker"],
                triggers=["growth_strategy"],
                priority=2
            ),
            "community_manager": Agent(
                id="community_manager",
                name="用户运营官",
                name_en="CommunityManager",
                description="负责私域沉淀与互动",
                skills=["skill-community-manager"],
                triggers=["community_management"],
                priority=3
            ),
            "compliance_officer": Agent(
                id="compliance_officer",
                name="合规审查员",
                name_en="ComplianceOfficer",
                description="负责内容安全与风控",
                skills=["skill-compliance-officer"],
                triggers=["risk_check"],
                priority=2
            ),
        })
        
        # 矩阵 Agent
        self.agents.update({
            "matrix_commander": Agent(
                id="matrix_commander",
                name="矩阵指挥官",
                name_en="MatrixCommander",
                description="负责矩阵整体策略规划",
                skills=["skill-matrix-commander"],
                triggers=["matrix_setup", "matrix_strategy"],
                priority=1
            ),
            "bulk_creative": Agent(
                id="bulk_creative",
                name="批量创意工厂",
                name_en="BulkCreative",
                description="负责一稿多改批量生成",
                skills=["skill-bulk-creative", "skill-creative-studio"],
                triggers=["bulk_creation", "content_variation"],
                priority=1
            ),
            "account_keeper": Agent(
                id="account_keeper",
                name="账号维护工",
                name_en="AccountKeeper",
                description="负责多账号登录态维护",
                skills=["skill-account-keeper"],
                triggers=["account_maintenance"],
                priority=2
            ),
            "traffic_broker": Agent(
                id="traffic_broker",
                name="流量互导员",
                name_en="TrafficBroker",
                description="负责矩阵内部流量调度",
                skills=["skill-traffic-broker"],
                triggers=["traffic_routing"],
                priority=2
            ),
        })
        
        # 意图到 Agent 的映射
        self.intent_agent_map = {
            # 单账号意图
            "diagnosis": ["data_analyst", "content_strategist"],
            "content_creation": ["creative_studio", "compliance_officer"],
            "script_creation": ["creative_studio"],
            "strategy": ["content_strategist"],
            "topic_selection": ["content_strategist"],
            "traffic_analysis": ["data_analyst", "growth_hacker"],
            "risk_check": ["compliance_officer"],
            "growth_strategy": ["growth_hacker"],
            "community_management": ["community_manager"],
            
            # 矩阵意图
            "matrix_setup": ["matrix_commander", "account_keeper"],
            "matrix_strategy": ["matrix_commander"],
            "bulk_creation": ["bulk_creative"],
            "content_variation": ["bulk_creative"],
            "traffic_routing": ["traffic_broker"],
            "account_maintenance": ["account_keeper"],
        }
        
        # 执行模式配置
        self.execution_modes = {
            "diagnosis": ExecutionMode.PARALLEL,
            "traffic_analysis": ExecutionMode.PARALLEL,
            "content_creation": ExecutionMode.SERIAL,
            "script_creation": ExecutionMode.SERIAL,
            "matrix_setup": ExecutionMode.MIXED,
        }
    
    def _load_config(self, config_path: str) -> None:
        """从文件加载配置"""
        import yaml
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 加载 Agent 定义
        for agent_id, agent_data in config.get('single_account_agents', {}).items():
            self.agents[agent_id] = Agent(
                id=agent_id,
                name=agent_data['name'],
                name_en=agent_data['name_en'],
                description=agent_data['description'],
                skills=agent_data['skills'],
                triggers=agent_data['triggers'],
                priority=agent_data.get('priority', 1),
                llm_config=agent_data.get('llm_config')
            )
        
        for agent_id, agent_data in config.get('matrix_agents', {}).items():
            self.agents[agent_id] = Agent(
                id=agent_id,
                name=agent_data['name'],
                name_en=agent_data['name_en'],
                description=agent_data['description'],
                skills=agent_data['skills'],
                triggers=agent_data['triggers'],
                priority=agent_data.get('priority', 1),
                llm_config=agent_data.get('llm_config')
            )
        
        # 加载映射关系
        self.intent_agent_map = config.get('orchestration', {}).get('intent_agent_map', {})
    
    def orchestrate(
        self,
        intent_type: str,
        intent_subtype: Optional[str],
        user_id: str,
        mode: AgentMode = AgentMode.SINGLE,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentTeam:
        """
        组建 Agent 小队
        
        Args:
            intent_type: 意图类型
            intent_subtype: 意图子类型
            user_id: 用户ID
            mode: 单账号/矩阵模式
            context: 上下文
        
        Returns:
            Agent 小队
        """
        # 确定要使用的意图键
        intent_key = intent_subtype or intent_type
        
        # 获取 Agent ID 列表
        agent_ids = self.intent_agent_map.get(intent_key, [])
        
        # 如果子类型未匹配，尝试主类型
        if not agent_ids and intent_subtype:
            agent_ids = self.intent_agent_map.get(intent_type, [])
        
        # 默认使用通用 Agent
        if not agent_ids:
            if mode == AgentMode.MATRIX:
                agent_ids = ["matrix_commander"]
            else:
                agent_ids = ["content_strategist"]
        
        # 获取 Agent 实例
        team_agents = [self.agents[aid] for aid in agent_ids if aid in self.agents]
        
        # 按优先级排序
        team_agents.sort(key=lambda a: a.priority)
        
        # 确定执行模式
        execution_mode = self.execution_modes.get(
            intent_key,
            ExecutionMode.SERIAL
        )
        
        return AgentTeam(
            agents=team_agents,
            mode=execution_mode,
            context=context or {}
        )
    
    async def execute_team(
        self,
        team: AgentTeam,
        user_input: str,
        context: Dict[str, Any]
    ) -> ExecutionResult:
        """
        执行 Agent 小队
        
        Args:
            team: Agent 小队
            user_input: 用户输入
            context: 上下文
        
        Returns:
            执行结果
        """
        import time
        start_time = time.time()
        
        result = ExecutionResult(success=True)
        
        try:
            if team.mode == ExecutionMode.PARALLEL:
                # 并行执行
                tasks = [
                    self._execute_agent(agent, user_input, context)
                    for agent in team.agents
                ]
                agent_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for agent, agent_result in zip(team.agents, agent_results):
                    if isinstance(agent_result, Exception):
                        result.errors.append(f"{agent.id}: {str(agent_result)}")
                    else:
                        result.agent_outputs[agent.id] = agent_result
                
                result.success = len(result.errors) < len(team.agents)
                
            elif team.mode == ExecutionMode.SERIAL:
                # 串行执行
                accumulated_context = dict(context)
                
                for agent in team.agents:
                    try:
                        agent_result = await self._execute_agent(
                            agent, user_input, accumulated_context
                        )
                        result.agent_outputs[agent.id] = agent_result
                        accumulated_context.update(agent_result)
                    except Exception as e:
                        result.errors.append(f"{agent.id}: {str(e)}")
                        result.success = False
                        break
                
                if not result.errors:
                    result.success = True
                    
            else:  # MIXED
                # 混合模式：部分并行，部分串行
                result = await self._execute_mixed(team, user_input, context)
            
            # 汇总结果
            result.results = self._aggregate_results(result.agent_outputs)
            
        except Exception as e:
            result.success = False
            result.errors.append(str(e))
        
        result.execution_time_ms = int((time.time() - start_time) * 1000)
        return result
    
    async def _execute_agent(
        self,
        agent: Agent,
        user_input: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行单个 Agent"""
        # 这里调用具体的 Skill
        # 实际实现会通过 MCP 调用 Python Skill
        
        return {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "skills": agent.skills,
            "status": "executed",
            "context_keys": list(context.keys())
        }
    
    async def _execute_mixed(
        self,
        team: AgentTeam,
        user_input: str,
        context: Dict[str, Any]
    ) -> ExecutionResult:
        """混合模式执行"""
        # 示例：先并行执行一批，再串行执行一批
        result = ExecutionResult(success=True)
        
        # 第一阶段：并行执行高优先级 Agent
        priority_agents = [a for a in team.agents if a.priority == 1]
        if priority_agents:
            tasks = [
                self._execute_agent(agent, user_input, context)
                for agent in priority_agents
            ]
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for agent, res in zip(priority_agents, parallel_results):
                if isinstance(res, Exception):
                    result.errors.append(f"{agent.id}: {str(res)}")
                else:
                    result.agent_outputs[agent.id] = res
        
        # 第二阶段：串行执行低优先级 Agent
        secondary_agents = [a for a in team.agents if a.priority > 1]
        accumulated = dict(context)
        accumulated.update(result.agent_outputs)
        
        for agent in secondary_agents:
            try:
                agent_result = await self._execute_agent(agent, user_input, accumulated)
                result.agent_outputs[agent.id] = agent_result
                accumulated.update(agent_result)
            except Exception as e:
                result.errors.append(f"{agent.id}: {str(e)}")
        
        result.success = len(result.errors) < len(team.agents)
        return result
    
    def _aggregate_results(self, agent_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """汇总 Agent 执行结果"""
        aggregated = {
            "agents_executed": list(agent_outputs.keys()),
            "outputs": agent_outputs,
        }
        
        # 提取关键信息
        for agent_id, output in agent_outputs.items():
            if isinstance(output, dict):
                # 合并重要字段
                for key in ["recommendations", "insights", "content"]:
                    if key in output:
                        if key not in aggregated:
                            aggregated[key] = []
                        if isinstance(output[key], list):
                            aggregated[key].extend(output[key])
                        else:
                            aggregated[key].append(output[key])
        
        return aggregated
