# 二维码登录系统使用指南

## 功能概述

系统现在支持通过二维码登录抖音、小红书等平台，登录后会自动保存凭证，下次无需重复扫码。

## 工作流程

### 1. 用户触发登录

用户可以通过以下方式触发二维码登录：

- 直接说："登录抖音"、"登录小红书"
- 请求诊断时未提供链接："帮我分析下抖音账号"

### 2. 系统返回二维码

系统会生成二维码并返回给前端展示：

```json
{
  "type": "qr_code_login",
  "platform": "douyin",
  "qr_code_base64": "iVBORw0KGgo...",
  "instructions": [
    "1. 打开 抖音 APP",
    "2. 点击右上角扫一扫",
    "3. 扫描下方二维码",
    "4. 在手机上确认登录"
  ]
}
```

### 3. 用户扫码登录

用户使用手机 APP 扫描二维码并确认登录。

### 4. 系统自动获取数据

登录成功后，系统自动：
- 获取账号信息
- 保存登录凭证（加密存储）
- 进行账号诊断

### 5. 下次自动使用

下次同一用户请求时：
- 系统自动使用已保存的凭证
- 无需再次扫码
- 凭证过期前 7 天会提示重新登录

## API 接口

### 1. 请求二维码登录

```python
# Skill: skill-account-keeper
# Tool: request_qr_code_login

result = await skill_hub_client.call(
    "request_qr_code_login",
    {
        "platform": "douyin",  # 或 "xiaohongshu"
        "user_id": "user_123",
    }
)

# 返回结果
{
    "type": "qr_code",
    "qr_code_base64": "...",
    "session_id": "uuid",
    "expires_in": 300,
}
```

### 2. 检查登录状态

```python
# Skill: skill-account-keeper
# Tool: check_login_status

result = await skill_hub_client.call(
    "check_login_status",
    {
        "session_id": "uuid",
        "user_id": "user_123",
    }
)

# 返回结果
{
    "status": "success",  # pending, scanned, success, expired
    "account_info": {
        "account_name": "用户昵称",
    }
}
```

### 3. 获取已保存账号

```python
result = await skill_hub_client.call(
    "get_saved_accounts",
    {"user_id": "user_123"}
)

# 返回结果
{
    "accounts": [
        {
            "platform": "douyin",
            "account_name": "抖音用户",
            "expires_at": "2024-12-31T23:59:59",
        }
    ]
}
```

### 4. 退出登录

```python
result = await skill_hub_client.call(
    "logout_platform",
    {
        "platform": "douyin",
        "user_id": "user_123",
    }
)
```

## 安全说明

### 凭证存储

1. **加密存储**：所有 Cookie 和 Token 都经过加密后存储
2. **文件权限**：凭证文件设置 600 权限，仅当前用户可读写
3. **分离密钥**：每个用户有独立的加密密钥
4. **自动过期**：凭证默认 30 天后过期

### 数据隔离

- 每个用户的凭证独立存储
- 用户间数据完全隔离
- 按用户名区分不同平台账号

## 前端集成

### 展示二维码

```html
<img src="data:image/png;base64,{{ qr_code_base64 }}" alt="扫码登录">
```

### 轮询检查状态

```javascript
// 每 3 秒检查一次登录状态
const checkStatus = setInterval(async () => {
    const result = await fetch('/api/check_login_status', {
        method: 'POST',
        body: JSON.stringify({ session_id: sessionId })
    }).then(r => r.json());
    
    if (result.status === 'success') {
        clearInterval(checkStatus);
        // 登录成功，刷新页面或显示成功消息
    } else if (result.status === 'expired') {
        clearInterval(checkStatus);
        // 二维码过期，提示重新获取
    }
}, 3000);
```

## 故障排查

### 二维码无法显示

1. 检查是否安装了 `qrcode` 库：`pip install qrcode[pil]`
2. 检查日志中的错误信息

### 扫码后无反应

1. 确认二维码在 5 分钟内有效
2. 检查浏览器是否正常启动
3. 查看日志中的扫码状态

### 凭证保存失败

1. 检查 `data/credentials` 目录权限
2. 确认磁盘空间充足

## 开发说明

### 添加新平台支持

1. 在 `QRCodeLoginManager` 中添加平台登录 URL
2. 实现平台特定的二维码检测逻辑
3. 添加平台特定的账号信息提取

### 修改存储方式

默认使用文件存储，可以替换为数据库存储：

1. 继承 `SecureStorage` 类
2. 实现 `save` 和 `load` 方法
3. 在 `QRCodeLoginManager` 中传入自定义存储

## 注意事项

1. **隐私合规**：确保用户同意保存登录凭证
2. **定期清理**：系统会自动清理过期凭证
3. **异常处理**：扫码过程中可能遇到验证码，需要人工处理
