# Lumina Docker 本地部署指南

> 本文档指导你如何在本地使用 Docker 快速启动 Lumina AI营销平台

---

## 📋 前置要求

### 必须安装

| 软件 | 版本要求 | 下载地址 |
|------|---------|---------|
| Docker Desktop | 4.0+ | https://www.docker.com/products/docker-desktop |
| Git | 任意版本 | https://git-scm.com/downloads |

### 系统要求

- **Windows**: Windows 10/11 专业版或企业版（启用 WSL2）
- **macOS**: macOS 11+ (Big Sur)
- **Linux**: Ubuntu 20.04+ / CentOS 8+

### 资源配置

- **内存**: 至少 4GB 可用内存（推荐 8GB）
- **磁盘**: 至少 10GB 可用空间
- **网络**: 稳定的互联网连接（下载镜像）

---

## 🚀 快速开始

### 方式一：使用启动脚本（推荐）

#### Windows (CMD/PowerShell)

```powershell
# 1. 进入项目目录
cd d:\project\lumina

# 2. 运行启动脚本
.\scripts\docker-start.bat

# 或 PowerShell 版本
.\scripts\docker-start.ps1

# 3. 选择启动模式
# [1] 基础模式 - API + PostgreSQL + Redis
# [2] 完整模式 - 额外包含 pgAdmin + Redis Insight
# [3] 浏览器模式 - 额外包含 Playwright 浏览器
```

#### Linux / macOS

```bash
# 1. 进入项目目录
cd /path/to/lumina

# 2. 给脚本执行权限
chmod +x scripts/docker-start.sh

# 3. 运行启动脚本
./scripts/docker-start.sh

# 或使用模式参数
./scripts/docker-start.sh basic   # 基础模式
./scripts/docker-start.sh full    # 完整模式
./scripts/docker-start.sh browser # 浏览器模式
./scripts/docker-start.sh stop    # 停止服务
```

---

### 方式二：手动启动

#### 1. 克隆项目

```bash
git clone <your-repo-url> lumina
cd lumina
```

#### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.docker .env

# 编辑 .env 文件，填写必要的 API Keys
vim .env  # 或 code .env / nano .env
```

**必填配置**:
```env
# LLM API Keys（至少填一个）
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-your-key
DEEPSEEK_API_KEY=your-key  # 推荐，性价比高
```

#### 3. 启动服务

```bash
# 基础模式（推荐）
docker compose -f docker-compose.local.yml up --build

# 后台运行
 docker compose -f docker-compose.local.yml up -d

# 完整模式（含管理工具）
docker compose -f docker-compose.local.yml --profile with-pgadmin --profile with-redis-insight up -d
```

#### 4. 验证启动

```bash
# 查看服务状态
docker ps

# 测试 API
curl http://localhost:8000/health

# 查看日志
docker logs -f lumina-api
```

---

## 📁 服务说明

### 核心服务

| 服务名 | 端口 | 说明 | 访问地址 |
|-------|------|------|---------|
| lumina-api | 8000 | 主 API 服务 | http://localhost:8000 |
| postgres | 5432 | PostgreSQL 数据库 | localhost:5432 |
| redis | 6379 | Redis 缓存 | localhost:6379 |

### 可选服务（完整模式）

| 服务名 | 端口 | 说明 | 默认账号 |
|-------|------|------|---------|
| pgadmin | 5050 | 数据库管理 | admin@lumina.local / admin |
| redis-insight | 5540 | Redis 管理 | - |

---

## 🔧 常用命令

### 服务管理

```bash
# 启动服务
docker compose -f docker-compose.local.yml up -d

# 停止服务
docker compose -f docker-compose.local.yml down

# 重启服务
docker compose -f docker-compose.local.yml restart

# 查看日志
docker logs -f lumina-api

# 查看所有服务状态
docker compose -f docker-compose.local.yml ps
```

### 调试命令

```bash
# 进入 API 容器
docker exec -it lumina-api bash

# 进入数据库
docker exec -it lumina-postgres psql -U lumina

# 进入 Redis
docker exec -it lumina-redis redis-cli

# 查看容器资源使用
docker stats
```

### 数据管理

```bash
# 备份数据库
docker exec lumina-postgres pg_dump -U lumina lumina > backup.sql

# 恢复数据库
docker exec -i lumina-postgres psql -U lumina lumina < backup.sql

# 清理所有数据（谨慎！）
docker compose -f docker-compose.local.yml down -v
```

---

## 🐛 故障排除

### 问题一：端口被占用

**错误信息**:
```
Error response from daemon: Ports are not available: listen tcp 0.0.0.0:8000
```

**解决方案**:
```bash
# 1. 查找占用端口的进程
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000

