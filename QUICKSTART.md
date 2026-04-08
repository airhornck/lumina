# Lumina 快速启动指南

> 5 分钟本地启动 Lumina AI营销平台

---

## 🎯 快速开始

### 第一步：安装 Docker

- **Windows/Mac**: [下载 Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Linux**: `curl -fsSL https://get.docker.com | sh`

### 第二步：下载项目

```bash
git clone <repository-url>
cd lumina
```

### 第三步：启动服务

#### Windows

双击运行：`scripts\docker-start.bat`

或在 PowerShell 中执行：
```powershell
.\scripts\docker-start.ps1
```

#### Linux / macOS

```bash
chmod +x scripts/docker-start.sh
./scripts/docker-start.sh
```

### 第四步：验证启动

浏览器访问：http://localhost:8000/health

看到 `{"status": "ok"}` 即表示成功！

---

## 📂 项目结构

```
lumina/
├── apps/
│   ├── api/           # FastAPI 主服务
│   ├── intent/        # 工业级 Intent 层
│   ├── orchestra/     # Agent 编排
│   └── rpa/           # 浏览器自动化
├── skills/            # 13个 Agent Skills
├── config/            # 配置文件
├── scripts/           # 启动脚本
├── docker-compose.local.yml  # Docker 配置
└── docs/              # 文档
```

---

## 🔧 常用命令

```bash
# 查看日志
docker logs -f lumina-api

# 重启服务
docker compose -f docker-compose.local.yml restart

# 停止服务
docker compose -f docker-compose.local.yml down

# 进入容器
docker exec -it lumina-api bash
```

---

## 🐛 常见问题

### 端口被占用

编辑 `.env` 文件：
```env
LUMINA_PORT=8001  # 改为其他端口
```

### 需要 API Key

编辑 `.env` 文件，填写至少一个：
```env
DEEPSEEK_API_KEY=your-key-here  # 推荐
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-your-key
```

---

## 📖 详细文档

- [Docker 部署完整指南](docs/DOCKER_DEPLOYMENT.md)
- [项目开发计划](Development_Plan_v3_Integrated.md)
- [API 文档](http://localhost:8000/docs) (启动后访问)

---

**启动遇到问题？** 查看 [故障排除](docs/DOCKER_DEPLOYMENT.md#-故障排除)
