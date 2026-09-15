# Lumina 改造 Docker 部署与功能影响分析（混合方案）

> **⚠️ 架构决策更新（2026-07-15）**：本文所述意图识别/规则编排相关内容已决策退役，聊天链路统一由 Hermes LLM planner 承担，详见 `docs/specs/phase4_unified_planner_deprecation_spec.md`。本文保留为历史记录，内容不再维护。

> 版本：v2.0
> 日期：2026-07-04
> 基于方案：《Lumina 混合改造计划（最终版）》
> 前置文档：`LUMINA_BUSINESS_SOURCE_OF_TRUTH.md`

---

## 一、核心结论（TL;DR）

### 1.1 Docker 部署是否需要改变？

**改变很小。**

| 维度 | 当前状态 | 混合方案改造后 | 影响 |
|------|----------|---------------|------|
| 容器数量 | 1 个（lumina-api） | **1 个**（lumina-api） | **无变化** |
| 端口映射 | 8000 | 8000 | 无变化 |
| 新增服务 | 无 | 无 | 无变化 |
| 新增卷 | 源码 + 数据 | 源码 + 数据 + Hermes 数据 | 低 |
| 启动命令 | `docker compose up` | `docker compose up` | 无变化 |
| 环境变量 | 现有变量 | 现有变量 + `LUMINA_USE_HERMES` 等 | 低 |

### 1.2 现有功能是否会受影响？

**不会。**

| 功能 | 影响 | 最终状态 |
|------|------|----------|
| `/health` | 无 | 保留 |
| `/api/v1/debug/chat/stream` | 无 | 保留，内部可路由到 Hermes |
| `/api/v1/services/{service}/stream` | 无 | 保留 |
| `/api/v1/marketing/hub` | 无 | 保留 |
| `/skill/*` | 无 | 保留 |
| `/api/v1/usage/*` | 无 | 保留 |
| `/api/v1/exports/*` | 无 | 保留 |
| `/mcp` | 无 | 保留 |
| RPA/Playwright | 无 | 保留 |
| 内容生成引擎 | 无 | 保留 |

---

## 二、为什么容器数量不变？

混合方案的核心设计是：**Hermes 作为 Python 依赖内嵌到现有 lumina-api 容器中**，不启动独立的 Hermes 服务进程。

```
当前：
┌─────────────────┐
│  lumina-api     │
│  (FastAPI)      │
└─────────────────┘

改造后：
┌─────────────────────────────────────────┐
│  lumina-api                             │
│  ┌──────────────┐  ┌─────────────────┐ │
│  │  FastAPI     │  │  Hermes AIAgent │ │
│  │  路由层       │  │  （Python 库）   │ │
│  └──────────────┘  └─────────────────┘ │
│         │                   ▲          │
│         └───────────────────┘          │
│              内部调用                    │
└─────────────────────────────────────────┘
```

这样设计的好处：
- **不新增容器**，运维复杂度不变
- **不新增端口**，网络安全边界不变
- **Hermes 与 Lumina 同进程通信**，无网络延迟
- **启动命令不变**，开发工作流不变

---

## 三、Docker Compose 变化

### 3.1 改造后的 docker-compose.yml

```yaml
# docker-compose.yml（混合方案）

services:
  lumina-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: lumina-api
    ports:
      - "${LUMINA_PORT:-8000}:8000"
    working_dir: /app
    volumes:
      # 源码热加载
      - .:/app
      # 持久化 Hermes 数据
      - lumina_hermes_data:/app/data/hermes
    env_file:
      - path: .env
        required: false
    environment:
      LLM_CONFIG_PATH: /app/infra/config/llm.yaml
      WATCHFILES_FORCE_POLLING: "${WATCHFILES_FORCE_POLLING:-true}"
      # 新增：Hermes 引擎开关
      LUMINA_USE_HERMES: "${LUMINA_USE_HERMES:-false}"
      HERMES_HOME: /app/data/hermes
    command:
      - uvicorn
      - api.main:app
      - --host
      - "0.0.0.0"
      - --port
      - "8000"
      - --reload
      - --reload-dir
      - /app
      - --app-dir
      - apps/api/src
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 25s

volumes:
  lumina_hermes_data:
```

### 3.2 新增环境变量

```bash
# .env（新增）

# Hermes 引擎开关
LUMINA_USE_HERMES=false  # 阶段 0 保持 false，阶段 1 后设为 true

# Hermes 数据目录
HERMES_HOME=./data/hermes

# Hermes 工具控制（可选）
LUMINA_HERMES_ENABLED_TOOLSETS=lumina_marketing
LUMINA_HERMES_DISABLED_TOOLS=terminal,execute_code,browser,shell,file_write,file_delete
```

### 3.3 新增卷

```bash
# Docker 命名卷
lumina_hermes_data:/app/data/hermes
```

**内容**：
```
data/hermes/
├── config.yaml              # Hermes 配置
├── personas/
│   └── lumina-marketing.md  # Lumina 人设
├── skills/                  # Hermes Skill
├── memory/                  # Hermes 记忆索引
└── sessions/                # Hermes 会话索引
```

---

## 四、Dockerfile 变化

### 4.1 改造后的 Dockerfile

