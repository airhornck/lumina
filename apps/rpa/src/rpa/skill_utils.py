"""
RPA Skill 工具集

为需要浏览器自动化的 Skill 提供统一的 RPA 调用接口
"""

from __future__ import annotations

import asyncio
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
            
            # 小红书需要 Cookie 登录，先加载 Cookie
            if platform == "xiaohongshu":
                await self._load_xiaohongshu_cookies(session.page)
            
            # 根据数据类型访问不同页面
            urls = {
                "trends": {
                    "douyin": "https://www.douyin.com/discover",
                    "xiaohongshu": "https://www.xiaohongshu.com/explore",
                },
                "hot_topics": {
                    "douyin": "https://www.douyin.com/hot",
                    "xiaohongshu": "https://www.xiaohongshu.com/search_result?keyword=热门",
                    "bilibili": "https://www.bilibili.com/v/popular/all",
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
            
            await session.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # 针对动态渲染页面，增加更长的等待时间
            # 并尝试滚动页面触发懒加载
            await asyncio.sleep(5)
            await session.page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(3)
            
            # 使用 Playwright 的 query_selector_all 而不是 JS evaluate
            # 因为 Playwright 可以更好地处理动态渲染
            hot_topics = []
            
            if platform == "douyin":
                hot_topics = await self._extract_douyin_hot(session.page)
            elif platform == "xiaohongshu":
                hot_topics = await self._extract_xiaohongshu_hot(session.page)
            elif platform == "bilibili":
                hot_topics = await self._extract_bilibili_hot(session.page)
            
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
    
    async def _extract_douyin_hot(self, page) -> List[Dict[str, Any]]:
        """提取抖音热榜"""
        topics = []
        
        # 抖音热榜页: 从 li 元素中提取视频信息
        # 文本格式通常是: 时长 标题 #话题 @UP主 发布时间
        try:
            elements = await page.query_selector_all("li")
            for el in elements[:30]:
                try:
                    text = await el.text_content()
                    if not text:
                        continue
                    text = text.strip()
                    
                    # 过滤条件
                    if len(text) < 10 or len(text) > 100:
                        continue
                    if text.startswith("http"):
                        continue
                    
                    # 清理文本: 去掉时长前缀 (00:12, 01:23 等)
                    import re
                    cleaned = re.sub(r'^\d{2}:\d{2}', '', text).strip()
                    # 去掉数字前缀 (播放量等)
                    cleaned = re.sub(r'^\d+\.?\d*[万k]?', '', cleaned).strip()
                    
                    # 提取话题标签
                    hashtags = re.findall(r'#([^\s#]+)', cleaned)
                    # 提取标题部分（@之前的文本）
                    title_part = cleaned.split("@")[0].strip()
                    # 去掉末尾的时间描述
                    title_part = re.sub(r'\d+[天小时分钟]+前$', '', title_part).strip()
                    
                    if len(title_part) > 5 and not any(t["title"] == title_part for t in topics):
                        topics.append({
                            "title": title_part,
                            "rank": len(topics) + 1,
                            "hashtags": hashtags[:5],
                            "raw": text[:100],
                        })
                except Exception:
                    continue
        except Exception:
            pass
        
        return topics[:15]
    
    async def _load_xiaohongshu_cookies(self, page) -> None:
        """加载小红书 Cookie"""
        try:
            from pathlib import Path
            # skill_utils.py 位于 apps/rpa/src/rpa/，需要上溯4层到项目根目录
            cookie_file = Path(__file__).resolve().parents[4] / "data" / "credentials" / "xiaohongshu_cookies.txt"
            if cookie_file.exists():
                cookie_str = cookie_file.read_text().strip()
                cookies = []
                for item in cookie_str.split("; "):
                    if "=" in item:
                        name, value = item.split("=", 1)
                        cookies.append({
                            "name": name.strip(),
                            "value": value.strip(),
                            "domain": ".xiaohongshu.com",
                            "path": "/",
                        })
                await page.context.add_cookies(cookies)
                print(f"[RPA] 小红书Cookie已加载，共 {len(cookies)} 条")
            else:
                print(f"[RPA] 小红书Cookie文件不存在: {cookie_file}")
        except Exception as e:
            print(f"[RPA] 加载小红书Cookie失败: {e}")
    
    async def _extract_xiaohongshu_hot(self, page) -> List[Dict[str, Any]]:
        """提取小红书热门"""
        topics = []
        
        # 需要过滤掉的页脚/法律文本关键词
        skip_keywords = [
            "ICP", "备案", "许可证", "营业执照", "增值电信",
            "医疗器械", "网络文化", "药品信息", "互联网医院",
            "网安备", "12345", "青少年", "举报", "扫黄打非",
            "不良信息", "广告", "侵权", "隐私", "协议",
        ]
        
        # 小红书搜索页: 笔记标题策略
        # Cookie 登录后，笔记标题主要在 span 元素中
        strategies = [
            # 策略1: 笔记卡片中的 span（小红书标题通常在 span 中）
            {
                "selector": 'span',
            },
            # 策略2: 搜索笔记链接
            {
                "selector": 'a[href*="/explore/"]',
            },
            # 策略3: 包含 title 属性的元素
            {
                "selector": '[title]',
            },
            # 策略4: 通用内容卡片
            {
                "selector": 'div[class*="note"]',
            },
            # 策略5: section 中的文本（小红书常用 section 布局）
            {
                "selector": 'section',
            },
        ]
        
        for strategy in strategies:
            try:
                elements = await page.query_selector_all(strategy["selector"])
                for idx, el in enumerate(elements[:60]):
                    try:
                        text = await el.text_content()
                        if not text:
                            continue
                        text = text.strip()
                        
                        # 过滤条件: 放宽长度限制
                        if len(text) < 8 or len(text) > 80:
                            continue
                        
                        # 过滤页脚法律文本
                        if any(kw in text for kw in skip_keywords):
                            continue
                        
                        # 过滤纯数字
                        if text.replace(".", "").isdigit():
                            continue
                        
                        # 过滤无意义的短文本（按钮文字、导航等）
                        meaningless = [
                            "分享", "收藏", "评论", "点赞", "关注", "更多", "收起", "展开",
                            "登录", "注册", "首页", "发现", "购物", "消息", "我",
                            "获取验证码", "手机号登录", "密码登录", "其他登录方式",
                        ]
                        if text in meaningless:
                            continue
                        
                        # 过滤过短的纯中文（如"阅读","笔记"等）
                        if len(text) < 10 and text in ["阅读", "笔记", "收藏", "喜欢"]:
                            continue
                        
                        if not any(t["title"] == text for t in topics):
                            topics.append({
                                "title": text,
                                "rank": len(topics) + 1,
                            })
                    except Exception:
                        continue
                if len(topics) >= 5:
                    break
            except Exception:
                continue
        
        return topics[:15]
    
    async def _extract_bilibili_hot(self, page) -> List[Dict[str, Any]]:
        """提取B站热门"""
        topics = []
        
        # B站热门页: 视频列表结构
        # 从调试可以看到: 标题 + UP主 + 播放量 + 弹幕数
        # B站热门视频卡片通常在 .video-card 或特定结构中
        
        # 需要过滤的导航/提示文字
        skip_words = [
            "首页", "番剧", "直播", "游戏中心", "会员购", "下载APP",
            "登录", "注册", "历史", "收藏", "消息", "创作中心", "投稿",
            "每周必看", "全站排行榜", "排行榜", "排行榜解析", "排行榜规则",
            "关闭", "bilibili", "关于我们", "联系我们", "用户协议", "隐私政策",
        ]
        
        # 策略: 先尝试提取视频卡片中的标题
        # B站热门页的视频卡片结构通常是:
        # <div class="video-card">...<a href="/video/BVxxx"><h3>标题</h3></a>...</div>
        strategies = [
            # 策略1: h3 标签（B站视频标题常用）
            {
                "selector": 'h3',
            },
            # 策略2: 视频卡片中的链接
            {
                "selector": 'a[href*="/video/"]',
            },
            # 策略3: B站视频列表项
            {
                "selector": '.video-card, [class*="card"]',
            },
            # 策略4: 所有较长的文本内容
            {
                "selector": 'span, div',
            },
        ]
        
        for strategy in strategies:
            try:
                elements = await page.query_selector_all(strategy["selector"])
                for idx, el in enumerate(elements[:40]):
                    try:
                        text = await el.text_content()
                        if not text:
                            continue
                        text = text.strip()
                        
                        # 过滤条件
                        if len(text) < 8 or len(text) > 100:
                            continue
                        
                        # 过滤导航/菜单/提示文字
                        if any(sw in text for sw in skip_words):
                            continue
                        
                        # 过滤纯数字（播放量等）
                        if text.replace(".", "").replace("万", "").isdigit():
                            continue
                        
                        # 过滤过短的无意义文本
                        if len(text.replace(" ", "").replace("\n", "")) < 8:
                            continue
                        
                        if not any(t["title"] == text for t in topics):
                            topics.append({
                                "title": text,
                                "rank": len(topics) + 1,
                            })
                    except Exception:
                        continue
                if len(topics) >= 5:
                    break
            except Exception:
                continue
        
        return topics[:15]
    
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
