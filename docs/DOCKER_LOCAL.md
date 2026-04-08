# 本地 Docker 启动与 LLM 密钥配置

## 前置条件

- 已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows/macOS）或 Docker Engine + Compose（Linux）。
- 仓库根目录即 `d:\project\lumina`（或你的本机路径）。

## 一键启动（代码热加载）

在项目根目录执行：

```bash
docker compose up --build
```

- 镜像内已执行 `pip install -e ".[dev]"`；通过 **卷挂载** 把当前目录挂到容器内 `/app`，`uvicorn --reload` 会监视 `/app` 下文件变更并自动重启进程。
- API：<http://127.0.0.1:8000/health>  
- 调试对话页：<http://127.0.0.1:8000/debug/chat/>  
- 修改 `apps/`、`packages/`、`static/` 等下的代码保存后，一般几秒内生效（Windows + Docker Desktop 下已设 `WATCHFILES_FORCE_POLLING=true` 以提高可靠性）。

更换宿主机端口：

```bash
set LUMINA_PORT=8080
docker compose up
```

（PowerShell：`$env:LUMINA_PORT=8080`）

## 配置真实 LLM Key（本地测试）

### 1. 使用根目录 `.env`（推荐）

1. 复制模板（若还没有）：

   ```bash
   copy .env.example .env
   ```

2. 编辑 **`.env`**，填入你在 `infra/config/llm.yaml` 里用到的提供商密钥，例如：

   ```env
   # OpenAI（池条目 gpt-4o-mini 等）
   OPENAI_API_KEY=sk-...

   # Anthropic（claude-sonnet 等）
   ANTHROPIC_API_KEY=sk-ant-...

   # DeepSeek（deepseek-v3 等）
   DEEPSEEK_API_KEY=...
   # DEEPSEEK_API_BASE=https://api.deepseek.com  # 如需自定义
   ```

3. `docker-compose.yml` 已通过 `env_file: .env` 把这些变量注入容器；`api.main` 会从 **`/app/.env`**（即你挂载的仓库根 `.env`）再 `load_dotenv` 一次，与本地直接跑 `uvicorn` 行为一致。

4. `llm.yaml` 使用占位符 `${OPENAI_API_KEY:-}` 等形式，由 **环境变量** 替换，**不要把 Key 写进 YAML 提交到 Git**。

### 2. 确认 `debug_chat` / 各 Skill 使用的模型

打开 `infra/config/llm.yaml`：

- `skill_config.debug_chat`：调试页流式对话默认走这里（当前示例为 `gpt-4o-mini` → 需要 **`OPENAI_API_KEY`**）。
- 其他 key（如 `generate_text` → `claude-sonnet`）需对应 **`ANTHROPIC_API_KEY`**。

改模型：只改 `llm.yaml` 里对应条目的 `llm:` 名称，并保证该名称在 `llm_pool` 中已定义且环境变量已配置。

### 3. 容器内配置文件路径

Compose 中已设置：

```yaml
environment:
  LLM_CONFIG_PATH: /app/infra/config/llm.yaml
```

即容器内始终读挂载进来的仓库里的 YAML；你改 `infra/config/llm.yaml` 保存后也会随热加载进程重启而生效。

## 常用命令

| 操作 | 命令 |
|------|------|
| 后台运行 | `docker compose up -d --build` |
| 看日志 | `docker compose logs -f lumina-api` |
| 停掉 | `docker compose down` |
| 依赖变更后重建 | `docker compose build --no-cache && docker compose up` |

若你修改了 **`pyproject.toml` 的依赖列表**，需要 **重新 build 镜像**（`docker compose build --no-cache`），仅改业务代码则无需重建。

## 故障排查

- **热重载不触发**：将 `WATCHFILES_FORCE_POLLING` 设为 `true`（compose 默认已设）；仍异常时可尝试在 Linux/WSL2 下运行 Docker。
- **调试页报无 API Key**：检查 `.env` 是否在仓库根、变量名是否与 `llm.yaml` 中 `${VAR:-}` 一致，且容器已重启（`docker compose up` 会读最新 `env_file`）。
- **healthcheck unhealthy**：首次启动 pip/依赖较重，可等 `start_period` 过后再判；或执行 `docker compose logs lumina-api` 看 traceback。

## 与 OpenClaw 联调

容器只跑 **Python API**。OpenClaw 仍在宿主机 `vendor/openclaw` 中运行；扩展里 **`LUMINA_PYTHON_URL`** 应指向宿主机可访问的 API 地址，例如：

- 同一台机：`http://127.0.0.1:8000`（端口映射与 `LUMINA_PORT` 一致即可）。