# 2. 修改 .env 文件，更换端口
LUMINA_PORT=8001
```

### 问题二：内存不足

**错误信息**:
```
ERROR: Service 'lumina-api' failed to build: no space left on device
```

**解决方案**:
```bash
# 清理 Docker 缓存
docker system prune -a

# 增加 Docker 内存限制（Docker Desktop 设置中）
# Settings -> Resources -> Memory -> 8GB
```

### 问题三：热加载不生效（Windows）

**解决方案**:
确保 .env 中设置了:
```env
WATCHFILES_FORCE_POLLING=true
```

### 问题四：数据库连接失败

**错误信息**:
```
connection refused to postgres:5432
```

**解决方案**:
```bash
# 等待数据库完全启动
docker compose -f docker-compose.local.yml restart postgres

# 检查数据库日志
docker logs lumina-postgres
```

### 问题五：Playwright 浏览器无法启动

**解决方案**:
```bash
# 进入容器安装浏览器
docker exec -it lumina-api bash
playwright install chromium
```

---

## 📝 配置说明

### 环境变量清单

| 变量名 | 必填 | 默认值 | 说明 |
|-------|------|--------|------|
| OPENAI_API_KEY | 是* | - | OpenAI API Key |
| ANTHROPIC_API_KEY | 是* | - | Claude API Key |
| DEEPSEEK_API_KEY | 是* | - | DeepSeek API Key |
| LUMINA_PORT | 否 | 8000 | API 端口 |
| LOG_LEVEL | 否 | INFO | 日志级别 |
| WATCHFILES_FORCE_POLLING | 否 | true | Windows 热加载 |

*至少配置一个 LLM API Key

### 配置文件

| 文件 | 说明 | 热加载 |
|------|------|--------|
| config/intent_rules.yaml | Intent 识别规则 | ✅ 是 |
| config/llm.yaml | LLM 配置 | ❌ 否 |
| config/agents.yaml | Agent 编排配置 | ❌ 否 |

---

## 🌐 API 端点

### 核心端点

```bash
# 健康检查
curl http://localhost:8000/health

# Intent 识别
curl -X POST http://localhost:8000/intent/recognize \
  -H "Content-Type: application/json" \
  -d '{"text": "帮我诊断账号", "user_id": "test_001"}'

# Skill 列表
curl http://localhost:8000/skill/list

# 执行 Skill
curl -X POST http://localhost:8000/skill/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_name": "data_analyst",
    "method": "diagnose_account",
    "params": {"account_url": "https://example.com/user"},
    "user_id": "test_001"
  }'
```

### 完整 API 文档

启动后访问: http://localhost:8000/docs

---

## 🔒 安全注意事项

1. **不要在生产环境使用此配置**
   - 默认密码是公开的
   - 未启用 HTTPS
   - 调试模式已开启

2. **保护 API Keys**
   - .env 文件不要提交到 Git
   - 定期轮换 API Keys

3. **数据安全**
   - 数据库默认无密码（开发便利）
   - 生产环境请配置强密码

---

## 📊 性能优化

### 提升启动速度

```bash
# 使用 BuildKit
docker buildx create --use
docker compose -f docker-compose.local.yml build

# 多阶段构建缓存
DOCKER_BUILDKIT=1 docker compose build
```

### 减少内存占用

```bash
# 限制容器内存
docker compose -f docker-compose.local.yml up -d --memory=2g
```

---

## 🆘 获取帮助

### 查看日志

```bash
# 所有服务日志
docker compose -f docker-compose.local.yml logs

# 特定服务
docker logs -f lumina-api

# 最近 100 行
docker logs --tail 100 lumina-api
```

### 重置环境

```bash
# 完全重置（删除所有数据）
docker compose -f docker-compose.local.yml down -v
docker system prune -a

# 重新启动
docker compose -f docker-compose.local.yml up --build
```

---

## 🎉 验证部署成功

访问以下地址验证:

1. **Health Check**: http://localhost:8000/health
   - 应返回: `{"status": "ok", ...}`

2. **API Docs**: http://localhost:8000/docs
   - 应看到 Swagger UI

3. **Intent Test**:
   ```bash
   curl -X POST http://localhost:8000/intent/recognize \
     -d '{"text": "你好", "user_id": "test"}'
   ```
   - 应返回 Intent 识别结果

---

## 📚 延伸阅读

- [项目 README](../README.md)
- [开发计划](../Development_Plan_v3_Integrated.md)
- [API 文档](http://localhost:8000/docs) (启动后访问)

---

**文档版本**: 2026-03-30  
**维护者**: Lumina Team
