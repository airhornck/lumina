"""
代理管理器

管理 IP 代理池，为每个账号分配独立的代理
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class Proxy:
    """代理配置"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"
    location: Optional[str] = None
    last_used: Optional[datetime] = None
    fail_count: int = 0
    
    @property
    def url(self) -> str:
        """获取代理 URL"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"
    
    @property
    def server(self) -> str:
        """获取 Playwright 格式的 server"""
        return f"{self.protocol}://{self.host}:{self.port}"


class ProxyManager:
    """
    代理管理器
    
    负责：
    - 代理池管理
    - IP 分配
    - 健康检测
    - 失败处理
    """
    
    def __init__(self):
        self.proxies: Dict[str, List[Proxy]] = {}  # location -> proxies
        self.account_proxy_map: Dict[str, Proxy] = {}  # account_id -> proxy
        self._init_default_proxies()
    
    def _init_default_proxies(self) -> None:
        """初始化默认代理（实际使用时从配置文件或 API 加载）"""
        # 这里可以集成第三方代理服务
        # 如：Bright Data, Oxylabs, Smartproxy 等
        pass
    
    def add_proxy(self, proxy: Proxy, location: Optional[str] = None) -> None:
        """
        添加代理到池
        
        Args:
            proxy: 代理配置
            location: 地理位置（可选）
        """
        loc = location or "default"
        if loc not in self.proxies:
            self.proxies[loc] = []
        self.proxies[loc].append(proxy)
    
    def add_proxies_from_config(self, config: List[Dict]) -> None:
        """从配置加载代理列表"""
        for item in config:
            proxy = Proxy(
                host=item["host"],
                port=item["port"],
                username=item.get("username"),
                password=item.get("password"),
                protocol=item.get("protocol", "http"),
                location=item.get("location"),
            )
            self.add_proxy(proxy, proxy.location)
    
    async def allocate(self, account_id: str, location: Optional[str] = None) -> Optional[Proxy]:
        """
        为账号分配代理
        
        Args:
            account_id: 账号ID
            location: 期望的地理位置
        
        Returns:
            分配的代理
        """
        # 检查是否已有分配
        if account_id in self.account_proxy_map:
            return self.account_proxy_map[account_id]
        
        # 选择代理池
        if location and location in self.proxies:
            pool = self.proxies[location]
        else:
            # 使用默认池
            pool = self.proxies.get("default", [])
        
        if not pool:
            return None
        
        # 选择失败次数最少的代理
        available = [p for p in pool if p.fail_count < 3]
        if not available:
            # 重置所有失败计数
            for p in pool:
                p.fail_count = 0
            available = pool
        
        # 随机选择
        proxy = random.choice(available)
        proxy.last_used = datetime.now()
        
        # 记录分配
        self.account_proxy_map[account_id] = proxy
        
        return proxy
    
    def release(self, account_id: str) -> None:
        """释放代理"""
        if account_id in self.account_proxy_map:
            del self.account_proxy_map[account_id]
    
    def report_failure(self, account_id: str) -> None:
        """报告代理失败"""
        if account_id in self.account_proxy_map:
            proxy = self.account_proxy_map[account_id]
            proxy.fail_count += 1
            
            # 失败次数过多时更换代理
            if proxy.fail_count >= 3:
                self.release(account_id)
    
    async def health_check(self) -> Dict[str, int]:
        """
        健康检查
        
        Returns:
            各位置可用代理数量
        """
        result = {}
        for location, proxies in self.proxies.items():
            healthy = sum(1 for p in proxies if p.fail_count < 3)
            result[location] = healthy
        return result
