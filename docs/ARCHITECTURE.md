# AI Core Service 架构文档

## 版本信息
- 版本: V3.1
- 日期: 2026-03-28
- 变更: 调整为微服务架构，当前服务专注于 AI 能力

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端应用层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Web App    │  │  Mobile App │  │  客户管理端 (Admin)      │ │
│  │  (Next.js)  │  │   (React)   │  │  (独立服务)              │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
└─────────┼────────────────┼─────────────────────┼───────────────┘
          │                │                     │
          │                │                     │ 管理租户/用户/权限
          │                │                     ▼
          │                │      ┌──────────────────────────┐
          │                │      │   Customer Management    │
          │                │      │   Service (独立)          │
          │                │      │  - 租户管理               │
          │                │      │  - 用户注册/登录           │
          │                │      │  - 权限控制 (RBAC)        │
          │                │      │  - 套餐/计费              │
          │                │      └──────────┬───────────────┘
          │                │                 │
          │                │                 │ 颁发 JWT (含 user_id)
          │                │                 ▼
          └────────────────┴─────────────────┬───────────────┐
                                             │               │
               ┌─────────────────────────────┘               │
               │ 携带 user_id 请求                           │
               ▼                                             │
┌──────────────────────────────────┐                        │
│       API Gateway                │                        │
│  (Kong / Nginx / Traefik)        │                        │
│  - 限流 / 认证 / 路由             │                        │
└──────────┬───────────────────────┘                        │
           │                                                │
           ▼                                                │
┌───────────────────────────────────────────────────────────┤
│              AI Core Service (本服务)                      │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  接入层 (REST API)                                   │  │
│  │  - /v1/chat (对话接口，需 user_id)                   │  │
│  │  - /v1/skills/{name} (Skill 调用，需 user_id)        │  │
│  │  - /v1/memory/{user_id} (记忆管理)                   │  │
│  │  - /v1/profile/{user_id} (画像管理)                  │  │
│  └─────────────────────────────────────────────────────┘  │
│                          │                                │
│                          ▼                                │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Orchestra Core (编排层)                             │  │
│  │  - Router (意图路由)                                 │  │
│  │  - Planner (动态规划)                                │  │
│  │  - Executor (执行器)                                 │  │
│  │  - Critic (审核器)                                   │  │
│  └─────────────────────────────────────────────────────┘  │
│                          │                                │
│                          ▼                                │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Skills Hub (能力层)                                 │  │
│  │  - 账号诊断 / 流量分析                                │  │
│  │  - 内容生成 / 选题建议                                │  │
│  │  - 行业画像 / 方法论                                 │  │
│  └─────────────────────────────────────────────────────┘  │
│                          │                                │
│                          ▼                                │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  User Context (用户上下文层，按 user_id 隔离)          │  │
│  │  - User Profile Service (画像管理)                   │  │
│  │  - Memory Service (记忆管理)                         │  │
│  │  - Conversation Service (对话记录)                   │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
           │
           ▼
┌───────────────────────────────────────────────────────────┐
│  数据层 (按 user_id 隔离)                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │ PostgreSQL │  │   Redis    │  │  Milvus/Pinecone   │  │
│  │ (用户数据)  │  │ (缓存/记忆) │  │   (向量检索)       │  │
│  └────────────┘  └────────────┘  └────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

## 服务边界

### AI Core Service (本服务)

**职责**：
- ✅ AI 对话处理（Orchestra 编排）
- ✅ Skill 执行（7+ Core Skills）
- ✅ 按 `user_id` 的用户画像管理
- ✅ 按 `user_id` 的记忆/上下文管理
- ✅ 按 `user_id` 的对话记录管理
- ✅ 行业画像包应用
- ✅ Critic 审核与质量保障
- ✅ 数据隔离（所有数据按 `user_id` 隔离）

**不职责**：
- ❌ 租户管理（由客户管理端实现）
- ❌ 用户注册/登录（由客户管理端实现）
- ❌ 权限控制（由客户管理端实现，本服务只接收 user_id）
- ❌ 套餐/计费（由客户管理端实现）
- ❌ 多租户数据隔离（由客户管理端在租户层处理）

### Customer Management Service (客户管理端，独立服务)

**职责**：
- 租户管理（创建、配置、停用）
- 用户管理（注册、登录、密码重置）
- 权限控制（RBAC：角色、权限、API Key）
- 套餐与计费管理
- 使用统计与监控
- 向 AI Core Service 颁发带 `user_id` 的 Token

## 数据模型

### 核心表结构（按 user_id 隔离）

```sql
-- 对话记录
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,           -- 数据隔离键
    session_id VARCHAR(64) NOT NULL,
    messages JSONB NOT NULL,                -- 消息列表
    metadata JSONB,                         -- 元数据
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_user_id (user_id),
    INDEX idx_user_session (user_id, session_id),
    INDEX idx_created_at (created_at)
);

-- 用户画像
CREATE TABLE user_profiles (
    user_id VARCHAR(64) PRIMARY KEY,
    industry VARCHAR(64),                   -- 行业
    preferences JSONB,                      -- 偏好设置
    content_style JSONB,                    -- 内容风格
    platform_settings JSONB,                -- 平台设置
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 用户记忆（短期/长期）
CREATE TABLE user_memories (
    user_id VARCHAR(64) NOT NULL,
    memory_key VARCHAR(128) NOT NULL,       -- 记忆键
    memory_value JSONB NOT NULL,            -- 记忆值
    memory_type VARCHAR(32),                -- short_term / long_term
    expires_at TIMESTAMP,                   -- 过期时间（短期记忆）
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (user_id, memory_key),
    INDEX idx_user_type (user_id, memory_type)
);

-- Skill 执行记录
CREATE TABLE skill_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64),
    skill_name VARCHAR(64) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    execution_time_ms INTEGER,
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_user_skill (user_id, skill_name),
    INDEX idx_created_at (created_at)
);

-- 用户反馈
CREATE TABLE user_feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    session_id VARCHAR(64),
    feedback_type VARCHAR(32) NOT NULL,     -- rating / thumbs / comment
    rating INTEGER,                         -- 1-5评分
    comment TEXT,
    skill_name VARCHAR(64),
    execution_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_user_id (user_id),
    INDEX idx_skill (skill_name)
);
```

