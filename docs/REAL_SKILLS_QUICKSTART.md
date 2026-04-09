# Skill 真实实现快速开始

## 环境准备

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip install playwright aiohttp litellm

# 安装浏览器（用于 RPA）
playwright install chromium
```

### 2. 配置环境变量

```bash
# LLM 配置（必需）
export OPENAI_API_KEY="sk-..."
# 或使用通用配置
export LLM_PROVIDER="openai"
export LLM_MODEL="gpt-4o-mini"
export LLM_API_KEY="sk-..."

# 外部 API（可选）
export NEWSAPI_KEY="..."  # 从 https://newsapi.org/ 获取

# 调试（可选）
export RPA_HEADLESS="false"  # 显示浏览器窗口用于调试
```

---

## 快速测试

```bash
# 运行完整测试
python scripts/test_all_skills.py

# 测试 RPA 抓取
python scripts/test_crawler_manual.py --platform douyin --account "目标账号"
```

---

## 使用示例

### 1. 账号诊断（RPA 真实抓取）

```python
import asyncio
from lumina_skills.diagnosis import diagnose_account

async def main():
    result = await diagnose_account(
        account_url="https://www.douyin.com/user/xxx",
        platform="douyin",
        user_id="user_123",
        use_crawler=True,
    )
    
    print(f"健康分: {result['health_score']}")
    print(f"粉丝数: {result['metrics']['followers']}")
    print(f"数据来源: {result['data_source']}")  # "rpa_crawler"

asyncio.run(main())
```

### 2. 生成文案（LLM）

```python
from skill_creative_studio.main import generate_text, TextGenerationInput

async def main():
    result = await generate_text(TextGenerationInput(
        topic="如何提升工作效率",
        platform="xiaohongshu",
        content_type="post",
        tone="friendly",
        user_id="user_123"
    ))
    
    print(result.title)
    print(result.content)
    print(result.hashtags)

asyncio.run(main())
```

### 3. 竞品分析（RPA + LLM）

```python
from skill_content_strategist.main import analyze_competitor_real

async def main():
    result = await analyze_competitor_real(
        competitor_id="目标账号ID",
        platform="douyin",
        analysis_depth="standard",
        user_id="user_123"
    )
    
    print(f"竞品昵称: {result['overview']['nickname']}")
    print(f"粉丝数: {result['overview']['follower_count']}")
    print(f"最近内容: {result['content_analysis']['recent_contents']}")

asyncio.run(main())
```

### 4. 账号养号（RPA）

```python
from skill_account_keeper.main import daily_maintenance

async def main():
    result = await daily_maintenance(
        account_ids=["account_1", "account_2"],
        platforms=["douyin", "xiaohongshu"],
        maintenance_type="light",  # light/standard/intensive
        user_id="user_123"
    )
    
    for r in result["results"]:
        print(f"{r['account_id']}: {r['status']}, 操作{r['actions_performed']}次")

asyncio.run(main())
```

### 5. 获取行业新闻

```python
from lumina_skills.tool_skills import fetch_industry_news

async def main():
    news = await fetch_industry_news(category="美妆", days=3)
    
    for item in news["news_list"]:
        print(f"- {item['title']}")

asyncio.run(main())
```

---

## 配置文件

### LLM 配置（config/llm.yaml）

```yaml
llm_pool:
  gpt4o:
    provider: openai
    model: gpt-4o
    api_key: ${OPENAI_API_KEY}
    temperature: 0.7
    max_tokens: 2000
  
  gpt4o_mini:
    provider: openai
    model: gpt-4o-mini
    api_key: ${OPENAI_API_KEY}
    temperature: 0.8
    max_tokens: 2000

default_llm: gpt4o_mini

skill_config:
  content_strategist:
    llm: gpt4o
    temperature: 0.7
  creative_studio:
    llm: gpt4o_mini
    temperature: 0.8
  knowledge_miner:
    llm: gpt4o
    temperature: 0.7
```

---

## 故障排查

### LLM 不工作
```bash
# 检查环境变量
echo $OPENAI_API_KEY

# 测试
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### RPA 不工作
```bash
# 检查浏览器安装
playwright install chromium

# 测试浏览器启动
python -c "
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.chromium.launch()
print('浏览器启动成功')
b.close()
p.stop()
"
```

### Cookie 登录
1. 手动登录目标平台
2. 导出 Cookie（使用浏览器扩展如 EditThisCookie）
3. 导入到系统

```python
from skill_account_keeper.main import import_cookies

await import_cookies(
    account_id="my_douyin_account",
    platform="douyin",
    cookies=[...],  # 从浏览器导出的 cookie 列表
    user_id="user_123"
)
```

---

## 性能优化

### 1. 会话复用
RPA 会自动保存和复用会话，第一次较慢（需启动浏览器），后续较快。

### 2. 并发限制
使用 `RateLimiter` 自动控制并发，避免触发平台风控。

### 3. 缓存建议
```python
# 对 RPA 结果进行缓存
from functools import lru_cache
import time

_cache = {}

async def get_cached_account_data(account_url, max_age=3600):
    key = account_url
    now = time.time()
    
    if key in _cache:
        data, timestamp = _cache[key]
        if now - timestamp < max_age:
            return data
    
    # 重新抓取
    data = await crawl_account(account_url, ...)
    _cache[key] = (data, now)
    return data
```

---

## 安全注意事项

1. **Cookie 安全**: 导出的 Cookie 包含登录凭证，请妥善保管
2. **速率限制**: RPA 已内置限流，但仍需注意不要频繁抓取
3. **平台规则**: 遵守平台 ToS，仅抓取公开数据
4. **API Key**: 不要在代码中硬编码 API Key，使用环境变量
