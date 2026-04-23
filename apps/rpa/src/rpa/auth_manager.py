"""
二维码登录认证管理器

提供抖音、小红书等平台的二维码登录功能
"""

from __future__ import annotations

import asyncio
import json
import uuid
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import secrets


class LoginStatus(Enum):
    """登录状态"""
    PENDING = "pending"           # 等待扫码
    SCANNED = "scanned"           # 已扫码，等待确认
    CONFIRMED = "confirmed"       # 已确认登录
    EXPIRED = "expired"           # 二维码过期
    CANCELLED = "cancelled"       # 用户取消
    ERROR = "error"               # 错误


@dataclass
class QRCodeSession:
    """二维码登录会话"""
    session_id: str
    platform: str
    user_id: str  # 系统用户ID
    status: LoginStatus
    
    # 二维码数据
    qr_code_url: str = ""  # 二维码图片URL或Base64
    qr_code_data: str = ""  # 二维码原始数据（如URL内容）
    
    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = field(default_factory=lambda: (datetime.now() + timedelta(minutes=5)).isoformat())
    scanned_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    
    # 登录结果
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    account_info: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    
    # 回调函数（用于通知状态变化）
    _on_status_change: Optional[Callable] = field(default=None, repr=False)


@dataclass
class PlatformAccount:
    """平台账号信息"""
    platform: str
    account_id: str  # 平台账号ID（如抖音号）
    account_name: str  # 昵称
    avatar: str = ""
    
    # 凭证（加密存储）
    cookies: List[Dict[str, Any]] = field(default_factory=list)
    token: str = ""
    refresh_token: str = ""
    
    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_login_at: str = ""
    expires_at: str = ""
    
    # 账号状态
    is_active: bool = True
    login_type: str = "qrcode"  # qrcode, password, oauth


@dataclass
class UserAccount:
    """用户账号（跨平台）"""
    user_id: str
    username: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 各平台账号
    platform_accounts: Dict[str, PlatformAccount] = field(default_factory=dict)
    
    # 加密密钥（用于加密该用户的凭证）
    encryption_key: str = field(default_factory=lambda: secrets.token_hex(32))


