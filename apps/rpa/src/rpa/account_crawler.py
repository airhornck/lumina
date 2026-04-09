"""
账号数据抓取器

通过无头浏览器抓取抖音、小红书等平台账号信息
"""

from __future__ import annotations

import re
import json
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from urllib.parse import urljoin, urlparse


@dataclass
class CrawledAccountData:
    """抓取的账号数据结构"""
    platform: str
    account_id: str
    nickname: str = ""
    avatar: str = ""
    bio: str = ""
    followers: int = 0
    following: int = 0
    likes: int = 0  # 获赞数
    content_count: int = 0  # 作品数
    
    # 内容分析
    recent_contents: List[Dict[str, Any]] = field(default_factory=list)
    
    # 标签/风格
    content_tags: List[str] = field(default_factory=list)
    
    # 原始数据
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    crawled_at: str = field(default_factory=lambda: datetime.now().isoformat())
    crawl_status: str = "pending"  # pending, success, partial, failed
    error_message: Optional[str] = None
    requires_login: bool = False  # 新增：是否需要登录


class AccountCrawler:
    """
    账号数据抓取器
    
    支持平台：
    - 抖音 (douyin)
    - 小红书 (xiaohongshu)
    
    特点：
    - 自动识别平台
    - 反检测对抗
    - 数据缓存
    - 失败重试
    """
    
    # 平台配置
    PLATFORM_CONFIG = {
        "douyin": {
            "name": "抖音",
            "domain": "douyin.com",
            "user_url_template": "https://www.douyin.com/user/{user_id}",
            "search_url_template": "https://www.douyin.com/search/{keyword}?type=user",
        },
        "xiaohongshu": {
            "name": "小红书",
            "domain": "xiaohongshu.com",
            "user_url_template": "https://www.xiaohongshu.com/user/profile/{user_id}",
            "search_url_template": "https://www.xiaohongshu.com/search_result?keyword={keyword}&type=user",
        },
    }
    
    def __init__(self, browser_grid, rate_limiter=None):
        """
        初始化抓取器
        
        Args:
            browser_grid: BrowserGrid 实例
            rate_limiter: 速率限制器（可选）
        """
        self.browser_grid = browser_grid
        self.rate_limiter = rate_limiter
        self._parsers: Dict[str, Callable] = {
            "douyin": self._parse_douyin,
            "xiaohongshu": self._parse_xiaohongshu,
        }
    
    async def crawl_account(
        self,
        account_url: str,
        platform: str,
        account_id: str = None,
        user_id: str = None,
        max_contents: int = 10,
        cookies: Optional[List[Dict[str, Any]]] = None,
    ) -> CrawledAccountData:
        """
        抓取账号数据
        
        Args:
            account_url: 账号主页 URL（可选，如果没有则通过账号名搜索）
            platform: 平台类型
            account_id: 账号唯一标识
            user_id: 用户ID（用于会话管理）
            max_contents: 最大抓取内容数量
            cookies: 可选的 Cookie 列表用于认证
            
        Returns:
            抓取结果
        """
        result = CrawledAccountData(
            platform=platform,
            account_id=account_id or "unknown",
        )
        
        # 速率限制检查
        if self.rate_limiter:
            await self.rate_limiter.acquire(platform)
        
        session = None
        try:
            # 创建浏览器会话（传入 cookies 如果提供）
            session = await self.browser_grid.create_session(
                account_id=user_id or "crawler",
                platform=platform,
                cookies=cookies,
            )
            
            # 访问账号页面
            if account_url:
                # 使用更宽松的加载策略（抖音/小红书有大量资源）
                try:
                    await session.page.goto(account_url, wait_until="domcontentloaded", timeout=20000)
                except Exception:
                    # 如果 domcontentloaded 也超时，就继续执行
                    pass
                # 额外等待一会儿让 JS 执行
                await asyncio.sleep(3)
            else:
                # 通过搜索查找账号
                await self._search_account(session.page, account_id, platform)
            
            # 检查是否需要登录
            current_url = session.page.url
            print(f"[crawl_account] 当前页面URL: {current_url}")
            
            # 检查是否是登录页面或搜索页面（未跳转）
            if "/login" in current_url or "/search" in current_url:
                result.requires_login = True
                result.crawl_status = "partial"
                result.error_message = "需要登录才能查看完整内容。建议：1) 提供 Cookie 登录；2) 直接提供账号主页链接"
                
                # 尝试从搜索页面提取一些信息
                await self._extract_from_search_page(session.page, result)
                return result
            
            # 等待页面加载
            await asyncio.sleep(2)
            
            # 滚动加载更多内容
            await self._scroll_load(session.page, scroll_times=3)
            
            # 解析数据
            parser = self._parsers.get(platform)
            if parser:
                result = await parser(session.page, result)
            else:
                result.crawl_status = "failed"
                result.error_message = f"不支持的平台: {platform}"
            
            # 限制内容数量
            if len(result.recent_contents) > max_contents:
                result.recent_contents = result.recent_contents[:max_contents]
                
        except Exception as e:
            result.crawl_status = "failed"
            result.error_message = str(e)
            
        finally:
            if session:
                await self.browser_grid.close_session(user_id or "crawler", save_state=True)
        
        return result
    
    async def _extract_from_search_page(self, page, result: CrawledAccountData):
        """从搜索页面提取有限的信息"""
        try:
            # 尝试提取搜索结果中的第一个用户信息
            search_data = await page.evaluate("""
                () => {
                    const users = [];
                    // 抖音搜索页用户卡片
                    const cards = document.querySelectorAll('[data-e2e="search-card-user"], .B6JkCp0k, [class*="search-card"]');
                    cards.forEach((card, idx) => {
                        if (idx < 3) {
                            const nameEl = card.querySelector('[data-e2e="search-card-user-name"], .N6JkCp0k, h6, .nickname');
                            const descEl = card.querySelector('[data-e2e="search-card-user-desc"], .desc');
                            const linkEl = card.querySelector('a[href*="/user/"]');
                            
                            if (nameEl) {
                                users.push({
                                    nickname: nameEl.textContent?.trim() || '',
                                    desc: descEl?.textContent?.trim() || '',
                                    link: linkEl?.href || ''
                                });
                            }
                        }
                    });
                    return {
                        users: users,
                        title: document.title,
                        url: window.location.href
                    };
                }
            """)
            
            result.raw_data = {"search_page_data": search_data}
            
            # 如果有搜索结果，提取第一个
            users = search_data.get("users", [])
            if users:
                result.nickname = users[0].get("nickname", "")
                result.bio = users[0].get("desc", "")
                result.crawl_status = "partial"
            else:
                # 可能是被重定向到登录页了
                if "login" in search_data.get("url", "") or "sso" in search_data.get("url", ""):
                    result.requires_login = True
                    result.error_message = "抖音需要登录才能查看搜索结果。请提供 Cookie 或直接提供账号主页链接"
                else:
                    result.error_message = "未找到搜索结果，可能需要登录"
                    
        except Exception as e:
            result.error_message = f"搜索页面解析失败: {e}"
    
    async def _search_account(self, page, account_name: str, platform: str):
        """通过搜索查找账号"""
        config = self.PLATFORM_CONFIG.get(platform)
        if not config:
            raise ValueError(f"不支持的平台: {platform}")
        
        search_url = config["search_url_template"].format(keyword=account_name)
        
        # 使用更宽松的加载策略
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass  # 即使超时也继续
        
        await asyncio.sleep(5)  # 等待 JS 渲染搜索结果
        
        # 点击第一个搜索结果
        if platform == "douyin":
            # 抖音搜索结果的多种可能选择器
            selectors = [
                '[data-e2e="search-card-user"] a',
                '.search-result-card a',
                '[class*="search"] a[href*="/user/"]',
                'a[href*="/user/"]',
            ]
        elif platform == "xiaohongshu":
            selectors = [
                '.user-item a',
                '.search-user-item a',
                'a[href*="/user/profile/"]',
            ]
        else:
            selectors = ['a[href*="/user/"]']
        
        # 尝试多个选择器
        clicked = False
        for selector in selectors:
            try:
                # 等待元素出现
                await page.wait_for_selector(selector, timeout=5000)
                await page.click(selector)
                # 等待页面跳转
                await asyncio.sleep(3)
                clicked = True
                break
            except Exception:
                continue
        
        if not clicked:
            # 如果点击失败，截图保存用于调试
            try:
                await page.screenshot(path=f"search_failed_{platform}.png")
            except Exception:
                pass
            # 不抛出异常，让调用者检查当前URL
    
    async def _scroll_load(self, page, scroll_times: int = 3, delay: float = 1.5):
        """滚动页面加载更多内容"""
        for i in range(scroll_times):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(delay)
    
    async def _parse_douyin(self, page, result: CrawledAccountData) -> CrawledAccountData:
        """解析抖音页面"""
        try:
            # 尝试从页面脚本中提取数据
            page_data = await page.evaluate("""
                () => {
                    // 尝试获取 SSR 数据
                    const ssrData = window._SSR_HYDRATED_DATA || window.__INITIAL_STATE__ || {};
                    
                    // 从 DOM 提取
                    const nickname = document.querySelector('[data-e2e="user-name"]')?.textContent || 
                                    document.querySelector('.lC6iS6P0')?.textContent ||
                                    document.querySelector('h1')?.textContent || '';
                    
                    const bio = document.querySelector('[data-e2e="user-signature"]')?.textContent || 
                               document.querySelector('.kOqN4al3')?.textContent || '';
                    
                    // 提取数字（粉丝、关注、获赞）
                    const stats = document.querySelectorAll('[data-e2e="user-tab-count"], .YxgsjAbE');
                    const numbers = [];
                    stats.forEach(el => {
                        const text = el.textContent || '';
                        numbers.push(text);
                    });
                    
                    // 提取作品
                    const contents = [];
                    const contentEls = document.querySelectorAll('[data-e2e="user-post-item"], .video-card');
                    contentEls.forEach((el, idx) => {
                        if (idx < 10) {
                            const title = el.querySelector('.title, .desc')?.textContent || '';
                            const likes = el.querySelector('.like-count, .count')?.textContent || '0';
                            contents.push({title: title.slice(0, 100), likes_text: likes});
                        }
                    });
                    
                    return {
                        ssrData: ssrData,
                        nickname: nickname.trim(),
                        bio: bio.trim(),
                        stats: numbers,
                        contents: contents,
                        html: document.body.innerHTML.slice(0, 5000)
                    };
                }
            """)
            
            result.raw_data = page_data
            
            # 解析昵称
            if page_data.get('nickname'):
                result.nickname = page_data['nickname']
            
            # 解析简介
            if page_data.get('bio'):
                result.bio = page_data['bio']
            
            # 解析统计数据
            stats = page_data.get('stats', [])
            if len(stats) >= 3:
                result.following = self._parse_number(stats[0])
                result.followers = self._parse_number(stats[1])
                result.likes = self._parse_number(stats[2])
            
            # 解析作品
            for content in page_data.get('contents', []):
                result.recent_contents.append({
                    "title": content.get("title", ""),
                    "likes_text": content.get("likes_text", "0"),
                    "platform": "douyin"
                })
            
            result.content_count = len(result.recent_contents)
            
            # 尝试从 SSR 数据解析（更可靠）
            ssr_data = page_data.get('ssrData', {})
            if ssr_data:
                await self._extract_from_ssr_douyin(ssr_data, result)
            
            # 确定状态
            if result.nickname and result.followers > 0:
                result.crawl_status = "success"
            elif result.nickname:
                result.crawl_status = "partial"
            else:
                result.crawl_status = "partial"
                result.error_message = "未能提取到完整的账号信息，可能需要登录"
            
        except Exception as e:
            result.crawl_status = "failed"
            result.error_message = f"解析失败: {str(e)}"
        
        return result
    
    async def _extract_from_ssr_douyin(self, ssr_data: Dict, result: CrawledAccountData):
        """从抖音 SSR 数据中提取信息"""
        try:
            # 抖音数据通常在 user 或 app 字段中
            user_data = ssr_data.get('user', {}) or ssr_data.get('app', {}).get('user', {})
            
            if user_data:
                info = user_data.get('info', {})
                if info:
                    result.nickname = info.get('nickname', result.nickname)
                    result.bio = info.get('signature', result.bio)
                    result.followers = info.get('follower_count', result.followers)
                    result.following = info.get('following_count', result.following)
                    result.likes = info.get('total_favorited', result.likes)
                    result.content_count = info.get('aweme_count', result.content_count)
                    
                # 提取内容
                posts = user_data.get('post', {}).get('data', [])
                if posts:
                    result.recent_contents = []
                    for post in posts[:10]:
                        desc = post.get('desc', '')
                        stats = post.get('stats', {})
                        result.recent_contents.append({
                            "title": desc[:100],
                            "likes": stats.get('digg_count', 0),
                            "comments": stats.get('comment_count', 0),
                            "shares": stats.get('share_count', 0),
                            "platform": "douyin"
                        })
        except Exception:
            pass
    
    async def _parse_xiaohongshu(self, page, result: CrawledAccountData) -> CrawledAccountData:
        """解析小红书页面"""
        try:
            page_data = await page.evaluate("""
                () => {
                    // 尝试获取初始数据
                    const initialData = window.__INITIAL_STATE__ || window._SSR_HYDRATED_DATA || {};
                    
                    // 从 DOM 提取
                    const nickname = document.querySelector('.nickname, .user-nickname')?.textContent || 
                                    document.querySelector('h1')?.textContent || '';
                    
                    const bio = document.querySelector('.desc, .user-desc')?.textContent || '';
                    
                    // 提取统计数字
                    const stats = document.querySelectorAll('.stats-num, .count');
                    const numbers = [];
                    stats.forEach(el => {
                        numbers.push(el.textContent || '');
                    });
                    
                    // 提取笔记
                    const contents = [];
                    const noteEls = document.querySelectorAll('.note-item, .feed-card');
                    noteEls.forEach((el, idx) => {
                        if (idx < 10) {
                            const title = el.querySelector('.title, .note-title')?.textContent || '';
                            const likes = el.querySelector('.like-count, .count')?.textContent || '0';
                            contents.push({title: title.slice(0, 100), likes: likes});
                        }
                    });
                    
                    return {
                        initialData: initialData,
                        nickname: nickname.trim(),
                        bio: bio.trim(),
                        stats: numbers,
                        contents: contents
                    };
                }
            """)
            
            result.raw_data = page_data
            
            if page_data.get('nickname'):
                result.nickname = page_data['nickname']
            if page_data.get('bio'):
                result.bio = page_data['bio']
            
            stats = page_data.get('stats', [])
            if len(stats) >= 3:
                result.followers = self._parse_number(stats[0])
                result.following = self._parse_number(stats[1])
                result.likes = self._parse_number(stats[2])
            
            for content in page_data.get('contents', []):
                result.recent_contents.append({
                    "title": content.get("title", ""),
                    "likes_text": content.get("likes", "0"),
                    "platform": "xiaohongshu"
                })
            
            result.content_count = len(result.recent_contents)
            
            # 尝试从 SSR 数据解析
            initial_data = page_data.get('initialData', {})
            if initial_data:
                await self._extract_from_ssr_xiaohongshu(initial_data, result)
            
            # 确定状态
            if result.nickname and result.followers > 0:
                result.crawl_status = "success"
            elif result.nickname:
                result.crawl_status = "partial"
            else:
                result.crawl_status = "partial"
                result.error_message = "未能提取到完整的账号信息"
            
        except Exception as e:
            result.crawl_status = "failed"
            result.error_message = f"解析失败: {str(e)}"
        
        return result
    
    async def _extract_from_ssr_xiaohongshu(self, initial_data: Dict, result: CrawledAccountData):
        """从小红书 SSR 数据中提取信息"""
        try:
            user_data = initial_data.get('user', {}).get('userPageData', {})
            
            if user_data:
                basic_info = user_data.get('basicInfo', {})
                if basic_info:
                    result.nickname = basic_info.get('nickname', result.nickname)
                    result.bio = basic_info.get('desc', result.bio)
                    result.followers = basic_info.get('fans', result.followers)
                    result.following = basic_info.get('follows', result.following)
                    result.likes = basic_info.get('liked', result.likes)
                
                # 提取笔记
                notes = user_data.get('notes', [])
                if notes:
                    result.recent_contents = []
                    for note in notes[:10]:
                        result.recent_contents.append({
                            "title": note.get('title', '')[:100],
                            "likes": note.get('likes', 0),
                            "platform": "xiaohongshu"
                        })
        except Exception:
            pass
    
    def _parse_number(self, text: str) -> int:
        """解析数字文本（支持 w/万 单位）"""
        if not text:
            return 0
        
        text = str(text).strip().replace(',', '')
        
        # 匹配数字
        match = re.match(r'^([\d.]+)', text)
        if not match:
            return 0
        
        num = float(match.group(1))
        
        # 处理单位
        if 'w' in text.lower() or '万' in text:
            num *= 10000
        elif 'k' in text.lower():
            num *= 1000
        
        return int(num)


