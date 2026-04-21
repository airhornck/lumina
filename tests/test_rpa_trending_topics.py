"""
测试 RPA 抓取平台热门话题
验证 fetch_trending_topics 是否能获取到真实数据
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目路径
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "packages" / "lumina-skills" / "src"))
sys.path.insert(0, str(root / "apps" / "rpa" / "src"))


async def test_fetch_trending_topics():
    """测试抓取热门话题"""
    from lumina_skills.tool_skills import fetch_trending_topics

    platforms = [
        ("douyin", "抖音", "https://www.douyin.com/hot"),
        ("xiaohongshu", "小红书", "https://www.xiaohongshu.com/search_result?keyword=热门"),
        ("bilibili", "B站", "https://www.bilibili.com/v/popular/all"),
    ]

    print("=" * 60)
    print("开始测试 fetch_trending_topics")
    print("=" * 60)

    for platform, name, url in platforms:
        print(f"\n{'-' * 60}")
        print(f"测试平台: {name} ({platform})")
        print(f"目标URL: {url}")
        print(f"{'-' * 60}")

        start = asyncio.get_event_loop().time()
        try:
            result = await fetch_trending_topics(
                platform=platform,
                category="general",
                limit=10,
            )
            elapsed = asyncio.get_event_loop().time() - start

            has_topics = bool(result.get("topics"))
            print(f"耗时: {elapsed:.1f}s")
            print(f"结果状态: {'SUCCESS' if has_topics else 'NO_DATA'}")
            print(f"数据源: {result.get('data_source', 'unknown')}")
            if result.get('error'):
                print(f"错误信息: {result['error'][:200]}")
            if result.get('note'):
                print(f"提示: {result['note']}")

            topics = result.get("topics", [])
            print(f"抓取到话题数: {len(topics)}")

            if topics:
                print("\n话题列表 (前5条):")
                for topic in topics[:5]:
                    rank = topic.get("rank", "?")
                    title = topic.get("title", "N/A")
                    print(f"  [{rank}] {title}")
            else:
                print("WARNING: 未抓取到任何话题，可能原因:")
                print("  1. CSS 选择器不匹配目标网站 DOM")
                print("  2. 网站加载了反爬机制/验证码")
                print("  3. 页面结构已变更")
                print("  4. 页面访问超时或被拦截")

        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start
            print(f"耗时: {elapsed:.1f}s")
            print(f"ERROR: {type(e).__name__}: {str(e)}")

    print(f"\n{'=' * 60}")
    print("测试完成")
    print(f"{'=' * 60}")


async def test_registry():
    """验证 Tool Registry 是否正确注册"""
    from lumina_skills.registry import TOOL_REGISTRY

    print("\n" + "=" * 60)
    print("验证 Tool Registry 注册状态")
    print("=" * 60)

    if "fetch_trending_topics" in TOOL_REGISTRY:
        print("PASS: fetch_trending_topics 已注册到 TOOL_REGISTRY")
        print(f"   函数: {TOOL_REGISTRY['fetch_trending_topics']}")
    else:
        print("FAIL: fetch_trending_topics 未注册！")
        print(f"   当前注册项: {list(TOOL_REGISTRY.keys())}")

    return "fetch_trending_topics" in TOOL_REGISTRY


async def test_direct_call():
    """通过 Registry 直接调用"""
    from lumina_skills.registry import TOOL_REGISTRY

    print("\n" + "=" * 60)
    print("通过 TOOL_REGISTRY 直接调用测试 (抖音)")
    print("=" * 60)

    fn = TOOL_REGISTRY.get("fetch_trending_topics")
    if not fn:
        print("FAIL: 未找到函数")
        return

    try:
        result = await fn(platform="douyin", limit=5)
        result_str = json.dumps(result, ensure_ascii=False, indent=2)
        print(f"调用结果 (前800字):\n{result_str[:800]}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")


async def main():
    """主入口"""
    # 1. 验证注册
    registered = await test_registry()
    if not registered:
        print("\n注册失败，终止测试")
        return

    # 2. 直接调用测试
    await test_direct_call()

    # 3. 完整 RPA 抓取测试
    await test_fetch_trending_topics()


if __name__ == "__main__":
    asyncio.run(main())
