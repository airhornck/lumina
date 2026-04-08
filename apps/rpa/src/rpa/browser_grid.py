"""
浏览器网格

管理无头浏览器池，支持多账号并发
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from .anti_detection import AntiDetectionLayer, BrowserFingerprint
from .session_manager import SessionManager
from .proxy_manager import ProxyManager


@dataclass
class BrowserSession:
    """浏览器会话"""
    browser: Any  # Playwright Browser
    context: Any  # Playwright BrowserContext
    page: Any  # Playwright Page
    account_id: str
    proxy: Optional[Any] = None
    fingerprint: Optional[BrowserFingerprint] = None


class BrowserGrid:
    """
    浏览器网格管理器
    
    特性：
    - 动态浏览器池管理
    - 多账号并发支持
    - 自动指纹伪装
    - Cookie 隔离
    """
    
    def __init__(
        self,
        max_instances: int = 50,
        headless: bool = True,
        session_storage: str = "./data/sessions"
    ):
        """
        初始化
        
        Args:
            max_instances: 最大浏览器实例数
            headless: 是否无头模式
            session_storage: 会话数据存储路径
        """
        self.max_instances = max_instances
        self.headless = headless
        
        # 组件初始化
        self.anti_detect = AntiDetectionLayer()
        self.session_mgr = SessionManager(session_storage)
        self.proxy_mgr = ProxyManager()
        
        # 状态管理
        self._playwright = None
        self._active_sessions: Dict[str, BrowserSession] = {}
        self._instance_count = 0
    
    async def initialize(self) -> None:
        """初始化 Playwright"""
        from playwright.async_api import async_playwright
        
        self._playwright = await async_playwright().start()
    
    async def close(self) -> None:
        """关闭所有浏览器"""
        # 关闭所有会话
        for session in self._active_sessions.values():
            await session.context.close()
        
        self._active_sessions.clear()
        
        # 停止 Playwright
        if self._playwright:
            await self._playwright.stop()
    
    async def create_session(
        self,
        account_id: str,
        platform: str,
        location: Optional[str] = None
    ) -> BrowserSession:
        """
        创建浏览器会话
        
        Args:
            account_id: 账号ID
            platform: 平台类型
            location: 代理位置
        
        Returns:
            浏览器会话
        """
        if not self._playwright:
            await self.initialize()
        
        # 检查是否已有会话
        if account_id in self._active_sessions:
            return self._active_sessions[account_id]
        
        # 检查实例限制
        if len(self._active_sessions) >= self.max_instances:
            raise RuntimeError(f"Max browser instances reached: {self.max_instances}")
        
        # 生成指纹
        fingerprint = self.anti_detect.generate_fingerprint(seed=account_id)
        
        # 分配代理
        proxy = await self.proxy_mgr.allocate(account_id, location)
        
        # 创建浏览器上下文
        browser_type = self._playwright.chromium
        
        # 浏览器启动参数
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
        ]
        
        browser = await browser_type.launch(
            headless=self.headless,
            args=args,
            proxy={"server": proxy.server} if proxy else None
        )
        
        # 创建上下文
        context = await browser.new_context(
            viewport={
                "width": int(fingerprint.screen_resolution.split("x")[0]),
                "height": int(fingerprint.screen_resolution.split("x")[1])
            },
            user_agent=fingerprint.user_agent,
            locale=fingerprint.language,
            timezone_id=fingerprint.timezone,
        )
        
        # 加载 Cookie
        cookies = await self.session_mgr.load_cookies(account_id)
        if cookies:
            await context.add_cookies(cookies)
        
        # 创建页面并应用反检测
        page = await context.new_page()
        await self.anti_detect.apply(page, fingerprint)
        
        # 创建会话对象
        session = BrowserSession(
            browser=browser,
            context=context,
            page=page,
            account_id=account_id,
            proxy=proxy,
            fingerprint=fingerprint
        )
        
        # 记录会话
        self._active_sessions[account_id] = session
        
        return session
    
    async def close_session(self, account_id: str, save_state: bool = True) -> None:
        """
        关闭浏览器会话
        
        Args:
            account_id: 账号ID
            save_state: 是否保存会话状态
        """
        if account_id not in self._active_sessions:
            return
        
        session = self._active_sessions[account_id]
        
        if save_state:
            # 保存 Cookie
            cookies = await session.context.cookies()
            await self.session_mgr.save_cookies(account_id, cookies)
        
        # 关闭上下文
        await session.context.close()
        await session.browser.close()
        
        # 释放代理
        self.proxy_mgr.release(account_id)
        
        # 移除会话
        del self._active_sessions[account_id]
    
    @asynccontextmanager
    async def session(
        self,
        account_id: str,
        platform: str,
        location: Optional[str] = None
    ):
        """上下文管理器方式的会话"""
        session = await self.create_session(account_id, platform, location)
        try:
            yield session
        finally:
            await self.close_session(account_id)
    
    async def get_session(self, account_id: str) -> Optional[BrowserSession]:
        """获取已存在的会话"""
        return self._active_sessions.get(account_id)
    
    async def list_active_sessions(self) -> List[str]:
        """列出所有活跃会话"""
        return list(self._active_sessions.keys())
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "active_sessions": len(self._active_sessions),
            "max_instances": self.max_instances,
            "proxy_health": await self.proxy_mgr.health_check()
        }
