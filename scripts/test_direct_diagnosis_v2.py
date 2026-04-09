#!/usr/bin/env python3
"""
直接测试诊断流程 - 详细调试版
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "packages/knowledge-base/src"))
sys.path.insert(0, str(project_root / "packages/lumina-skills/src"))
sys.path.insert(0, str(project_root / "apps/rpa/src"))

async def test_crawler_directly():
    """直接测试抓取器"""
    print("="*60)
    print("直接测试 RPA 抓取器")
    print("="*60)
    
    from rpa.browser_grid import BrowserGrid
    from rpa.account_crawler import AccountCrawler, RateLimiter
    
    browser_grid = BrowserGrid(max_instances=1, headless=True)
    rate_limiter = RateLimiter(default_delay=3.0)
    crawler = AccountCrawler(browser_grid, rate_limiter)
    
    # 测试搜索
    result = await crawler.crawl_account(
        account_url="https://www.douyin.com/search/%E4%BD%99%E8%80%85%E6%9D%A5%E6%9D%A5?type=user",
        platform="douyin",
        account_id="余者来来",
        user_id="test",
        max_contents=5,
    )
    
    print(f"\n抓取结果:")
    print(f"  状态: {result.crawl_status}")
    print(f"  错误: {result.error_message}")
    print(f"  昵称: {result.nickname}")
    print(f"  粉丝: {result.followers}")
    print(f"  内容数: {result.content_count}")
    
    # 查看原始数据
    print(f"\n原始数据 (前500字符):")
    html = result.raw_data.get('html', '')[:500] if result.raw_data else 'N/A'
    print(html)
    
    return result

async def main():
    try:
        result = await test_crawler_directly()
        
        if result.crawl_status in ["success", "partial"]:
            print("\n[OK] 抓取完成")
        else:
            print("\n[FAILED] 抓取失败")
            
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