```dockerfile
# Dockerfile（混合方案，关键变化段）

FROM python:3.12-slim-bookworm

# ... 现有依赖安装 ...

# 安装 Lumina 依赖（包含 Hermes 可选依赖组）
RUN pip install -e ".[hermes]" -i ${PIP_INDEX_URL}

# 可选：预下载 Hermes 需要的模型/浏览器（如果需要）
# 但 Lumina 不使用 Hermes 的浏览器自动化，不需要额外安装

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api/src"]
```

### 4.2 pyproject.toml 变化

```toml
# pyproject.toml（新增 hermes 可选依赖）

[project.optional-dependencies]
hermes = [
    "hermes-agent[core]>=0.x",
]

# 开发环境安装
# pip install -e ".[dev,hermes]"
```

**注意**：Hermes 全量安装很重（含 UI/TUI/桌面端），建议只安装核心依赖。

---

## 五、功能影响分析

### 5.1 各接口影响评估

| 接口/功能 | 阶段 0 影响 | 阶段 1 影响 | 阶段 2 影响 | 最终状态 |
|-----------|------------|------------|------------|----------|
| `/health` | 无 | 无 | 无 | 保留 |
| `/api/v1/debug/chat/stream` | 无 | 内部路由到 Hermes，SSE 格式不变 | 无 | 保留 |
| `/api/v1/services/{service}/stream` | 无 | 无 | 无 | 保留 |
| `/api/v1/marketing/hub` | 无 | 内部可路由到 Hermes | 无 | 保留 |
| `/skill/*` | 无 | 无 | 无 | 保留 |
| `/api/v1/usage/*` | 无 | 无 | 无 | 保留 |
| `/api/v1/exports/*` | 无 | 无 | 无 | 保留 |
| `/mcp` | 无 | 无 | 无 | 保留 |
| RPA/Playwright | 无 | 无 | 无 | 保留 |
| 内容生成引擎 | 无 | 无 | 无 | 保留 |

### 5.2 前端影响

**无影响。**

前端继续使用：
```javascript
// 原有 SSE 调用方式完全不变
const response = await fetch('/api/v1/debug/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    capability: 'system_chat',
    user_id: 'user-123',
    conversation_id: 'conv-456',
    message: '帮我写个小红书文案'
  })
});
```

### 5.3 数据影响

| 数据 | 影响 | 措施 |
|------|------|------|
| 现有对话记录 | 阶段 0 迁移到 PostgreSQL | 迁移脚本 |
| 用户画像 | 无影响 | 保留在 PostgreSQL |
| Token 用量 | 无影响 | 保留在 PostgreSQL |
| Hermes 记忆 | 阶段 1 新增 | 使用命名卷持久化 |
| Hermes Skill | 阶段 2 新增 | 使用命名卷持久化 |

---

## 六、回滚方案

### 6.1 阶段 1 回滚

如果 Hermes 集成后出现问题：

```bash
# 方式 1：环境变量回滚
docker compose down
# 修改 .env：LUMINA_USE_HERMES=false
docker compose up -d

# 方式 2：运行时回滚（不重启容器）
docker compose exec lumina-api /bin/bash
export LUMINA_USE_HERMES=false
# 等待 uvicorn reload（已挂载源码）
```

### 6.2 阶段 0 回滚

如果 PostgreSQL 记忆出现问题：

```python
# 在配置中切换回内存存储
CHAT_MEMORY_BACKEND=os.environ.get("CHAT_MEMORY_BACKEND", "postgres")
# 改为 memory 即可回退到 dict（不推荐长期）
```

---

## 七、风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| Hermes 依赖冲突 | 中 | 中 | 使用可选依赖组，隔离安装 |
| 镜像体积增大 | 中 | 低 | 仅安装核心依赖 |
| 卷权限问题 | 低 | 中 | 使用命名卷，避免绑定挂载权限 |
| 启动时间增加 | 低 | 低 | Hermes 是 Python 库，启动开销小 |

---

## 八、总结

### 8.1 Docker 部署结论

| 问题 | 结论 |
|------|------|
| 是否需要新增容器？ | **否** |
| 是否需要新增端口？ | **否** |
| 是否需要改变启动命令？ | **否** |
| 是否需要改变开发工作流？ | **否** |
| 镜像体积是否明显增加？ | 轻微（仅增加 Hermes 核心依赖） |
| 运维复杂度是否增加？ | 几乎不增加 |

### 8.2 功能影响结论

| 问题 | 结论 |
|------|------|
| 现有功能是否受影响？ | **否** |
| 前端是否需要改造？ | **否** |
| API 是否向后兼容？ | **是** |
| 数据是否安全？ | **是** |
| 回滚是否方便？ | **是** |

### 8.3 最终结论

混合方案在 Docker 部署和功能影响方面的成本极低：
- **容器架构不变**
- **对外接口不变**
- **开发工作流不变**
- **回滚简单**

这是符合业务真源约束（接口不变、最低改造成本）的最优部署方案。

---

## 附录：相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 混合改造计划 | `docs/LUMINA_HYBRID_RENOVATION_PLAN.md` | 最终改造方案 |
| 业务真源 | `docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` | 业务约束 |
| 效果评估 | `docs/LUMINA_RENOVATION_EFFECTIVENESS_ASSESSMENT.md` | 方案效果评估 |
| 底座对比 | `docs/LUMINA_RENOVATION_BASE_COMPARISON_AND_PLAN.md` | OpenClaw vs Hermes |
| 原 OpenClaw 方案 | `docs/LUMINA_OPENCLAW_RENOVATION_PLAN.md` | 已放弃的历史方案 |
