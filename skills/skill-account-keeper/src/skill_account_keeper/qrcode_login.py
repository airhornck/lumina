"""
账号保持者 - 二维码登录扩展

提供二维码登录相关的 Skill 接口
"""

from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, Dict, Any

mcp = FastMCP("account_keeper_qrlogin")


class QRCodeLoginInput(BaseModel):
    """二维码登录输入"""
    platform: str  # douyin, xiaohongshu
    user_id: str


class QRCodeStatusInput(BaseModel):
    """查询登录状态输入"""
    session_id: str
    user_id: str


@mcp.tool()
async def request_qr_code_login(input: QRCodeLoginInput) -> Dict[str, Any]:
    """
    请求二维码登录
    
    生成二维码并返回给用户扫码
    """
    try:
        from rpa.qrcode_login import get_qr_login_manager
        
        manager = get_qr_login_manager()
        
        # 检查是否已有有效凭证
        result = await manager.check_and_refresh_login(
            user_id=input.user_id,
            platform=input.platform,
        )
        
        if result["type"] == "ready":
            # 已有有效登录
            return {
                "type": "already_logged_in",
                "platform": input.platform,
                "account_name": result["credential"]["account_name"],
                "message": f"已登录 {input.platform} 账号: {result['credential']['account_name']}",
            }
        
        # 需要扫码登录
        session = result["session"]
        
        return {
            "type": "qr_code",
            "platform": input.platform,
            "session_id": session["session_id"],
            "qr_code_base64": session["qr_code"],
            "expires_in": session["expires_in"],
            "message": f"请使用 {input.platform} APP 扫描下方二维码登录",
            "instructions": [
                f"1. 打开 {input.platform} APP",
                "2. 点击右上角扫一扫",
                "3. 扫描下方二维码",
                "4. 在手机上确认登录",
            ],
        }
        
    except Exception as e:
        return {
            "type": "error",
            "error": str(e),
            "message": "生成二维码失败，请稍后重试",
        }


@mcp.tool()
async def check_login_status(input: QRCodeStatusInput) -> Dict[str, Any]:
    """
    检查登录状态
    
    轮询检查用户是否已完成扫码登录
    """
    try:
        from rpa.qrcode_login import get_qr_login_manager
        
        manager = get_qr_login_manager()
        status = await manager.get_session_status(input.session_id)
        
        if not status:
            return {
                "status": "not_found",
                "message": "会话不存在或已过期",
            }
        
        if status["status"] == "confirmed":
            return {
                "status": "success",
                "platform": status["platform"],
                "account_info": status["account_info"],
                "message": f"登录成功！已保存 {status['platform']} 账号信息",
            }
        
        elif status["status"] == "pending":
            return {
                "status": "waiting",
                "expires_in": status["expires_in"],
                "message": "等待扫码...",
            }
        
        elif status["status"] == "scanned":
            return {
                "status": "scanned",
                "message": "已扫码，请在手机上确认登录",
            }
        
        elif status["status"] == "expired":
            return {
                "status": "expired",
                "message": "二维码已过期，请重新获取",
            }
        
        else:
            return {
                "status": status["status"],
                "message": "登录状态异常",
            }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@mcp.tool()
async def get_saved_accounts(user_id: str) -> Dict[str, Any]:
    """
    获取已保存的账号列表
    """
    try:
        from rpa.qrcode_login import get_qr_login_manager
        
        manager = get_qr_login_manager()
        
        platforms = ["douyin", "xiaohongshu"]
        accounts = []
        
        for platform in platforms:
            cred = await manager.get_user_credential(user_id, platform)
            if cred:
                accounts.append({
                    "platform": platform,
                    "account_name": cred.account_name,
                    "expires_at": cred.expires_at,
                    "is_active": cred.is_active,
                })
        
        return {
            "accounts": accounts,
            "total": len(accounts),
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "accounts": [],
        }


@mcp.tool()
async def logout_platform(platform: str, user_id: str) -> Dict[str, Any]:
    """
    退出平台登录
    """
    try:
        from rpa.qrcode_login import get_qr_login_manager
        
        manager = get_qr_login_manager()
        await manager.logout_platform(user_id, platform)
        
        return {
            "success": True,
            "message": f"已退出 {platform} 登录",
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


if __name__ == "__main__":
    mcp.run(transport="sse")
