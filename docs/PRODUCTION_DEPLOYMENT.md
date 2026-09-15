# Lumina 生产环境部署指南

> 本文档指导你如何在 Linux 服务器上使用 Docker Compose 部署 Lumina AI 营销平台，并持久化历史对话与日志数据。

---

## 架构选择

当前采用 **方案 A**：

- **PostgreSQL**：继续使用宿主机上已安装的 PostgreSQL（yum/apt），确保数据在容器重建后仍保留。
- **Lumina API**：使用 Docker Compose 管理容器，替代裸 `docker run`，提升可维护性、健康检查与重启策略。

> 为什么不直接用 `docker run`？
> - `docker run` 命令参数散落在历史记录中，难以复现。
> - 环境变量、端口、重启策略不便于版本控制。
> - Docker Compose 提供声明式配置、健康检查、日志聚合与一键回滚。

---

## 前置要求

### 服务器环境

- Linux 服务器（CentOS 7+/Ubuntu 20.04+）
- Docker 20.10+
- Docker Compose v2+
- PostgreSQL 已安装并监听可被容器访问的地址

### 已确认信息（以当前服务器 `182.92.84.206` 为例）

| 项目 | 值 | 说明 |
|------|-----|------|
| 宿主机内网 IP | `172.29.146.189` | 容器通过该 IP 访问宿主机 PostgreSQL |
| PostgreSQL 端口 | `5432` | 已监听 `0.0.0.0:5432` |
| 数据库名 | `lumina` | |
| 数据库用户 | `lumina` | |
| 数据库密码 | `lumina123` | 生产环境请使用强密码 |
| 对外端口 | `8080` | 映射到容器内 `8000` |
| 镜像标签 | `lumina720:1.0` | |

---

## 部署文件

本地项目已提供两个文件：

| 文件 | 作用 |
|------|------|
| `docker-compose.prod.yml` | Docker Compose 生产编排配置 |
| `env-prod-template.txt` | `.env.prod` 模板，上传到服务器后改名为 `.env.prod` 并填写真实值 |

> `.env.prod` 包含密码等敏感信息，**不要提交到 Git**。

---

## 部署步骤

### 1. 本地构建镜像（如尚未构建）

```bash
cd d:\project\lumina
docker build -t lumina720:1.0 -f apps/api/Dockerfile .
```

### 2. 上传镜像到服务器

```bash
docker save lumina720:1.0 | ssh root@182.92.84.206 "docker load"
```

### 3. 上传编排文件到服务器

```bash
scp docker-compose.prod.yml root@182.92.84.206:/root/lumina-prod/
scp env-prod-template.txt root@182.92.84.206:/root/lumina-prod/
```

### 4. 在服务器上创建 `.env.prod`

```bash
ssh root@182.92.84.206
mkdir -p /root/lumina-prod
cd /root/lumina-prod
cp env-prod-template.txt .env.prod
vim .env.prod
```

最小可用配置示例：

```env
LUMINA_IMAGE=lumina720:1.0
LUMINA_PORT=8080

DATABASE_URL=postgresql://lumina:lumina123@172.29.146.189:5432/lumina
CHAT_MEMORY_BACKEND=postgres

LUMINA_HERMES_MODEL=deepseek-v4-flash
LUMINA_HERMES_PROVIDER=deepseek
```

> 当前 `llm.yaml` 中已包含默认的 DeepSeek API Key，因此 `.env.prod` 中可不填 `DEEPSEEK_API_KEY`；如需覆盖，可追加 `DEEPSEEK_API_KEY=sk-...`。

### 5. 切换到 Docker Compose 部署

```bash
cd /root/lumina-prod

# 停止并移除旧的 docker run 容器
docker stop lumina51
docker rm lumina51

# 使用 Docker Compose 启动
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

---

## 常用命令

### 查看状态

```bash
cd /root/lumina-prod
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

### 重启服务

```bash
cd /root/lumina-prod
docker compose -f docker-compose.prod.yml restart
```

### 停止服务（不删除数据）

```bash
cd /root/lumina-prod
docker compose -f docker-compose.prod.yml down
```

### 重新创建容器（更新镜像或环境变量后）

```bash
cd /root/lumina-prod
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --force-recreate
```

---

## 验证部署

### 1. 健康检查

```bash
curl -s http://localhost:8080/health | python -m json.tool
```

期望返回：

```json
{
    "status": "ok",
    "service": "lumina",
    "db_pool": true
}
```

### 2. 验证历史记忆持久化

```bash
curl -s "http://localhost:8080/api/v1/services/system-chat/memory?user_id=13810689392&conversation_id=6eaf2db8-8d71-45de-b565-ae426562c6e0&limit=10" | python -m json.tool
```

期望返回 `count > 0` 且有 `messages` 数组。

### 3. 直接查询数据库

```bash
PGPASSWORD=lumina123 psql -h 172.29.146.189 -U lumina -d lumina -c 'SELECT COUNT(*) FROM chat_messages;'
```

---

## 数据持久化说明

- **聊天记录**存储在 PostgreSQL 的 `chat_messages` 表中。
- **对话画像**存储在 PostgreSQL 的 `conversation_profiles` 表中。
- 因为 PostgreSQL 运行在宿主机上，即使 `lumina51` 容器被删除、重建或升级，数据仍然保留。
- 升级 Lumina 镜像时，只需重新 `docker load` 新镜像，然后 `docker compose up -d --force-recreate`。

---

## 回滚方案

如果 Compose 部署后出现问题，可快速回滚到旧的 `docker run` 方式：

```bash
cd /root/lumina-prod
docker compose -f docker-compose.prod.yml down

docker run -d --name lumina51 \
  -p 8080:8000 \
  --restart always \
  -e DATABASE_URL=postgresql://lumina:lumina123@172.29.146.189:5432/lumina \
  -e CHAT_MEMORY_BACKEND=postgres \
  -e LUMINA_HERMES_MODEL=deepseek-v4-flash \
  -e LUMINA_HERMES_PROVIDER=deepseek \
  lumina720:1.0
```

---

## 注意事项

1. **宿主机 IP 变化**：如果服务器重启后内网 IP 发生变化，需要更新 `.env.prod` 中的 `DATABASE_URL` 并重新 `docker compose up -d`。
2. **防火墙**：确保 `5432` 端口不对外开放，仅允许容器或本地访问。
3. **备份**：定期使用 `pg_dump` 备份数据库。
4. **HTTPS**：生产环境建议在 Nginx/Cloudflare 等反向代理后启用 HTTPS。

---

## 相关文件

- `docker-compose.prod.yml`
- `env-prod-template.txt`
- `docs/DOCKER_DEPLOYMENT.md`（本地开发环境部署）

---

**文档版本**: 2026-07-28  
**维护者**: Lumina Team
