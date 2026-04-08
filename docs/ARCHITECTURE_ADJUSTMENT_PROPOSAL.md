# AI 营销助手架构调整建议

## 调整背景

将单体架构调整为微服务架构，实现前后端分离，当前 AI 服务专注于核心 AI 能力。

## 调整后架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端应用层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Web App    │  │  Admin      │  │  客户管理端              │ │
│  │  (用户界面)  │  │  (管理后台)  │  │  (租户/用户/权限管理)     │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
└─────────┼────────────────┼─────────────────────┼───────────────┘
          │                │                     │
          │                │                     │ 管理 API
          │                │                     ▼
          │                │      ┌──────────────────────────┐
          │                │      │    客户管理服务           │
          │                │      │  - 租户管理               │
          │                │      │  - 用户管理               │
          │                │      │  - 权限控制               │
          │                │      │  - 套餐/计费              │
          │                │      └──────────┬───────────────┘
          │                │                 │
          │                │                 │ 获取租户配置
          │                │                 ▼
          │                │      ┌──────────────────────────┐
          └────────────────┴──────┤      AI Core Service      │
                                  │      (当前服务)           │
                                  ├──────────────────────────┤
                                  │  ┌────────────────────┐  │
                                  │  │  User Context      │  │
                                  │  │  - user_id         │  │
                                  │  │  - user_profile    │  │
                                  │  │  - memory          │  │
                                  │  │  - conversation    │  │
                                  │  └────────────────────┘  │
                                  │                          │
                                  │  ┌────────────────────┐  │
                                  │  │  Orchestra Core    │  │
                                  │  │  - Router          │  │
                                  │  │  - Planner         │  │
                                  │  │  - Executor        │  │
                                  │  │  - Critic          │  │
                                  │  └────────────────────┘  │
                                  │                          │
                                  │  ┌────────────────────┐  │
                                  │  │  Skills Hub        │  │
                                  │  │  - 7+ Core Skills  │  │
                                  │  └────────────────────┘  │
                                  └──────────────────────────┘
```

## 职责划分

### 1. AI Core Service (当前服务)

**定位**：无状态 AI 服务，专注智能能力

**职责**：
- ✅ AI 对话处理（Orchestra 编排）
- ✅ Skill 执行（诊断、生成、分析等）
- ✅ 用户级记忆管理（按 user_id）
- ✅ 用户级画像管理（按 user_id）
- ✅ 对话记录存储（按 user_id）
- ✅ 上下文管理

**不处理**：
- ❌ 租户管理
- ❌ 用户注册/登录
- ❌ 权限验证（仅接收 user_id）
- ❌ 计费/套餐

**API 设计**：
```python
# 核心接口
POST /v1/chat              # 对话（需传入 user_id）
POST /v1/skills/{name}     # 直接调用 Skill
GET  /v1/memory/{user_id}  # 获取用户记忆
POST /v1/memory/{user_id}  # 更新用户记忆
GET  /v1/profile/{user_id} # 获取用户画像
```

### 2. 客户管理端（独立服务）

**定位**：客户管理、租户管理、权限控制

**职责**：
- 租户管理（创建、配置、停用）
- 用户管理（注册、登录、密码重置）
- 权限控制（RBAC）
- 套餐与计费
- API Key 管理
- 使用统计（从 AI 服务获取数据聚合）

**与 AI 服务关系**：
- AI 服务启动时从客户管理服务获取租户配置
- 或 AI 服务仅接收 user_id，不感知租户概念

## 数据边界

### AI Core Service 数据（按 user_id 隔离）

```
数据库: ai_service_db

表:
- conversations (user_id, session_id, messages, created_at)
- user_profiles (user_id, industry, preferences, created_at)
- user_memories (user_id, key, value, updated_at)
- skill_executions (user_id, skill_name, input, output, created_at)
```

### 客户管理端数据

```
数据库: customer_management_db

表:
- tenants (tenant_id, name, config, status)
- users (user_id, tenant_id, email, role, status)
- roles (role_id, permissions)
- subscriptions (tenant_id, plan, quota, used)
- api_keys (key, tenant_id, user_id, permissions)
```

## 认证流程

```
1. 用户登录 -> 客户管理端
2. 客户管理端验证 -> 颁发 JWT Token
3. 前端携带 Token 请求 AI 服务
4. AI 服务验证 Token（可选，或只验证客户管理端签名的 user_id）
5. AI 服务使用 user_id 进行数据隔离
```

简化方案：
- AI 服务只接收 `user_id` + `tenant_id`（在 JWT payload 中）
- AI 服务不验证权限，只负责数据按 user_id 隔离
- 权限在客户管理端控制（API Gateway 层）

## 修改建议

### 1. 当前服务简化

移除：
- 多租户相关代码
- 复杂的权限控制
- 企业级 SSO（保留简单的 user_id 识别）

保留：
- 按 user_id 的数据隔离
- 用户画像（按 user_id）
- 记忆管理（按 user_id）
- 对话记录（按 user_id）

### 2. API 调整

所有 API 都需要 `user_id` 参数：

```python
# 调整前
async def process(self, user_input: str, session_id: str, context: dict)

# 调整后（明确 user_id）
async def process(
    self, 
    user_id: str,           # 新增：必填
    user_input: str, 
    session_id: str, 
    context: dict
)
```

### 3. 数据访问调整

所有数据操作都按 `user_id` 过滤：

```python
# 用户画像
def get_user_profile(user_id: str) -> UserProfile:
    return db.query(UserProfile).filter_by(user_id=user_id).first()

# 记忆
def get_memory(user_id: str, key: str) -> str:
    return cache.get(f"memory:{user_id}:{key}")
```

## 部署架构

```
┌─────────────────────────────────────┐
│           API Gateway               │
│    (Kong / Nginx / Traefik)         │
│    - 路由 / 限流 / 认证              │
└──────────────┬──────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
    ▼                     ▼
┌─────────┐         ┌──────────────┐
│ AI Core │         │ Customer     │
│ Service │         │ Management   │
│         │         │              │
│:8000    │         │:8001         │
└────┬────┘         └──────┬───────┘
     │                      │
     ▼                      ▼
┌─────────┐         ┌──────────────┐
│ AI DB   │         │ Customer DB  │
│(用户数据)│         │(租户/用户)    │
└─────────┘         └──────────────┘
```

## 实施步骤

1. **当前服务清理**
   - 移除多租户相关代码
   - 简化认证为 user_id 识别
   - 确保所有数据操作按 user_id 隔离

2. **客户管理端开发**（作为独立项目）
   - 租户管理
   - 用户管理
   - 权限控制
   - API Key 管理

3. **API 调整**
   - 所有接口增加 user_id 参数
   - 调整数据访问层
   - 更新文档

4. **部署配置**
   - 分离数据库
   - 配置 API Gateway
   - 部署两个服务
