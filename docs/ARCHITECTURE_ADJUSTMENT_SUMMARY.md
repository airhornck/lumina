# 架构调整总结

## 调整日期
2026-03-28

## 调整原因
将 AI 营销助手从单体架构调整为微服务架构，当前服务专注于 AI 核心能力。

## 核心变更

### 1. 服务定位调整

**调整前**：
- 单体应用，包含租户管理、用户管理、AI 能力

**调整后**：
- **AI Core Service（当前服务）**：专注 AI 能力，按 `user_id` 数据隔离
- **客户管理端（独立服务）**：租户管理、用户管理、权限控制

### 2. 当前服务职责（已修改）

**保留功能**：
- ✅ AI 对话处理（Orchestra 编排）
- ✅ 7+ Core Skills 执行
- ✅ 按 `user_id` 的用户画像管理
- ✅ 按 `user_id` 的记忆/上下文管理
- ✅ 按 `user_id` 的对话记录
- ✅ 行业画像包
- ✅ Critic 审核

**移除功能（移到客户管理端）**：
- ❌ 多租户管理
- ❌ 用户注册/登录
- ❌ SSO 单点登录
- ❌ 复杂的权限控制
- ❌ 套餐/计费

### 3. 文档修改清单

| 文档 | 修改内容 |
|------|----------|
| `DEVELOPMENT_PLAN.md` | 更新架构图、添加服务定位说明、修改阶段六内容、添加 API 规范、添加按 user_id 的数据模型 |
| `docs/ARCHITECTURE.md` | 新建详细架构文档 |
| `docs/ARCHITECTURE_ADJUSTMENT_PROPOSAL.md` | 新建架构调整建议书 |

### 4. API 变更

**所有接口必须包含 `user_id`**：

```python
# 调整前
async def process(self, user_input: str, session_id: str, context: dict)

# 调整后
async def process(
    self, 
    user_id: str,           # 新增：必填参数
    user_input: str, 
    session_id: str, 
    context: dict
)
```

**主要 API**：
- `POST /v1/chat` - 对话（需 user_id）
- `POST /v1/skills/{name}` - Skill 调用（需 user_id）
- `GET/PUT /v1/profile/{user_id}` - 画像管理
- `GET/POST/DELETE /v1/memory/{user_id}` - 记忆管理

### 5. 数据模型调整

所有表结构增加 `user_id` 字段作为数据隔离键：

```sql
-- 示例：conversations 表
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,  -- 数据隔离键
    session_id VARCHAR(64) NOT NULL,
    messages JSONB,
    INDEX idx_user_id (user_id),
    INDEX idx_user_session (user_id, session_id)
);
```

### 6. 开发计划调整

**阶段六变更**：
- 原："多租户、私有化部署、SLA 保障"
- 新："性能优化、水平扩展、私有化部署"
- 移除多租户相关内容

**新增说明**：
- 明确说明多租户由客户管理端实现
- 当前服务只负责按 `user_id` 数据隔离

## 文件变更

### 修改的文件
1. `DEVELOPMENT_PLAN.md` - 开发计划文档

### 新建的文件
1. `docs/ARCHITECTURE.md` - 详细架构文档
2. `docs/ARCHITECTURE_ADJUSTMENT_PROPOSAL.md` - 架构调整建议
3. `docs/ARCHITECTURE_ADJUSTMENT_SUMMARY.md` - 本总结文档

## 后续建议

### 1. 当前服务开发重点
- 确保所有数据操作都按 `user_id` 隔离
- 完善用户画像、记忆管理接口
- 保持服务无状态，便于水平扩展

### 2. 客户管理端开发（独立项目）
- 租户管理
- 用户注册/登录/密码重置
- JWT Token 颁发（包含 user_id）
- 权限控制（RBAC）
- API Key 管理

### 3. 部署架构
```
前端 -> API Gateway -> AI Core Service (本服务)
              |
              v
       Customer Management Service (客户管理端)
```

## 优势

1. **单一职责**：AI 服务专注 AI，管理端专注管理
2. **无状态化**：AI 服务可水平扩展
3. **灵活性**：客户管理端可独立演进
4. **安全性**：敏感逻辑在独立服务中
5. **简化开发**：当前服务只需关注 user_id 隔离
