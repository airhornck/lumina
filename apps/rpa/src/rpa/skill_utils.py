"""
RPA Skill 工具集

为需要浏览器自动化的 Skill 提供统一的 RPA 调用接口
"""

from __future__ import annotations

from typing import Any, Dict, Optional, List
from dataclasses import dataclass


@dataclass
class RPAResult:
    """RPA 执行结果"""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    screenshot: Optional[str] = None


class RPASkillHelper:
    """
    RPA Skill 辅助类
    
    为 Skill 提供简化的 RPA 调用接口
    """
    
    def __init__(self):
        self._browser_grid = None
        self._rate_limiter = None
        self._crawler = None
    
    async def _get_browser_grid(self):
        """获取或创建 BrowserGrid"""
        if self._browser_grid is None:
            from rpa.browser_grid import BrowserGrid
            self._browser_grid = BrowserGrid(
                max_instances=5,
                headless=True,  # 生产环境使用无头模式
            )
            await self._browser_grid.initialize()
        return self._browser_grid
    
    async def _get_rate_limiter(self):
        """获取或创建 RateLimiter"""
        if self._rate_limiter is None:
            from rpa.account_crawler import RateLimiter
            self._rate_limiter = RateLimiter(
                default_delay=3.0,
                platform_delays={
                    "douyin": 4.0,
                    "xiaohongshu": 3.5,
                    "bilibili": 3.0,
                    "kuaishou": 3.5,
                },
                max_requests_per_minute=8,
            )
        return self._rate_limiter
    
    async def _get_crawler(self):
        """获取或创建 AccountCrawler"""
        if self._crawler is None:
            from rpa.account_crawler import AccountCrawler
            browser_grid = await self._get_browser_grid()
            rate_limiter = await self._get_rate_limiter()
            self._crawler = AccountCrawler(browser_grid, rate_limiter)
        return self._crawler
    
    async def crawl_account(
        self,
        account_url: str,
        platform: str,
        account_id: str,
        user_id: str,
        max_contents: int = 10,
    ) -> RPAResult:
        """
        抓取账号数据
        
        Args:
            account_url: 账号主页 URL
            platform: 平台类型
            account_id: 账号标识
            user_id: 用户ID
            max_contents: 最大抓取内容数
            
        Returns:
            RPA 执行结果
        """
        try:
            crawler = await self._get_crawler()
            
            result = await crawler.crawl_account(
                account_url=account_url,
                platform=platform,
                account_id=account_id,
                user_id=user_id,
                max_contents=max_contents,
            )
            
            from rpa.account_crawler import convert_to_diagnosis_format
            
            return RPAResult(
                success=result.crawl_status in ["success", "partial"],
                data={
                    "platform": result.platform,
                    "account_id": result.account_id,
                    "nickname": result.nickname,
                    "bio": result.bio,
                    "followers": result.followers,
                    "following": result.following,
                    "likes": result.likes,
                    "content_count": result.content_count,
                    "recent_contents": result.recent_contents,
                    "diagnosis": convert_to_diagnosis_format(result),
                    "crawl_status": result.crawl_status,
                    "crawled_at": result.crawled_at,
                },
                error=result.error_message,
            )
            
        except Exception as e:
            return RPAResult(
                success=False,
                data={},
                error=str(e),
            )
    
    async def check_account_login(
        self,
        platform: str,
        account_id: str,
        cookies: Optional[List[Dict]] = None,
    ) -> RPAResult:
        """
        检查账号登录状态
        
        Args:
            platform: 平台类型
            account_id: 账号ID
            cookies: 可选的 Cookie 列表
            
        Returns:
            RPA 执行结果
        """
        try:
            browser_grid = await self._get_browser_grid()
            
            # 创建会话
            session = await browser_grid.create_session(
                account_id=account_id,
                platform=platform,
            )
            
            # 访问平台首页检查登录状态
            platform_urls = {
                "douyin": "https://www.douyin.com",
                "xiaohongshu": "https://www.xiaohongshu.com",
                "bilibili": "https://www.bilibili.com",
                "kuaishou": "https://www.kuaishou.com",
            }
            
            url = platform_urls.get(platform, "https://www.douyin.com")
            await session.page.goto(url, wait_until="networkidle")
            
            # 检查登录状态（通过查找特定元素）
            login_selectors = {
                "douyin": "[data-e2e='user-name'], .avatar, .user-name",
                "xiaohongshu": ".user-name, .avatar, [class*='user']",
                "bilibili": ".user-name, .avatar, .login-panel",
                "kuaishou": ".user-name, .avatar",
            }
            
            selector = login_selectors.get(platform, "")
            is_logged_in = False
            
            if selector:
                try:
                    element = await session.page.wait_for_selector(
                        selector, timeout=5000
                    )
                    is_logged_in = element is not None
                except Exception:
                    is_logged_in = False
            
            # 获取页面信息
            page_info = await session.page.evaluate("""
                () => ({
                    title: document.title,
                    url: window.location.href,
                })
            """)
            
            await browser_grid.close_session(account_id, save_state=True)
            
            return RPAResult(
                success=True,
                data={
                    "platform": platform,
                    "account_id": account_id,
                    "is_logged_in": is_logged_in,
                    "page_title": page_info.get("title"),
                    "page_url": page_info.get("url"),
                    "checked_at": __import__('datetime').datetime.now().isoformat(),
                },
            )
            
        except Exception as e:
            return RPAResult(
                success=False,
                data={},
                error=str(e),
            )
    
    async def perform_daily_maintenance(
        self,
        platform: str,
        account_id: str,
        maintenance_type: str = "light",
    ) -> RPAResult:
        """
        执行日常养号操作
        
        Args:
            platform: 平台类型
            account_id: 账号ID
            maintenance_type: light/standard/intensive
            
        Returns:
            RPA 执行结果
        """
        try:
            browser_grid = await self._get_browser_grid()
            rate_limiter = await self._get_rate_limiter()
            
            # 速率限制
            await rate_limiter.acquire(platform)
            
            # 创建会话
            session = await browser_grid.create_session(
                account_id=account_id,
                platform=platform,
            )
            
            # 定义养号策略
            strategies = {
                "light": {"browse_time": 300, "interactions": 3},  # 5分钟
                "standard": {"browse_time": 900, "interactions": 8},  # 15分钟
                "intensive": {"browse_time": 1800, "interactions": 15},  # 30分钟
            }
            
            strategy = strategies.get(maintenance_type, strategies["light"])
            
            # 访问推荐页
            platform_feeds = {
                "douyin": "https://www.douyin.com/recommend",
                "xiaohongshu": "https://www.xiaohongshu.com/explore",
                "bilibili": "https://www.bilibili.com",
                "kuaishou": "https://www.kuaishou.com",
            }
            
            feed_url = platform_feeds.get(platform, "https://www.douyin.com")
            await session.page.goto(feed_url, wait_until="networkidle")
            
            # 模拟浏览行为
            import asyncio
            import random
            
            actions_performed = []
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < strategy["browse_time"]:
                # 滚动
                await session.page.evaluate(
                    f"window.scrollBy(0, {random.randint(500, 1000)})"
                )
                await asyncio.sleep(random.uniform(2, 5))
                
                # 偶尔点击（模拟观看）
                if random.random() < 0.3 and len(actions_performed) < strategy["interactions"]:
                    try:
                        # 尝试点击内容
                        content_selectors = [
                            "[data-e2e='card']",
                            ".video-card",
                            ".feed-card",
                            "a[href*='/video/']",
                        ]
                        
                        for selector in content_selectors:
                            try:
                                elements = await session.page.query_selector_all(selector)
                                if elements:
                                    await elements[0].click()
                                    actions_performed.append({"action": "click_content", "time": asyncio.get_event_loop().time() - start_time})
                                    await asyncio.sleep(random.uniform(5, 10))
                                    await session.page.go_back()
                                    break
                            except Exception:
                                continue
                    except Exception:
                        pass
                
                # 偶尔点赞（更小的概率）
                if random.random() < 0.1 and len(actions_performed) < strategy["interactions"]:
                    actions_performed.append({"action": "like", "time": asyncio.get_event_loop().time() - start_time})
            
            await browser_grid.close_session(account_id, save_state=True)
            
            return RPAResult(
                success=True,
                data={
                    "platform": platform,
                    "account_id": account_id,
                    "maintenance_type": maintenance_type,
                    "browse_duration": strategy["browse_time"],
                    "actions_performed": len(actions_performed),
                    "actions_detail": actions_performed,
                    "completed_at": __import__('datetime').datetime.now().isoformat(),
                },
            )
            
        except Exception as e:
            return RPAResult(
                success=False,
                data={},
                error=str(e),
            )
    
    async def fetch_platform_data(
        self,
        platform: str,
        data_type: str,
        account_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> RPAResult:
        """
        获取平台数据（趋势、热门等）
        
        Args:
            platform: 平台类型
            data_type: 数据类型 (trends, hot_topics, rankings)
            account_id: 账号ID
            params: 额外参数
            
        Returns:
            RPA 执行结果
        """
        try:
            browser_grid = await self._get_browser_grid()
            
            session = await browser_grid.create_session(
                account_id=account_id,
                platform=platform,
            )
            
            # 根据数据类型访问不同页面
            urls = {
                "trends": {
                    "douyin": "https://www.douyin.com/discover",
                    "xiaohongshu": "https://www.xiaohongshu.com/explore",
                },
                "hot_topics": {
                    "douyin": "https://www.douyin.com/hot",
                    "xiaohongshu": "https://www.xiaohongshu.com/search_result?keyword=热门",
                },
            }
            
            platform_urls = urls.get(data_type, {})
            url = platform_urls.get(platform)
            
            if not url:
                return RPAResult(
                    success=False,
                    data={},
                    error=f"不支持的数据类型: {data_type}",
                )
            
            await session.page.goto(url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            # 提取热门话题/趋势
            hot_topics = await session.page.evaluate("""
                () => {
                    const topics = [];
                    // 尝试多种选择器
                    const selectors = [
                        '[data-e2e="hot-topic"]',
                        '.hot-topic',
                        '.trend-item',
                        '[class*="hot"]',
                        '[class*="trend"]',
                    ];
                    
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach((el, idx) => {
                            if (idx < 10) {
                                const text = el.textContent || '';
                                if (text && text.length < 50) {
                                    topics.push({
                                        title: text.trim(),
                                        rank: idx + 1,
                                    });
                                }
                            }
                        });
                        if (topics.length > 0) break;
                    }
                    
                    return topics;
                }
            """)
            
            await browser_grid.close_session(account_id, save_state=True)
            
            return RPAResult(
                success=True,
                data={
                    "platform": platform,
                    "data_type": data_type,
                    "hot_topics": hot_topics,
                    "fetched_at": __import__('datetime').datetime.now().isoformat(),
                },
            )
            
        except Exception as e:
            return RPAResult(
                success=False,
                data={},
                error=str(e),
            )
    
    async def close(self):
        """关闭所有资源"""
        if self._browser_grid:
            await self._browser_grid.close()
            self._browser_grid = None
            self._crawler = None


# 全局辅助实例
_rpa_helper: Optional[RPASkillHelper] = None


def get_rpa_helper() -> RPASkillHelper:
    """获取全局 RPA 辅助实例"""
    global _rpa_helper
    if _rpa_helper is None:
        _rpa_helper = RPASkillHelper()
    return _rpa_helper


async def close_rpa_helper():
    """关闭全局 RPA 辅助实例"""
    global _rpa_helper
    if _rpa_helper:
        await _rpa_helper.close()
        _rpa_helper = None