## API 规范

### 1. 对话接口

```http
POST /v1/chat
Content-Type: application/json
Authorization: Bearer {token}  # 由客户管理端颁发

{
    "user_id": "user_abc123",           # 必填
    "session_id": "session_xyz789",      # 可选，不传则创建新会话
    "message": "帮我诊断小红书账号",
    "context": {
        "platform": "xiaohongshu",
        "industry": "beauty"
    }
}

Response:
{
    "success": true,
    "data": {
        "session_id": "session_xyz789",
        "response": "根据您的账号数据分析...",
        "skills_used": ["account_diagnosis"],
        "execution_time_ms": 500,
        "suggested_followup": ["查看详细报告", "优化建议"]
    }
}
```

### 2. Skill 直接调用

```http
POST /v1/skills/{skill_name}
Content-Type: application/json

{
    "user_id": "user_abc123",
    "input": {
        "platform": "xiaohongshu",
        "topic": "护肤技巧"
    }
}
```

### 3. 用户画像管理

```http
# 获取画像
GET /v1/profile/{user_id}

# 更新画像
PUT /v1/profile/{user_id}
{
    "industry": "beauty",
    "preferences": {
        "tone": "friendly",
        "content_length": "medium"
    }
}
```

### 4. 记忆管理

```http
# 获取记忆
GET /v1/memory/{user_id}?key=last_topic

# 设置记忆
POST /v1/memory/{user_id}
{
    "key": "last_topic",
    "value": "护肤",
    "type": "short_term",
    "ttl": 3600
}

# 删除记忆
DELETE /v1/memory/{user_id}?key=last_topic
```

## 认证流程

### 方案1（推荐）：客户管理端前置认证

```
1. 用户登录 -> 客户管理端
2. 客户管理端验证用户身份和权限
3. 客户管理端颁发 JWT Token（包含 user_id, tenant_id）
4. 前端携带 Token 请求 AI Core Service
5. API Gateway 验证 Token
6. AI Core Service 从 Token 中提取 user_id，不处理权限
7. AI Core Service 按 user_id 进行数据隔离
```

### 方案2：API Key 认证

```
1. 客户在管理端生成 API Key
2. API Key 绑定到特定 user_id 或应用
3. 前端使用 API Key 请求 AI Core Service
4. AI Core Service 验证 API Key，获取 user_id
```

## 部署架构

### 开发环境

```yaml
# docker-compose.yml
version: '3.8'
services:
  ai-core:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_core
      - REDIS_URL=redis://redis:6379
  
  postgres:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7
```

### 生产环境

```
┌─────────────────────────────────────┐
│           K8s Cluster               │
│  ┌─────────────────────────────┐   │
│  │     Ingress Controller      │   │
│  │    (Nginx / Traefik)        │   │
│  └─────────────┬───────────────┘   │
│                │                    │
│  ┌─────────────┴───────────────┐   │
│  │      AI Core Service        │   │
│  │      (3+ Replicas)          │   │
│  │  ┌─────┐ ┌─────┐ ┌─────┐   │   │
│  │  │Pod 1│ │Pod 2│ │Pod 3│   │   │
│  │  └─────┘ └─────┘ └─────┘   │   │
│  └─────────────┬───────────────┘   │
│                │                    │
│  ┌─────────────┴───────────────┐   │
│  │      PostgreSQL Cluster     │   │
│  │      (Primary + Replica)    │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

## 关键设计决策

### 1. 为什么将多租户移到客户管理端？

- **单一职责**：AI Core Service 专注于 AI 能力，不处理复杂的租户逻辑
- **无状态化**：AI Core Service 可以水平扩展，不依赖租户配置
- **灵活性**：客户管理端可以独立演进，支持多种租户模型
- **安全性**：敏感的用户管理逻辑在独立服务中处理

### 2. 数据隔离策略

- **应用层隔离**：所有 SQL 查询都带 `WHERE user_id = ?`
- **不依赖数据库行级安全**：保持简单，便于分库分表
- **Redis 隔离**：使用 `user:{user_id}:key` 作为 key

### 3. 水平扩展

- **无状态服务**：不保存用户会话在内存中
- **外部化状态**：会话状态、记忆存储在 Redis
- **数据库连接池**：支持高并发连接

## 迁移指南

### 从单体架构迁移

1. **数据迁移**：将用户数据导出，按 user_id 重新组织
2. **API 调整**：所有接口增加 user_id 参数
3. **认证剥离**：将认证逻辑移到 API Gateway 或客户管理端
4. **分阶段上线**：先上线 AI Core，再逐步迁移用户

## 性能目标

| 指标 | 目标值 |
|------|--------|
| API 响应时间 (P95) | < 1s |
| Skill 执行时间 (P95) | < 3s |
| 并发用户数 | 10,000+ |
| 数据库查询时间 (P95) | < 50ms |
| 可用性 | 99.9% |
