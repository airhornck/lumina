"""
使用真实 Cookie 测试小红书登录访问
验证能否获取到笔记内容
"""

import asyncio
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "apps" / "rpa" / "src"))

# 用户提供的 Cookie
cookie_str = "a1=19cdbf89844wtn4sjagtymcuh85j5qmuyqvhxhuta50000139209; webId=c627f37c5ca63300818755771909cc87; gid=yjSfDiY0W2vWyjSfDiYjYAx744E9I4MV0k9vh906S7xY2x28V2A67C888yqjJ8j88Yd2djKY; x-user-id-creator.xiaohongshu.com=66c1e7e8000000001d032e3d; customerClientId=529591855589904; abRequestId=c627f37c5ca63300818755771909cc87; ets=1776785973965; webBuild=6.7.0; acw_tc=0a4ac1bc17767859758541731e836a17f192d74fd9a5d9a499cfd5d0fb1228; websectiga=3633fe24d49c7dd0eb923edc8205740f10fdb18b25d424d2a2322c6196d2a4ad; sec_poison_id=0b856f19-874b-4384-a0ea-451fe72e7f57; web_session=040069b7b5a4a0257e6b26d2d23b4b43e2a85d; id_token=VjEAAIk9rxnH4n/AthT/FmIWNKfA2TQ4kjmJGQ5KgUXEZJfjfjMbJJJVTXTaldeHi/K2TgU6Yz0FHcgqSsKBoCyxA3JQzM1vdV7VVnIcWhx/zLI0AfsgcpRl1IXmUbuThVo35kE2; unread={%22ub%22:%2269ddbe6b0000000023021fff%22%2C%22ue%22:%2269ca4e5e0000000028009f5a%22%2C%22uc%22:25}; xsecappid=ranchi; loadts=1776786155691"


def parse_cookie_string(cookie_str: str) -> list:
    """解析 Cookie 字符串为 Playwright 格式"""
    cookies = []
    for item in cookie_str.split("; "):
        if "=" in item:
            name, value = item.split("=", 1)
            # 处理 domain 为 xiaohongshu.com 的 cookie
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".xiaohongshu.com",
                "path": "/",
            })
    return cookies


async def test_with_cookie(url: str, name: str):
    """使用 Cookie 访问小红书"""
    print(f"\n{'=' * 70}")
    print(f"测试: {name}")
    print(f"URL: {url}")
    print(f"{'=' * 70}")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright 未安装")
        return

    cookies = parse_cookie_string(cookie_str)
    print(f"Cookie 条目数: {len(cookies)}")
    print(f"关键 Cookie: web_session={[c['value'][:20]+'...' for c in cookies if c['name']=='web_session'][0] if any(c['name']=='web_session' for c in cookies) else 'N/A'}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        
        # 添加 Cookie
        await context.add_cookies(cookies)
        print("Cookie 已添加到浏览器上下文")
        
        page = await context.new_page()

        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print(f"页面响应状态: {response.status if response else 'N/A'}")
            
            # 等待渲染
            await asyncio.sleep(8)
            
            # 滚动触发懒加载
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(2)
            
            print(f"当前URL: {page.url}")
            
            # 检查页面内容
            body_text = await page.evaluate("() => document.body.innerText")
            print(f"页面文本长度: {len(body_text)} 字符")
            
            # 检查是否有登录提示
            login_indicators = ["登录", "注册", "手机号", "验证码", "立即登录", "登录查看"]
            has_login_prompt = any(ind in body_text[:3000] for ind in login_indicators)
            print(f"是否有登录提示: {has_login_prompt}")
            
            if has_login_prompt:
                print("WARNING: Cookie 可能已过期，页面仍要求登录")
                # 打印前20行看看有什么
                lines = [l.strip() for l in body_text.split('\n') if l.strip()]
                print("\n页面文本（前20行）:")
                for i, line in enumerate(lines[:20]):
                    print(f"  [{i+1}] {line[:80]}")
            else:
                print("SUCCESS: 页面未要求登录，可能有内容！")
                
                # 分析span元素
                spans = await page.query_selector_all("span")
                print(f"\nspan元素总数: {len(spans)}")
                span_texts = []
                for el in spans[:60]:
                    text = await el.text_content()
                    if text and 8 < len(text.strip()) < 80:
                        span_texts.append(text.strip())
                if span_texts:
                    print(f"有意义的span文本（前20条）:")
                    for i, t in enumerate(span_texts[:20]):
                        print(f"  [{i+1}] {t[:70]}")
                
                # 分析div元素
                divs = await page.query_selector_all("div")
                print(f"\ndiv元素总数: {len(divs)}")
                div_texts = []
                for el in divs[:100]:
                    text = await el.text_content()
                    if text and 8 < len(text.strip()) < 80:
                        div_texts.append(text.strip())
                if div_texts:
                    print(f"有意义的div文本（前20条）:")
                    for i, t in enumerate(div_texts[:20]):
                        print(f"  [{i+1}] {t[:70]}")
            
            await browser.close()
            print(f"\n{name} 测试完成")
            return not has_login_prompt

        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {str(e)}")
            await browser.close()
            return False


async def main():
    urls = [
        ("https://www.xiaohongshu.com/explore", "小红书发现页（带Cookie）"),
        ("https://www.xiaohongshu.com/search_result?keyword=职场&type=51", "小红书搜索-职场（带Cookie）"),
        ("https://www.xiaohongshu.com/search_result?keyword=穿搭&type=51", "小红书搜索-穿搭（带Cookie）"),
    ]

    success_count = 0
    for url, name in urls:
        success = await test_with_cookie(url, name)
        if success:
            success_count += 1
        await asyncio.sleep(3)

    print(f"\n{'=' * 70}")
    print(f"Cookie 登录测试完成: {success_count}/{len(urls)} 个页面成功绕过登录")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
