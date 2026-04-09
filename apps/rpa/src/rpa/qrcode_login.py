"""
二维码登录系统

支持在 Chat 中展示二维码，用户扫码登录后自动保存凭证
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable


class LoginStatus(Enum):
    """登录状态"""
    PENDING = "pending"       # 等待扫码
    SCANNED = "scanned"       # 已扫码
    CONFIRMED = "confirmed"   # 登录成功
    EXPIRED = "expired"       # 二维码过期
    ERROR = "error"           # 错误


@dataclass
class QRCodeSession:
    """二维码登录会话"""
    session_id: str
    platform: str
    user_id: str
    status: LoginStatus
    qr_code_base64: str = ""  # 二维码图片Base64
    qr_content: str = ""      # 二维码内容（URL）
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=5))
    confirmed_at: Optional[datetime] = None
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    account_info: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


@dataclass
class PlatformCredential:
    """平台凭证"""
    platform: str
    account_id: str
    account_name: str
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = ""
    is_active: bool = True


@dataclass
class UserCredentials:
    """用户凭证集合"""
    user_id: str
    encryption_key: str = field(default_factory=lambda: secrets.token_hex(32))
    platforms: Dict[str, PlatformCredential] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class SecureStorage:
    """加密存储"""
    
    def __init__(self, storage_path: str = "./data/credentials"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._master_key = self._load_or_create_master_key()
    
    def _load_or_create_master_key(self) -> bytes:
        key_file = self.storage_path / ".master_key"
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return base64.b64decode(f.read())
        key = secrets.token_bytes(32)
        with open(key_file, 'wb') as f:
            f.write(base64.b64encode(key))
        # 设置文件权限（仅当前用户可读写）
        import os
        os.chmod(key_file, 0o600)
        return key
    
    def _simple_encrypt(self, data: str, key: str) -> str:
        """简化加密（生产环境应使用AES-256-GCM）"""
        full_key = hashlib.sha256((self._master_key.hex() + key).encode()).digest()
        data_bytes = data.encode('utf-8')
        encrypted = bytearray()
        for i, b in enumerate(data_bytes):
            encrypted.append(b ^ full_key[i % len(full_key)])
        return base64.b64encode(bytes(encrypted)).decode()
    
    def _simple_decrypt(self, encrypted: str, key: str) -> str:
        """简化解密"""
        full_key = hashlib.sha256((self._master_key.hex() + key).encode()).digest()
        data_bytes = base64.b64decode(encrypted)
        decrypted = bytearray()
        for i, b in enumerate(data_bytes):
            decrypted.append(b ^ full_key[i % len(full_key)])
        return bytes(decrypted).decode('utf-8')
    
    def save(self, user_creds: UserCredentials) -> bool:
        """保存用户凭证"""
        try:
            file_path = self.storage_path / f"{user_creds.user_id}.json"
            data = asdict(user_creds)
            
            # 加密敏感字段
            for platform, cred in data.get("platforms", {}).items():
                if cred.get("cookies"):
                    cookies_json = json.dumps(cred["cookies"], ensure_ascii=False)
                    cred["cookies"] = self._simple_encrypt(cookies_json, user_creds.encryption_key)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 设置文件权限
            import os
            os.chmod(file_path, 0o600)
            return True
        except Exception as e:
            print(f"[SecureStorage] 保存失败: {e}")
            return False
    
    def load(self, user_id: str) -> Optional[UserCredentials]:
        """加载用户凭证"""
        try:
            file_path = self.storage_path / f"{user_id}.json"
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            user_key = data.get("encryption_key", "")
            
            # 解密
            for platform, cred in data.get("platforms", {}).items():
                if isinstance(cred.get("cookies"), str):
                    try:
                        decrypted = self._simple_decrypt(cred["cookies"], user_key)
                        cred["cookies"] = json.loads(decrypted)
                    except Exception:
                        cred["cookies"] = []
            
            return UserCredentials(**data)
        except Exception as e:
            print(f"[SecureStorage] 加载失败: {e}")
            return None


class QRCodeLoginManager:
    """二维码登录管理器"""
    
    def __init__(self):
        self.sessions: Dict[str, QRCodeSession] = {}
        self.storage = SecureStorage()
        self._polling_tasks: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        # 启动清理任务
        asyncio.create_task(self._cleanup_expired_sessions())
    
    async def create_login_session(
        self,
        platform: str,
        user_id: str,
    ) -> QRCodeSession:
        """
        创建二维码登录会话
        
        实际实现中需要：
        1. 启动浏览器访问登录页
        2. 获取二维码URL
        3. 生成二维码图片
        """
        session_id = str(uuid.uuid4())
        
        # 这里先模拟一个二维码，实际应该调用浏览器获取真实二维码
        # 模拟数据
        qr_content = f"https://www.douyin.com/login?token={session_id}"
        qr_base64 = await self._generate_qr_code(qr_content)
        
        session = QRCodeSession(
            session_id=session_id,
            platform=platform,
            user_id=user_id,
            status=LoginStatus.PENDING,
            qr_code_base64=qr_base64,
            qr_content=qr_content,
        )
        
        self.sessions[session_id] = session
        
        # 启动轮询任务（实际应调用平台API轮询）
        # 这里用BrowserGrid实现真实登录流程
        asyncio.create_task(self._start_browser_login(session_id, platform))
        
        return session
    
    async def _generate_qr_code(self, content: str) -> str:
        """生成二维码图片"""
        try:
            import qrcode
            from io import BytesIO
            
            qr = qrcode.QRCode(
                version=3,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(content)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode()
        except ImportError:
            # 如果没有qrcode库，返回提示
            return ""
    
    async def _start_browser_login(self, session_id: str, platform: str):
        """
        启动浏览器进行真实登录流程
        
        这是一个完整的浏览器自动化流程：
        1. 打开登录页
        2. 获取二维码
        3. 等待用户扫码
        4. 获取登录后的Cookie
        """
        from rpa.browser_grid import BrowserGrid
        from rpa.account_crawler import RateLimiter
        
        browser_grid = BrowserGrid(max_instances=1, headless=False)  # 非无头模式方便调试
        session = self.sessions.get(session_id)
        
        if not session:
            return
        
        try:
            # 创建浏览器会话
            browser_session = await browser_grid.create_session(
                account_id=session_id,
                platform=platform,
            )
            
            # 访问登录页
            if platform == "douyin":
                login_url = "https://www.douyin.com/login"
            elif platform == "xiaohongshu":
                login_url = "https://www.xiaohongshu.com/sign_in"
            else:
                login_url = "https://www.douyin.com/login"
            
            await browser_session.page.goto(login_url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            # 查找并截图二维码
            # 实际页面结构可能不同，需要根据真实页面调整
            qr_selector = "[class*='qrcode'], [class*='qr-code'], img[src*='qrcode']"
            
            try:
                qr_element = await browser_session.page.wait_for_selector(qr_selector, timeout=10000)
                if qr_element:
                    # 截图二维码区域
                    qr_screenshot = await qr_element.screenshot()
                    qr_base64 = base64.b64encode(qr_screenshot).decode()
                    
                    # 更新会话
                    session.qr_code_base64 = qr_base64
                    
                    print(f"[QRCodeLogin] 二维码已生成，等待用户扫码: {session_id}")
            except Exception as e:
                print(f"[QRCodeLogin] 未找到二维码元素，尝试整页截图: {e}")
                # 整页截图让用户自己找二维码
                page_screenshot = await browser_session.page.screenshot()
                session.qr_code_base64 = base64.b64encode(page_screenshot).decode()
            
            # 等待扫码（轮询检测登录状态）
            max_wait = 300  # 最多等5分钟
            for i in range(max_wait):
                await asyncio.sleep(1)
                
                # 检查当前URL是否已跳转到首页（登录成功）
                current_url = browser_session.page.url
                
                # 登录成功后URL会变化
                if "/login" not in current_url and "/sign_in" not in current_url:
                    # 登录成功
                    print(f"[QRCodeLogin] 登录成功: {session_id}")
                    
                    # 获取Cookie
                    cookies = await browser_session.context.cookies()
                    
                    # 获取账号信息
                    account_info = await self._extract_account_info(
                        browser_session.page, platform
                    )
                    
                    # 更新会话
                    session.status = LoginStatus.CONFIRMED
                    session.confirmed_at = datetime.now()
                    session.cookies = cookies
                    session.account_info = account_info
                    
                    # 保存凭证
                    await self._save_credentials(session)
                    
                    # 触发回调
                    await self._notify_status_change(session_id, "confirmed")
                    
                    break
                
                # 检查会话是否被取消
                if session.status == LoginStatus.ERROR:
                    break
            else:
                # 超时
                session.status = LoginStatus.EXPIRED
                session.error_message = "二维码已过期，请重新获取"
                await self._notify_status_change(session_id, "expired")
            
        except Exception as e:
            session.status = LoginStatus.ERROR
            session.error_message = str(e)
            await self._notify_status_change(session_id, "error")
        finally:
            await browser_grid.close()
    
    async def _extract_account_info(self, page, platform: str) -> Dict[str, Any]:
        """提取账号信息"""
        try:
            if platform == "douyin":
                # 访问个人主页获取信息
                await page.goto("https://www.douyin.com/user/self", wait_until="networkidle")
                await asyncio.sleep(2)
                
                info = await page.evaluate("""
                    () => {
                        const nickname = document.querySelector('[data-e2e="user-name"]')?.textContent || '';
                        const avatar = document.querySelector('[data-e2e="user-avatar"] img')?.src || '';
                        return { nickname, avatar };
                    }
                """)
                
                return {
                    "account_id": "self",  # 实际应从页面提取
                    "nickname": info.get("nickname", "未知"),
                    "avatar": info.get("avatar", ""),
                }
            
            elif platform == "xiaohongshu":
                # 小红书逻辑类似
                return {
                    "account_id": "self",
                    "nickname": "小红书用户",
                    "avatar": "",
                }
            
        except Exception as e:
            print(f"[_extract_account_info] 提取失败: {e}")
        
        return {"account_id": "unknown", "nickname": "未知用户", "avatar": ""}
    
    async def _save_credentials(self, session: QRCodeSession):
        """保存登录凭证"""
        user_creds = self.storage.load(session.user_id)
        
        if not user_creds:
            user_creds = UserCredentials(user_id=session.user_id)
        
        # 创建平台凭证
        cred = PlatformCredential(
            platform=session.platform,
            account_id=session.account_info.get("account_id", ""),
            account_name=session.account_info.get("nickname", ""),
            cookies=session.cookies,
            expires_at=(datetime.now() + timedelta(days=30)).isoformat(),
        )
        
        user_creds.platforms[session.platform] = cred
        self.storage.save(user_creds)
        
        print(f"[QRCodeLogin] 凭证已保存: {session.user_id}/{session.platform}")
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "platform": session.platform,
            "status": session.status.value,
            "qr_code": session.qr_code_base64 if session.status == LoginStatus.PENDING else None,
            "account_info": session.account_info if session.status == LoginStatus.CONFIRMED else None,
            "expires_in": int((session.expires_at - datetime.now()).total_seconds()),
        }
    
    async def wait_for_login(self, session_id: str, timeout: int = 300) -> bool:
        """等待登录完成"""
        for i in range(timeout):
            session = self.sessions.get(session_id)
            if not session:
                return False
            
            if session.status == LoginStatus.CONFIRMED:
                return True
            
            if session.status in [LoginStatus.EXPIRED, LoginStatus.ERROR]:
                return False
            
            await asyncio.sleep(1)
        
        return False
    
    async def get_user_credential(self, user_id: str, platform: str) -> Optional[PlatformCredential]:
        """获取用户保存的凭证"""
        user_creds = self.storage.load(user_id)
        if not user_creds:
            return None
        
        cred = user_creds.platforms.get(platform)
        if not cred or not cred.is_active:
            return None
        
        # 检查是否过期
        if cred.expires_at:
            expires = datetime.fromisoformat(cred.expires_at)
            if datetime.now() > expires:
                cred.is_active = False
                return None
        
        return cred
    
    async def check_and_refresh_login(self, user_id: str, platform: str) -> Dict[str, Any]:
        """
        检查并刷新登录状态
        
        返回:
        - type: "ready" | "need_login"
        - credential: 凭证信息（如果ready）
        - session: 新会话（如果need_login）
        """
        cred = await self.get_user_credential(user_id, platform)
        
        if cred:
            # 检查是否需要刷新（过期前7天）
            expires = datetime.fromisoformat(cred.expires_at)
            if datetime.now() < expires - timedelta(days=7):
                return {
                    "type": "ready",
                    "credential": {
                        "platform": cred.platform,
                        "account_name": cred.account_name,
                        "cookies": cred.cookies,
                    }
                }
        
        # 需要重新登录
        session = await self.create_login_session(platform, user_id)
        
        return {
            "type": "need_login",
            "session": {
                "session_id": session.session_id,
                "qr_code": session.qr_code_base64,
                "expires_in": int((session.expires_at - datetime.now()).total_seconds()),
            }
        }
    
    def on_status_change(self, session_id: str, callback: Callable):
        """注册状态变化回调"""
        if session_id not in self._callbacks:
            self._callbacks[session_id] = []
        self._callbacks[session_id].append(callback)
    
    async def _notify_status_change(self, session_id: str, status: str):
        """通知状态变化"""
        callbacks = self._callbacks.get(session_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(session_id, status)
                else:
                    callback(session_id, status)
            except Exception as e:
                print(f"[_notify_status_change] 回调错误: {e}")
    
    async def _cleanup_expired_sessions(self):
        """清理过期会话"""
        while True:
            await asyncio.sleep(60)
            
            now = datetime.now()
            expired = []
            
            for session_id, session in self.sessions.items():
                if now > session.expires_at:
                    if session.status == LoginStatus.PENDING:
                        session.status = LoginStatus.EXPIRED
                    
                    # 过期超过10分钟的删除
                    if now > session.expires_at + timedelta(minutes=10):
                        expired.append(session_id)
            
            for session_id in expired:
                del self.sessions[session_id]
                self._callbacks.pop(session_id, None)


# 全局实例
_qr_login_manager: Optional[QRCodeLoginManager] = None


def get_qr_login_manager() -> QRCodeLoginManager:
    """获取全局二维码登录管理器"""
    global _qr_login_manager
    if _qr_login_manager is None:
        _qr_login_manager = QRCodeLoginManager()
    return _qr_login_manager