class SecureCredentialStore:
    """
    安全凭证存储
    
    使用简单加密存储用户凭证（生产环境应使用专业密钥管理服务）
    """
    
    def __init__(self, storage_path: str = "./data/user_credentials"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._master_key = self._get_or_create_master_key()
    
    def _get_or_create_master_key(self) -> bytes:
        """获取或创建主密钥"""
        key_file = self.storage_path / ".master_key"
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return base64.b64decode(f.read())
        else:
            key = secrets.token_bytes(32)
            with open(key_file, 'wb') as f:
                f.write(base64.b64encode(key))
            return key
    
    def _encrypt(self, data: str, user_key: str) -> str:
        """加密数据（简化版XOR加密，生产环境请使用AES）"""
        key = hashlib.sha256((self._master_key.hex() + user_key).encode()).digest()
        data_bytes = data.encode('utf-8')
        encrypted = bytearray()
        for i, b in enumerate(data_bytes):
            encrypted.append(b ^ key[i % len(key)])
        return base64.b64encode(bytes(encrypted)).decode()
    
    def _decrypt(self, encrypted_data: str, user_key: str) -> str:
        """解密数据"""
        key = hashlib.sha256((self._master_key.hex() + user_key).encode()).digest()
        data_bytes = base64.b64decode(encrypted_data)
        decrypted = bytearray()
        for i, b in enumerate(data_bytes):
            decrypted.append(b ^ key[i % len(key)])
        return bytes(decrypted).decode('utf-8')
    
    def save_user_account(self, user_account: UserAccount) -> bool:
        """保存用户账号信息"""
        try:
            user_file = self.storage_path / f"{user_account.user_id}.json"
            
            # 加密敏感数据
            data = asdict(user_account)
            for platform, account in data.get("platform_accounts", {}).items():
                if account.get("cookies"):
                    cookies_json = json.dumps(account["cookies"], ensure_ascii=False)
                    account["cookies"] = self._encrypt(cookies_json, user_account.encryption_key)
                if account.get("token"):
                    account["token"] = self._encrypt(account["token"], user_account.encryption_key)
            
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"[SecureCredentialStore] 保存失败: {e}")
            return False
    
    def load_user_account(self, user_id: str) -> Optional[UserAccount]:
        """加载用户账号信息"""
        try:
            user_file = self.storage_path / f"{user_id}.json"
            if not user_file.exists():
                return None
            
            with open(user_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            user_key = data.get("encryption_key", "")
            
            # 解密敏感数据
            for platform, account in data.get("platform_accounts", {}).items():
                if account.get("cookies") and isinstance(account["cookies"], str):
                    try:
                        decrypted = self._decrypt(account["cookies"], user_key)
                        account["cookies"] = json.loads(decrypted)
                    except Exception:
                        account["cookies"] = []
                if account.get("token") and isinstance(account["token"], str):
                    try:
                        account["token"] = self._decrypt(account["token"], user_key)
                    except Exception:
                        account["token"] = ""
            
            return UserAccount(**data)
        except Exception as e:
            print(f"[SecureCredentialStore] 加载失败: {e}")
            return None
    
    def delete_user_account(self, user_id: str) -> bool:
        """删除用户账号"""
        try:
            user_file = self.storage_path / f"{user_id}.json"
            if user_file.exists():
                user_file.unlink()
            return True
        except Exception as e:
            print(f"[SecureCredentialStore] 删除失败: {e}")
            return False


class QRCodeAuthManager:
    """
    二维码登录认证管理器
    
    管理二维码生成、状态轮询、登录结果存储
    
    注：实际登录流程已委托给 rpa.qrcode_login.QRCodeLoginManager，
    本类仅做数据模型适配和 API 兼容层。
    """
    
    def __init__(self, credential_store: Optional[SecureCredentialStore] = None):
        self.sessions: Dict[str, QRCodeSession] = {}
        self.credential_store = credential_store or SecureCredentialStore()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    @property
    def _qr_manager(self):
        """延迟初始化真实的 QRCodeLoginManager"""
        from rpa.qrcode_login import get_qr_login_manager
        return get_qr_login_manager()
    
    def _map_status(self, qr_status):
        """将 qrcode_login 的状态映射到本地状态"""
        from rpa.qrcode_login import LoginStatus as QRLoginStatus
        mapping = {
            QRLoginStatus.PENDING: LoginStatus.PENDING,
            QRLoginStatus.SCANNED: LoginStatus.SCANNED,
            QRLoginStatus.CONFIRMED: LoginStatus.CONFIRMED,
            QRLoginStatus.EXPIRED: LoginStatus.EXPIRED,
            QRLoginStatus.ERROR: LoginStatus.ERROR,
        }
        return mapping.get(qr_status, LoginStatus.ERROR)
    
    def _start_cleanup_task(self):
        """启动定期清理任务"""
        async def cleanup_expired():
            while True:
                await asyncio.sleep(60)  # 每分钟检查一次
                now = datetime.now()
                expired_sessions = []
                for session_id, session in self.sessions.items():
                    expires = datetime.fromisoformat(session.expires_at)
                    if now > expires and session.status in [LoginStatus.PENDING, LoginStatus.SCANNED]:
                        session.status = LoginStatus.EXPIRED
                        expired_sessions.append(session_id)
                
                # 清理过期超过10分钟的会话
                for session_id in list(self.sessions.keys()):
                    session = self.sessions[session_id]
                    if session.status == LoginStatus.EXPIRED:
                        expires = datetime.fromisoformat(session.expires_at)
                        if now > expires + timedelta(minutes=10):
                            del self.sessions[session_id]
        
        self._cleanup_task = asyncio.create_task(cleanup_expired())
    
    async def create_qr_code_session(
        self,
        platform: str,
        user_id: str,
    ) -> QRCodeSession:
        """
        创建二维码登录会话
        
        委托给 QRCodeLoginManager 启动真实浏览器流程获取二维码
        """
        # 调用真实实现创建登录会话
        qr_session = await self._qr_manager.create_login_session(platform, user_id)
        
        # 转换数据格式
        session = QRCodeSession(
            session_id=qr_session.session_id,
            platform=qr_session.platform,
            user_id=qr_session.user_id,
            status=self._map_status(qr_session.status),
            qr_code_url=f"data:image/png;base64,{qr_session.qr_code_base64}",
            qr_code_data=qr_session.qr_content,
            created_at=qr_session.created_at.isoformat(),
            expires_at=qr_session.expires_at.isoformat(),
        )
        
        self.sessions[session.session_id] = session
        
        # 启动状态同步任务
        asyncio.create_task(self._sync_session_status(session.session_id))
        
        return session
    
    async def _generate_qr_code_image(self, content: str) -> str:
        """生成二维码图片（Base64）"""
        try:
            import qrcode
            from io import BytesIO
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
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
            # 如果没有 qrcode 库，返回一个占位图
            return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    
    async def _sync_session_status(self, session_id: str):
        """
        同步 qrcode_login 的会话状态到本地缓存
        
        真实登录流程由 QRCodeLoginManager._start_browser_login 处理，
        这里只负责同步状态和保存凭证。
        """
        for _ in range(300):  # 最多轮询 300 次（约 10 分钟）
            await asyncio.sleep(2)
            
            session = self.sessions.get(session_id)
            if not session:
                break
            
            # 从真实 manager 获取最新状态
            qr_status = await self._qr_manager.get_session_status(session_id)
            if not qr_status:
                break
            
            from rpa.qrcode_login import LoginStatus as QRLoginStatus
            new_status = self._map_status(QRLoginStatus(qr_status["status"]))
            
            if new_status != session.status:
                session.status = new_status
                
                if new_status == LoginStatus.CONFIRMED:
                    session.confirmed_at = datetime.now().isoformat()
                    if qr_status.get("account_info"):
                        session.account_info = qr_status["account_info"]
                    # 获取凭证并保存
                    cred = await self._qr_manager.get_user_credential(
                        session.user_id, session.platform
                    )
                    if cred:
                        session.cookies = cred.cookies
                        session.account_info = {
                            "account_id": cred.account_id,
                            "nickname": cred.account_name,
                            "avatar": "",
                        }
                        await self._save_login_result(session)
                    break
                elif new_status in (LoginStatus.EXPIRED, LoginStatus.ERROR):
                    break
    
    async def _poll_login_status(self, session_id: str, platform: str):
        """
        轮询登录状态（已废弃，由 _sync_session_status 替代）
        
        保留此方法以维持 API 兼容性。
        """
        pass
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        return {
            "session_id": session.session_id,
            "platform": session.platform,
            "status": session.status.value,
            "qr_code_url": session.qr_code_url if session.status == LoginStatus.PENDING else None,
            "created_at": session.created_at,
            "expires_at": session.expires_at,
            "account_info": session.account_info if session.status == LoginStatus.CONFIRMED else None,
        }
    
    async def confirm_login(
        self,
        session_id: str,
        cookies: List[Dict[str, Any]],
        account_info: Dict[str, Any],
    ) -> bool:
        """
        确认登录成功
        
        由 BrowserGrid 在扫码成功后调用
        """
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        if session.status != LoginStatus.SCANNED:
            return False
        
        session.status = LoginStatus.CONFIRMED
        session.confirmed_at = datetime.now().isoformat()
        session.cookies = cookies
        session.account_info = account_info
        
        # 保存到用户账号
        await self._save_login_result(session)
        
        return True
    
    async def _save_login_result(self, session: QRCodeSession):
        """保存登录结果到用户账号"""
        user_account = self.credential_store.load_user_account(session.user_id)
        
        if not user_account:
            # 创建新用户
            user_account = UserAccount(
                user_id=session.user_id,
                username=session.user_id,  # 使用ID作为默认用户名
            )
        
        # 创建平台账号
        platform_account = PlatformAccount(
            platform=session.platform,
            account_id=session.account_info.get("account_id", ""),
            account_name=session.account_info.get("nickname", ""),
            avatar=session.account_info.get("avatar", ""),
            cookies=session.cookies,
            login_type="qrcode",
            last_login_at=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(days=30)).isoformat(),
        )
        
        user_account.platform_accounts[session.platform] = platform_account
        
        # 保存
        self.credential_store.save_user_account(user_account)
    
    async def get_user_platform_account(
        self,
        user_id: str,
        platform: str,
    ) -> Optional[PlatformAccount]:
        """获取用户的平台账号"""
        # 优先从真实 manager 获取凭证
        cred = await self._qr_manager.get_user_credential(user_id, platform)
        if cred:
            account = PlatformAccount(
                platform=cred.platform,
                account_id=cred.account_id,
                account_name=cred.account_name,
                cookies=cred.cookies,
                login_type="qrcode",
                last_login_at=cred.created_at,
                expires_at=cred.expires_at,
                is_active=cred.is_active,
            )
            # 检查是否过期
            if account.expires_at:
                expires = datetime.fromisoformat(account.expires_at)
                if datetime.now() > expires:
                    account.is_active = False
            return account if account.is_active else None
        
        # Fallback：从本地 credential_store 读取
        user_account = self.credential_store.load_user_account(user_id)
        if not user_account:
            return None
        
        account = user_account.platform_accounts.get(platform)
        if not account:
            return None
        
        if account.expires_at:
            expires = datetime.fromisoformat(account.expires_at)
            if datetime.now() > expires:
                account.is_active = False
        
        return account if account.is_active else None
    
    async def get_or_create_auth_session(
        self,
        user_id: str,
        platform: str,
    ) -> Dict[str, Any]:
        """
        获取或创建认证会话
        
        如果有有效的登录凭证，直接返回
        否则创建二维码登录会话
        """
        # 委托给真实 manager 检查凭证状态
        result = await self._qr_manager.check_and_refresh_login(user_id, platform)
        
        if result["type"] == "ready":
            cred = result.get("credential", {})
            return {
                "type": "existing",
                "account": {
                    "platform": platform,
                    "account_id": "",
                    "account_name": cred.get("account_name", ""),
                    "avatar": "",
                },
            }
        
        # 需要重新登录，创建二维码会话
        session = await self.create_qr_code_session(platform, user_id)
        
        return {
            "type": "qr_code",
            "session_id": session.session_id,
            "qr_code_url": session.qr_code_url,
            "expires_at": session.expires_at,
        }
    
    async def logout_platform(self, user_id: str, platform: str) -> bool:
        """退出平台登录"""
        user_account = self.credential_store.load_user_account(user_id)
        if not user_account:
            return False
        
        if platform in user_account.platform_accounts:
            user_account.platform_accounts[platform].is_active = False
            return self.credential_store.save_user_account(user_account)
        
        return True


# 全局实例
_auth_manager: Optional[QRCodeAuthManager] = None


def get_auth_manager() -> QRCodeAuthManager:
    """获取全局认证管理器实例"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = QRCodeAuthManager()
    return _auth_manager
