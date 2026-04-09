# 账号抓取器 (Account Crawler)

基于无头浏览器的自动化账号数据采集系统，支持抖音、小红书等平台。

## 功能特性

- ✅ **多平台支持**: 抖音 (douyin)、小红书 (xiaohongshu)
- ✅ **反检测对抗**: 浏览器指纹伪装、Canvas 噪声、WebGL 伪造
- ✅ **智能限流**: 自适应速率控制，避免触发风控
- ✅ **数据解析**: 自动提取粉丝数、作品数据、互动率等关键指标
- ✅ **容错机制**: 失败重试、降级处理、状态追踪
- ✅ **诊断集成**: 直接对接诊断模块，生成专业分析报告

## 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip install playwright aiohttp

# 安装浏览器（首次运行需要）
playwright install chromium
```

### 2. 手动测试

```bash
# 通过账号名搜索（抖音）
python scripts/test_crawler_manual.py --platform douyin --account "余者来来"

# 通过 URL 直接访问
python scripts/test_crawler_manual.py --platform douyin --url "https://www.douyin.com/user/xxx"

# 小红书
python scripts/test_crawler_manual.py --platform xiaohongshu --account "xxx"
```

### 3. API 调用

#### 直接调用诊断模块（推荐）

```python
from lumina_skills.diagnosis import diagnose_account

result = await diagnose_account(
    account_url="https://www.douyin.com/user/xxx",
    platform="douyin",
    user_id="user_123",
    use_crawler=True,  # 启用 RPA 抓取
)

print(result["health_score"])  # 健康分
print(result["account_gene"])  # 账号基因
print(result["key_issues"])    # 关键问题
```

#### 调用 Skill

```python
from skill_rpa_executor.main import execute_task, RPATaskInput

result = await execute_task(RPATaskInput(
    task_type="crawl_account",
    account_id="user_123",
    platform="douyin",
    params={
        "account_url": "https://www.douyin.com/user/xxx",
        "platform": "douyin",
        "max_contents": 10,
    },
    user_id="user_123",
))

print(result.result_data)
```

## 技术架构

```
用户请求
    ↓
diagnose_account (lumina_skills)
    ↓
_try_crawl_account
    ↓ (尝试直接导入 RPA)
AccountCrawler
    ↓
BrowserGrid (Playwright + 反检测)
    ↓
抖音/小红书 网页
    ↓
数据解析器
    ↓
convert_to_diagnosis_format
    ↓
诊断报告
```

## 核心组件

### 1. AccountCrawler (`apps/rpa/src/rpa/account_crawler.py`)

主抓取器类，负责：
- 浏览器会话管理
- 页面导航和滚动
- 数据提取和解析
- 结果格式化

```python
from rpa.account_crawler import AccountCrawler, RateLimiter

browser_grid = BrowserGrid(max_instances=5, headless=True)
rate_limiter = RateLimiter(default_delay=3.0)
crawler = AccountCrawler(browser_grid, rate_limiter)

