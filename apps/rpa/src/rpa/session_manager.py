"""
Session 管理器

管理账号的 Cookie、LocalStorage 等会话数据
"""

from __future__ import annotations

import json
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any


class SessionManager:
    """
    Session 管理器
    
    负责：
    - Cookie 持久化存储
    - 登录态健康检查
    - 自动重新登录
    """
    
    def __init__(self, storage_path: str = "./data/sessions", encryption_key: Optional[str] = None):
        """
        初始化
        
        Args:
            storage_path: 会话数据存储路径
            encryption_key: 加密密钥（可选）
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.encryption_key = encryption_key
    
    def _get_session_file(self, account_id: str) -> Path:
        """获取会话文件路径"""
        return self.storage_path / f"{account_id}.json"
    
    async def load_cookies(self, account_id: str) -> list:
        """
        加载账号的 Cookie
        
        Args:
            account_id: 账号ID
        
        Returns:
            Cookie 列表
        """
        session_file = self._get_session_file(account_id)
        
        if not session_file.exists():
            return []
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cookies = data.get("cookies", [])
            
            # 检查 Cookie 是否过期
            valid_cookies = []
            for cookie in cookies:
                expires = cookie.get("expires")
                if expires:
                    expire_time = datetime.fromtimestamp(expires)
                    if expire_time > datetime.now():
                        valid_cookies.append(cookie)
                else:
                    valid_cookies.append(cookie)
            
            return valid_cookies
            
        except Exception:
            return []
    
    async def save_cookies(self, account_id: str, cookies: list) -> None:
        """
        保存账号的 Cookie
        
        Args:
            account_id: 账号ID
            cookies: Cookie 列表
        """
        session_file = self._get_session_file(account_id)
        
        data = {
            "account_id": account_id,
            "cookies": cookies,
            "updated_at": datetime.now().isoformat(),
        }
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    async def load_local_storage(self, account_id: str) -> Dict[str, Any]:
        """加载 LocalStorage"""
        session_file = self._get_session_file(account_id)
        
        if not session_file.exists():
            return {}
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("local_storage", {})
        except Exception:
            return {}
    
    async def save_local_storage(self, account_id: str, storage: Dict[str, Any]) -> None:
        """保存 LocalStorage"""
        session_file = self._get_session_file(account_id)
        
        # 读取现有数据
        data = {}
        if session_file.exists():
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        # 更新 LocalStorage
        data["local_storage"] = storage
        data["updated_at"] = datetime.now().isoformat()
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    async def is_session_valid(self, account_id: str, platform: str) -> bool:
        """
        检查会话是否有效
        
        Args:
            account_id: 账号ID
            platform: 平台类型
        
        Returns:
            会话是否有效
        """
        cookies = await self.load_cookies(account_id)
        
        if not cookies:
            return False
        
        # 检查是否有核心的登录态 Cookie
        essential_cookies = self._get_essential_cookies(platform)
        cookie_names = {c.get("name") for c in cookies}
        
        # 至少有一个核心 Cookie 存在
        return bool(essential_cookies & cookie_names)
    
    def _get_essential_cookies(self, platform: str) -> set:
        """获取平台的核心 Cookie 名称"""
        essential = {
            "xiaohongshu": {"session_id", "web_session", "user_id"},
            "douyin": {"sessionid", "sid_guard"},
            "bilibili": {"SESSDATA", "bili_jct"},
            "kuaishou": {"did", "userId"},
        }
        return essential.get(platform, set())
    
    async def clear_session(self, account_id: str) -> None:
        """清除会话数据"""
        session_file = self._get_session_file(account_id)
        if session_file.exists():
            session_file.unlink()