class RateLimiter:
    """
    速率限制器
    
    防止请求过快触发平台风控
    """
    
    def __init__(
        self,
        default_delay: float = 3.0,
        platform_delays: Optional[Dict[str, float]] = None,
        max_requests_per_minute: int = 10,
    ):
        """
        初始化
        
        Args:
            default_delay: 默认请求间隔（秒）
            platform_delays: 各平台特定延迟
            max_requests_per_minute: 每分钟最大请求数
        """
        self.default_delay = default_delay
        self.platform_delays = platform_delays or {}
        self.max_requests_per_minute = max_requests_per_minute
        
        self._last_request_time: Dict[str, float] = {}
        self._request_counts: Dict[str, List[float]] = {}
    
    async def acquire(self, platform: str = "default"):
        """
        获取请求许可
        
        Args:
            platform: 平台标识
        """
        import time
        
        now = time.time()
        
        # 获取平台特定延迟
        delay = self.platform_delays.get(platform, self.default_delay)
        
        # 检查上次请求时间
        last_time = self._last_request_time.get(platform, 0)
        elapsed = now - last_time
        
        if elapsed < delay:
            wait_time = delay - elapsed
            await asyncio.sleep(wait_time)
            now = time.time()
        
        # 检查每分钟请求数限制
        if platform not in self._request_counts:
            self._request_counts[platform] = []
        
        # 清理一分钟前的记录
        cutoff = now - 60
        self._request_counts[platform] = [
            t for t in self._request_counts[platform] if t > cutoff
        ]
        
        # 如果超过限制，等待
        if len(self._request_counts[platform]) >= self.max_requests_per_minute:
            sleep_time = 60 - (now - self._request_counts[platform][0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                now = time.time()
        
        # 记录本次请求
        self._last_request_time[platform] = now
        self._request_counts[platform].append(now)


def convert_to_diagnosis_format(crawled: CrawledAccountData) -> Dict[str, Any]:
    """
    将抓取数据转换为诊断模块格式
    
    Args:
        crawled: 抓取结果
        
    Returns:
        诊断模块可用的数据格式
    """
    # 计算互动率
    engagement_rate = 0.0
    if crawled.followers > 0 and crawled.likes > 0:
        # 估算互动率 = 总获赞 / 粉丝数 / 作品数
        engagement_rate = min(100.0, crawled.likes / max(crawled.followers, 1) / max(crawled.content_count, 1) * 100)
    
    # 分析内容类型
    content_types = set()
    for content in crawled.recent_contents:
        title = content.get("title", "").lower()
        if any(kw in title for kw in ["教程", "如何", "怎么", "攻略", "教学"]):
            content_types.add("tutorial")
        elif any(kw in title for kw in ["日常", "vlog", "生活", "今天"]):
            content_types.add("lifestyle")
        elif any(kw in title for kw in ["美食", "吃", "餐厅", "菜谱"]):
            content_types.add("food")
        elif any(kw in title for kw in ["穿搭", "衣服", "时尚", "ootd"]):
            content_types.add("fashion")
        elif any(kw in title for kw in ["旅行", "旅游", "酒店", "景点"]):
            content_types.add("travel")
    
    if not content_types:
        content_types.add("general")
    
    # 生成风格标签
    style_tags = []
    if crawled.bio:
        bio_lower = crawled.bio.lower()
        if any(kw in bio_lower for kw in ["干货", "分享", "知识"]):
            style_tags.append("干货")
        if any(kw in bio_lower for kw in ["搞笑", "幽默", "段子"]):
            style_tags.append("幽默")
        if any(kw in bio_lower for kw in ["温暖", "治愈", "正能量"]):
            style_tags.append("亲和")
    
    if not style_tags:
        style_tags = ["真实"]
    
    # 计算健康分
    health_score = 50.0
    if crawled.followers > 10000:
        health_score += 15
    if crawled.content_count > 30:
        health_score += 10
    if engagement_rate > 5:
        health_score += 15
    elif engagement_rate > 2:
        health_score += 5
    health_score = min(100.0, health_score)
    
    # 识别问题
    key_issues = []
    if crawled.content_count < 10:
        key_issues.append("内容数量较少，建议增加发布频率")
    if engagement_rate < 2:
        key_issues.append("互动率偏低，建议优化内容质量或互动引导")
    if not crawled.bio:
        key_issues.append("个人简介为空，建议完善账号信息")
    
    if not key_issues:
        key_issues = ["更新频率不稳定", "内容同质化风险"]
    
    result = {
        "account_gene": {
            "content_types": list(content_types),
            "style_tags": style_tags,
            "audience_sketch": "18-35 岁女性为主（基于内容推测）",
            "nickname": crawled.nickname,
            "bio": crawled.bio,
        },
        "health_score": round(health_score, 1),
        "key_issues": key_issues[:2],
        "improvement_suggestions": [
            {"area": "content", "tip": f"当前内容数 {crawled.content_count}，建议保持稳定更新节奏"},
            {"area": "engagement", "tip": f"当前互动率约 {engagement_rate:.1f}%，可通过优化开头 3 秒提升"},
        ],
        "recommended_methodology": "aida_advanced",
        "raw_metrics": {
            "followers": crawled.followers,
            "following": crawled.following,
            "likes": crawled.likes,
            "content_count": crawled.content_count,
            "engagement_rate_estimate": round(engagement_rate, 2),
        },
        "recent_contents": crawled.recent_contents[:5],
        "platform": crawled.platform,
        "crawled_at": crawled.crawled_at,
        "crawl_status": crawled.crawl_status,
    }
    
    # 如果需要登录，添加提示
    if crawled.requires_login:
        result["requires_login"] = True
        result["login_help"] = "抖音搜索需要登录才能查看完整内容。建议：1) 提供 Cookie 文件；2) 直接提供账号主页链接（如 https://www.douyin.com/user/xxx）"
    
    return result
