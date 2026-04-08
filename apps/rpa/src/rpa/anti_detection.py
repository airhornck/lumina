"""
反检测层

提供浏览器指纹伪装能力，绕过平台风控检测
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BrowserFingerprint:
    """浏览器指纹"""
    user_agent: str
    screen_resolution: str
    color_depth: int
    timezone: str
    language: str
    platform: str
    canvas_noise: float
    webgl_vendor: str
    webgl_renderer: str
    plugins: List[str] = field(default_factory=list)
    fonts: List[str] = field(default_factory=list)


class FingerprintGenerator:
    """指纹生成器"""
    
    # 常见的 User-Agent 列表
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ]
    
    # 屏幕分辨率
    SCREEN_RESOLUTIONS = [
        "1920x1080",
        "1366x768",
        "1440x900",
        "1536x864",
        "1280x720",
    ]
    
    # WebGL 厂商和渲染器
    WEBGL_CONFIGS = [
        ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        ("Apple Inc.", "Apple M1"),
        ("Intel Inc.", "Intel Iris Xe Graphics"),
    ]
    
    @classmethod
    def generate(cls, seed: Optional[str] = None) -> BrowserFingerprint:
        """生成随机指纹"""
        if seed:
            random.seed(seed)
        
        webgl_vendor, webgl_renderer = random.choice(cls.WEBGL_CONFIGS)
        
        return BrowserFingerprint(
            user_agent=random.choice(cls.USER_AGENTS),
            screen_resolution=random.choice(cls.SCREEN_RESOLUTIONS),
            color_depth=24,
            timezone=random.choice(["Asia/Shanghai", "Asia/Hong_Kong", "Asia/Singapore"]),
            language=random.choice(["zh-CN", "zh-TW", "en-US", "en-GB"]),
            platform=random.choice(["Win32", "MacIntel"]),
            canvas_noise=random.uniform(-0.0001, 0.0001),
            webgl_vendor=webgl_vendor,
            webgl_renderer=webgl_renderer,
            plugins=["Chrome PDF Viewer", "Widevine Content Decryption Module"],
            fonts=["Arial", "Times New Roman", "Helvetica", "Microsoft YaHei"],
        )


class AntiDetectionLayer:
    """
    反检测层
    
    应用各种反检测技术绕过平台风控
    """
    
    def __init__(self):
        self.fingerprint_generator = FingerprintGenerator()
    
    def generate_fingerprint(self, seed: Optional[str] = None) -> BrowserFingerprint:
        """生成浏览器指纹"""
        return self.fingerprint_generator.generate(seed)
    
    async def apply(self, page, fingerprint: BrowserFingerprint) -> None:
        """
        应用指纹到浏览器页面
        
        Args:
            page: Playwright 页面实例
            fingerprint: 浏览器指纹
        """
        # 设置 User-Agent
        await page.set_extra_http_headers({
            "User-Agent": fingerprint.user_agent,
            "Accept-Language": fingerprint.language,
        })
        
        # 注入脚本修改浏览器指纹
        await page.add_init_script(f"""
            // 修改 navigator 属性
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined
            }});
            
            Object.defineProperty(navigator, 'plugins', {{
                get: () => {fingerprint.plugins}
            }});
            
            Object.defineProperty(navigator, 'languages', {{
                get: () => ['{fingerprint.language}']
            }});
            
            // 修改屏幕属性
            Object.defineProperty(screen, 'width', {{
                get: () => {fingerprint.screen_resolution.split('x')[0]}
            }});
            
            Object.defineProperty(screen, 'height', {{
                get: () => {fingerprint.screen_resolution.split('x')[1]}
            }});
            
            // Canvas 噪声
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(...args) {{
                const imageData = originalGetImageData.apply(this, args);
                for (let i = 0; i < imageData.data.length; i += 4) {{
                    imageData.data[i] += {fingerprint.canvas_noise};
                }}
                return imageData;
            }};
        """)
    
    def get_stealth_scripts(self) -> List[str]:
        """获取所有隐身脚本"""
        return [
            self._webdriver_hide_script(),
            self._chrome_runtime_script(),
            self._permissions_script(),
        ]
    
    def _webdriver_hide_script(self) -> str:
        """隐藏 webdriver 标记"""
        return """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """
    
    def _chrome_runtime_script(self) -> str:
        """模拟 Chrome runtime"""
        return """
            window.chrome = {
                runtime: {
                    OnInstalledReason: {
                        CHROME_UPDATE: "chrome_update",
                        INSTALL: "install",
                        SHARED_MODULE_UPDATE: "shared_module_update",
                        UPDATE: "update"
                    },
                    OnRestartRequiredReason: {
                        APP_UPDATE: "app_update",
                        OS_UPDATE: "os_update",
                        PERIODIC: "periodic"
                    },
                    PlatformArch: {
                        ARM: "arm",
                        ARM64: "arm64",
                        MIPS: "mips",
                        MIPS64: "mips64",
                        X86_32: "x86-32",
                        X86_64: "x86-64"
                    },
                    PlatformNaclArch: {
                        ARM: "arm",
                        MIPS: "mips",
                        MIPS64: "mips64",
                        MIPS64EL: "mips64el",
                        MIPS32: "mipsel",
                        X86_32: "x86-32",
                        X86_64: "x86-64"
                    },
                    PlatformOs: {
                        ANDROID: "android",
                        CROS: "cros",
                        LINUX: "linux",
                        MAC: "mac",
                        OPENBSD: "openbsd",
                        WIN: "win"
                    },
                    RequestUpdateCheckStatus: {
                        NO_UPDATE: "no_update",
                        THROTTLED: "throttled",
                        UPDATE_AVAILABLE: "update_available"
                    }
                }
            };
        """
    
    def _permissions_script(self) -> str:
        """处理权限 API"""
        return """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' 
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters)
            );
        """
