"""
调试平台热榜页 DOM 结构
用 Playwright 打开实际页面，分析热门话题元素的选择器
"""

import asyncio
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "apps" / "rpa" / "src"))


async def debug_platform_page(platform: str, url: str, name: str):
    """调试单个平台页面"""
    print(f"\n{'=' * 70}")
    print(f"调试平台: {name} ({platform})")
    print(f"URL: {url}")
    print(f"{'=' * 70}")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright 未安装")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            print("正在打开页面...")
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print(f"页面响应状态: {response.status if response else 'N/A'}")

            # 等待页面加载
            await asyncio.sleep(5)
            print("页面已加载，开始分析 DOM...")

            # 1. 获取页面标题和 URL
            title = await page.title()
            current_url = page.url
            print(f"\n页面标题: {title}")
            print(f"当前URL: {current_url}")

            # 2. 尝试多种可能的选择器
            selector_candidates = [
                # 通用类名
                '[class*="hot"]',
                '[class*="trend"]',
                '[class*="rank"]',
                '[class*="popular"]',
                '[class*="topic"]',
                # 通用 data 属性
                '[data-e2e]',
                '[data-testid]',
                '[data-v-*]',
                # 链接相关
                'a[href*="hot"]',
                'a[href*="trend"]',
                # 列表项
                'li',
                'div[role="listitem"]',
                # 文本较长的元素（可能是话题标题）
            ]

            print("\n--- 选择器探测结果 ---")
            for selector in selector_candidates:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        texts = []
                        for el in elements[:5]:
                            text = await el.text_content()
                            if text and len(text.strip()) > 2 and len(text.strip()) < 100:
                                texts.append(text.strip()[:50])
                        if texts:
                            print(f"\n[{selector}] -> 匹配 {len(elements)} 个元素")
                            for i, t in enumerate(texts[:3]):
                                print(f"  [{i+1}] {t}")
                except Exception as e:
                    pass

            # 3. 获取页面 body 中的文本内容（前2000字符）
            print("\n--- 页面文本内容（前2000字符）---")
            body_text = await page.evaluate("() => document.body.innerText")
            print(body_text[:2000] if body_text else "(空)")

            # 4. 获取 body 中的 HTML 结构（前3000字符）
            print("\n--- 页面 HTML 结构（前3000字符）---")
            body_html = await page.evaluate("() => document.body.innerHTML")
            print(body_html[:3000] if body_html else "(空)")

            # 5. 尝试查找包含数字的元素（排名）
            print("\n--- 包含数字的元素（可能是排名）---")
            try:
                all_elements = await page.query_selector_all("*")
                numbered_elements = []
                for el in all_elements[:200]:
                    text = await el.text_content()
                    if text and text.strip().isdigit() and 1 <= int(text.strip()) <= 50:
                        parent = await el.evaluate("el => el.parentElement ? el.parentElement.outerHTML.substring(0,200) : ''")
                        numbered_elements.append((text.strip(), parent[:100]))
                for num, parent in numbered_elements[:10]:
                    print(f"  排名: {num} -> 父元素: {parent[:80]}")
            except Exception as e:
                print(f"查找数字元素失败: {e}")

            await browser.close()
            print(f"\n{name} 调试完成")

        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {str(e)}")
            await browser.close()


async def main():
    platforms = [
        ("douyin", "https://www.douyin.com/hot", "抖音热榜"),
        ("xiaohongshu", "https://www.xiaohongshu.com/search_result?keyword=热门", "小红书热门"),
        ("bilibili", "https://www.bilibili.com/v/popular/all", "B站热门"),
    ]

    for platform, url, name in platforms:
        await debug_platform_page(platform, url, name)
        await asyncio.sleep(2)

    print(f"\n{'=' * 70}")
    print("所有平台调试完成")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
