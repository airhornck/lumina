"""orchestra 包：仅保留 skills/ 纯 skill 函数资产（供 Hermes 工具层进程内调用）。

旧聊天编排链路（core/nlg/task_state/intent_guards/required_fields/
agent_orchestrator/router）已随 phase4 unified planner spec §7 退役删除，
统一规划由 Hermes Agent 承担（apps/api/src/services/hermes_adapter.py）。
"""
