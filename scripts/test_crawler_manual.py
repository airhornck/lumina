#!/usr/bin/env python3
"""
账号抓取器手动测试脚本

使用方法:
    python scripts/test_crawler_manual.py --platform douyin --account "余者来来"
    python scripts/test_crawler_manual.py --url "https://www.douyin.com/user/xxx"

注意:
    - 需要安装 playwright: pip install playwright && playwright install chromium
    - 首次运行会自动下载浏览器
    - 建议先测试少量账号，避免触发风控
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "rpa" / "src"))


async def test_crawler(platform: str, account_name: str = None, account_url: str = None):
    """测试账号抓取"""
    
    try:
        from rpa.browser_grid import BrowserGrid
        from rpa.account_crawler import AccountCrawler, RateLimiter, convert_to_diagnosis_format
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已安装依赖: pip install playwright && playwright install chromium")
        return
    
    print(f"\n{'='*60}")
    print(f"🚀 开始抓取账号信息")
    print(f"{'='*60}")
    print(f"平台: {platform}")
    if account_name:
        print(f"账号名: {account_name}")
    if account_url:
        print(f"账号URL: {account_url}")
    print(f"{'='*60}\n")
    
    # 初始化
    browser_grid = BrowserGrid(max_instances=1, headless=True)
    rate_limiter = RateLimiter(
        default_delay=3.0,
        platform_delays={"douyin": 4.0, "xiaohongshu": 3.5},
        max_requests_per_minute=5,
    )
    crawler = AccountCrawler(browser_grid, rate_limiter)
    
    try:
        # 执行抓取
        start_time = asyncio.get_event_loop().time()
        
        result = await crawler.crawl_account(
            account_url=account_url,
            platform=platform,
            account_id=account_name or "test",
            user_id="test_user",
            max_contents=10,
        )
        
        elapsed = asyncio.get_event_loop().time() - start_time
        
        print(f"\n✅ 抓取完成 (耗时: {elapsed:.1f}秒)")
        print(f"状态: {result.crawl_status}")
        
        if result.error_message:
            print(f"错误: {result.error_message}")
        
        print(f"\n{'='*60}")
        print("📊 账号基本信息")
        print(f"{'='*60}")
        print(f"昵称: {result.nickname or 'N/A'}")
        print(f"简介: {result.bio or 'N/A'}")
        
        print(f"\n{'='*60}")
        print("📈 数据统计")
        print(f"{'='*60}")
        print(f"粉丝数: {result.followers:,}")
        print(f"关注数: {result.following:,}")
        print(f"获赞数: {result.likes:,}")
        print(f"作品数: {result.content_count}")
        
        if result.recent_contents:
            print(f"\n{'='*60}")
            print("📝 最近作品")
            print(f"{'='*60}")
            for i, content in enumerate(result.recent_contents[:5], 1):
                title = content.get("title", "N/A")[:50]
                likes = content.get("likes_text", content.get("likes", "N/A"))
                print(f"{i}. {title}... (赞: {likes})")
        
        # 生成诊断报告
        diagnosis = convert_to_diagnosis_format(result)
        
        print(f"\n{'='*60}")
        print("🔍 诊断分析")
        print(f"{'='*60}")
        print(f"健康分: {diagnosis['health_score']}")
        print(f"内容类型: {', '.join(diagnosis['account_gene']['content_types'])}")
        print(f"风格标签: {', '.join(diagnosis['account_gene']['style_tags'])}")
        
        print(f"\n⚠️  主要问题:")
        for issue in diagnosis['key_issues']:
            print(f"  - {issue}")
        
        print(f"\n💡 改进建议:")
        for suggestion in diagnosis['improvement_suggestions']:
            print(f"  [{suggestion['area']}] {suggestion['tip']}")
        
        # 保存完整数据到文件
        output_file = f"crawl_result_{platform}_{account_name or 'test'}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "platform": result.platform,
                "account_id": result.account_id,
                "nickname": result.nickname,
                "bio": result.bio,
                "followers": result.followers,
                "following": result.following,
                "likes": result.likes,
                "content_count": result.content_count,
                "recent_contents": result.recent_contents,
                "crawl_status": result.crawl_status,
                "diagnosis": diagnosis,
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 完整数据已保存到: {output_file}")
        
    except Exception as e:
        print(f"\n❌ 抓取失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await browser_grid.close()


def main():
    parser = argparse.ArgumentParser(description="账号抓取器测试")
    parser.add_argument("--platform", choices=["douyin", "xiaohongshu"], 
                       default="douyin", help="平台类型")
    parser.add_argument("--account", help="账号名（用于搜索）")
    parser.add_argument("--url", help="账号主页URL（直接访问）")
    
    args = parser.parse_args()
    
    if not args.account and not args.url:
        print("❌ 请提供 --account 或 --url 参数")
        parser.print_help()
        return
    
    asyncio.run(test_crawler(
        platform=args.platform,
        account_name=args.account,
        account_url=args.url,
    ))


if __name__ == "__main__":
    main()
