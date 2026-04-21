"""
深度调试小红书页面DOM结构
测试多种公开页面URL和选择器策略
"""

import asyncio
import json
import sys
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "apps" / "rpa" / "src"))


async def debug_xiaohongshu_page(url: str, name: str):
    """调试小红书指定页面"""
    print(f"\n{'=' * 70}")
    print(f"调试: {name}")
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
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print(f"页面响应状态: {response.status if response else 'N/A'}")
            
            # 等待更长时间（小红书是SPA，需要等Vue渲染）
            await asyncio.sleep(8)
            
            # 滚动触发懒加载
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(2)
            
            print(f"当前URL: {page.url}")
            
            # 1. 获取页面文本（用于判断是否有内容）
            body_text = await page.evaluate("() => document.body.innerText")
            print(f"\n页面文本长度: {len(body_text)} 字符")
            
            # 2. 检查是否有登录提示
            login_indicators = ["登录", "注册", "手机号", "验证码", "立即登录"]
            has_login_prompt = any(ind in body_text[:2000] for ind in login_indicators)
            print(f"是否有登录提示: {has_login_prompt}")
            
            # 3. 打印页面文本前1500字符（过滤掉页脚）
            # 找到前1500个有意义的字符
            clean_text = re.sub(r'[\n\r]+', '\n', body_text)
            lines = [l.strip() for l in clean_text.split('\n') if len(l.strip()) > 3]
            # 过滤掉页脚法律文本
            skip_prefixes = ["ICP", "备案", "许可证", "增值电信", "网安备", "扫黄打非", "不良信息"]
            content_lines = []
            for line in lines:
                if any(line.startswith(sp) for sp in skip_prefixes):
                    break
                content_lines.append(line)
            
            print(f"\n页面内容（前30行非页脚文本）:")
            for i, line in enumerate(content_lines[:30]):
                print(f"  [{i+1}] {line[:80]}")
            
            # 4. 分析DOM结构：查找所有span和div中的文本
            print(f"\n--- DOM元素分析 ---")
            
            # 分析span元素
            spans = await page.query_selector_all("span")
            print(f"span元素总数: {len(spans)}")
            span_texts = []
            for el in spans[:50]:
                text = await el.text_content()
                if text and 5 < len(text.strip()) < 60:
                    span_texts.append(text.strip())
            if span_texts:
                print(f"\n有意义的span文本（前15条）:")
                for i, t in enumerate(span_texts[:15]):
                    print(f"  [{i+1}] {t[:60]}")
            
            # 分析div元素
            divs = await page.query_selector_all("div")
            print(f"\ndiv元素总数: {len(divs)}")
            div_texts = []
            for el in divs[:80]:
                text = await el.text_content()
                if text and 5 < len(text.strip()) < 60:
                    div_texts.append(text.strip())
            if div_texts:
                print(f"\n有意义的div文本（前15条）:")
                for i, t in enumerate(div_texts[:15]):
                    print(f"  [{i+1}] {t[:60]}")
            
            # 5. 尝试提取图片alt属性（小红书很多内容在图片alt中）
            images = await page.query_selector_all("img")
            print(f"\n图片总数: {len(images)}")
            img_alts = []
            for img in images[:30]:
                alt = await img.get_attribute("alt")
                if alt and len(alt.strip()) > 5:
                    img_alts.append(alt.strip())
            if img_alts:
                print(f"\n图片alt文本（前10条）:")
                for i, alt in enumerate(img_alts[:10]):
                    print(f"  [{i+1}] {alt[:60]}")
            
            # 6. 尝试获取所有链接文本
            links = await page.query_selector_all("a")
            print(f"\n链接总数: {len(links)}")
            link_texts = []
            for link in links[:40]:
                text = await link.text_content()
                href = await link.get_attribute("href")
                if text and 5 < len(text.strip()) < 60:
                    link_texts.append((text.strip(), href))
            if link_texts:
                print(f"\n有意义的链接文本（前15条）:")
                for i, (text, href) in enumerate(link_texts[:15]):
                    print(f"  [{i+1}] {text[:50]} -> {href[:40] if href else 'N/A'}")
            
            await browser.close()
            print(f"\n{name} 调试完成")

        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {str(e)}")
            await browser.close()


async def main():
    urls = [
        ("https://www.xiaohongshu.com/explore", "小红书发现页（无需搜索词）"),
        ("https://www.xiaohongshu.com/search_result?keyword=热门&type=51", "小红书搜索-热门"),
        ("https://www.xiaohongshu.com/search_result?keyword=职场&type=51", "小红书搜索-职场"),
        ("https://www.xiaohongshu.com/search_result?keyword=穿搭&type=51", "小红书搜索-穿搭"),
    ]

    for url, name in urls:
        await debug_xiaohongshu_page(url, name)
        await asyncio.sleep(3)

    print(f"\n{'=' * 70}")
    print("小红书所有页面调试完成")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
