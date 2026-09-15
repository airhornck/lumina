# Lumina Vendor Pin — hermes-agent

- **来源**：`D:/GitHub-Manager/repos/hermes-agent/`（NousResearch/hermes-agent，MIT License）
- **版本**：`0.16.0`（取自源仓库 `pyproject.toml`；源目录无 .git，无法记录 commit hash）
- **拷贝日期**：2026-07-15
- **拷贝方式**：全量源码，排除 `website/ tests/ apps/ ui-tui/ web/ docs/ __pycache__/ node_modules/`
- **用途**：Lumina Phase 4 统一 LLM Planner 执行引擎（`docs/specs/phase4_unified_planner_deprecation_spec.md`，决策点 D1：vendor 拷贝钉版本）
- **加载方式**：`apps/api/src/services/hermes_adapter.py` 在运行时将本目录追加到 `sys.path`（末尾，避免遮蔽 Lumina 同名顶层包）
- **更新纪律**：升级 = 整体重新拷贝 + 更新本文件版本号 + 跑 `tests/hermes/` 全量测试；禁止对本目录做任何本地修改（本地适配一律放在 `apps/api/src/services/hermes_*.py`）