result = await crawler.crawl_account(
    account_url="https://www.douyin.com/user/xxx",
    platform="douyin",
    max_contents=10,
)
```

### 2. 反检测层 (`apps/rpa/src/rpa/anti_detection.py`)

- 随机 User-Agent
- 屏幕分辨率伪装
- Canvas/WebGL 指纹噪声
- Webdriver 标记隐藏

### 3. 速率限制器 (`RateLimiter`)

```python
rate_limiter = RateLimiter(
    default_delay=3.0,              # 默认请求间隔
    platform_delays={               # 平台特定延迟
        "douyin": 4.0,
        "xiaohongshu": 3.5,
    },
    max_requests_per_minute=8,      # 每分钟最大请求数
)
```

### 4. 数据解析器

自动解析：
- 账号昵称、简介
- 粉丝数、关注数、获赞数
- 作品列表（标题、点赞数）
- 内容类型和风格标签

## 抓取的数据结构

```python
{
    "platform": "douyin",
    "account_id": "xxx",
    "nickname": "用户昵称",
    "bio": "个人简介",
    "followers": 50000,       # 粉丝数
    "following": 100,         # 关注数
    "likes": 100000,          # 获赞数
    "content_count": 50,      # 作品数
    "recent_contents": [      # 最近作品
        {
            "title": "作品标题",
            "likes": 1000,
            "platform": "douyin"
        }
    ],
    "content_tags": ["lifestyle", "tutorial"],  # 内容类型
    "crawl_status": "success",  # pending, success, partial, failed
    "crawled_at": "2024-01-01T12:00:00",
}
```

## 诊断报告格式

```python
{
    "ok": True,
    "data_source": "rpa_crawler",
    "crawl_status": "success",
    "account_gene": {
        "content_types": ["tutorial", "lifestyle"],
        "style_tags": ["干货", "亲和"],
        "audience_sketch": "18-35 岁女性为主（基于内容推测）",
        "nickname": "用户昵称",
        "bio": "个人简介",
    },
    "health_score": 72.5,
    "key_issues": [
        "更新频率不稳定",
        "互动率偏低",
    ],
    "improvement_suggestions": [
        {"area": "content", "tip": "当前内容数 50，建议保持稳定更新节奏"},
        {"area": "engagement", "tip": "当前互动率约 3.2%，可通过优化开头 3 秒提升"},
    ],
    "recommended_methodology": "aida_advanced",
    "metrics": {
        "followers": 50000,
        "following": 100,
        "likes": 100000,
        "content_count": 50,
        "engagement_rate_estimate": 3.2,
    },
    "content_samples": [...],  # 最近 5 条内容
    "platform": "douyin",
}
```

## 配置选项

### 环境变量

```bash
# 代理配置（可选）
export PROXY_HOST="proxy.example.com"
export PROXY_PORT="8080"
export PROXY_USERNAME="user"
export PROXY_PASSWORD="pass"

# 会话存储路径
export SESSION_STORAGE="./data/sessions"

# 调试模式（显示浏览器窗口）
export RPA_HEADLESS="false"
```

### diagnose_account 参数

```python
await diagnose_account(
    account_url="https://...",      # 账号主页 URL
    platform="douyin",              # 平台类型
    user_id="user_123",             # 用户ID
    analysis_depth="standard",      # 分析深度: basic/standard/deep
    use_crawler=True,               # 是否启用 RPA 抓取
    rpa_config={                    # RPA 配置（可选）
        "endpoint": "http://localhost:8000/rpa/crawl",
    },
)
```

## 注意事项

### 1. 法律合规

- 仅抓取**公开的**账号信息
- 遵守平台 Terms of Service
- 建议仅用于分析**自己的**账号

### 2. 反爬对抗

平台可能采取的反制措施：
- 验证码/滑块验证
- IP 封禁
- 登录态检查
- 行为检测

应对策略：
- 自动限流（已内置）
- 代理轮换（需配置）
- Cookie 持久化（已内置）
- 指纹伪装（已内置）

### 3. 稳定性建议

- 首次使用先测试少量账号
- 观察触发风控的频率
- 必要时手动验证账号
- 准备数据回退方案

## 故障排查

### 抓取失败

```bash
# 检查浏览器安装
playwright install chromium

# 测试浏览器能否启动
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); print('OK'); b.close(); p.stop()"
```

### 返回空数据

- 可能是页面结构变化，需要更新选择器
- 账号可能被限制访问
- 检查网络连接和代理设置

### 频繁触发验证码

- 增加 `default_delay` 值
- 使用代理池轮换 IP
- 降低抓取频率

## 后续优化方向

1. **验证码识别**: 集成 2Captcha 等打码服务
2. **更多平台**: 支持 B站、快手等
3. **数据缓存**: 缓存已抓取数据，减少重复请求
4. **增量更新**: 只抓取变化的数据
5. **数据持久化**: 将抓取结果存入数据库

## 相关文件

- `apps/rpa/src/rpa/account_crawler.py` - 主抓取器
- `apps/rpa/src/rpa/browser_grid.py` - 浏览器管理
- `apps/rpa/src/rpa/anti_detection.py` - 反检测
- `skills/skill-rpa-executor/src/skill_rpa_executor/main.py` - Skill 实现
- `packages/lumina-skills/src/lumina_skills/diagnosis.py` - 诊断集成
- `scripts/test_crawler_manual.py` - 手动测试脚本
